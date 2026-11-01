"""Read-only PNG exports: embedded resources or a visible page region."""

import io
import math
import pymupdf as fitz
from PIL import Image, ImageChops
from fastapi import HTTPException
from ..core import MAX_PIXELS


def embedded_png(document, page, xref):
    entry = next((item for item in page.get_images() if item[0] == xref), None)
    if entry is None:
        raise HTTPException(
            404,
            "This image is not embedded on the selected page. Select its visible region instead.",
        )
    if entry[2] * entry[3] > MAX_PIXELS:
        raise HTTPException(
            413,
            "Image exceeds the configured pixel limit. Export a smaller visible region.",
        )
    pix = fitz.Pixmap(document, xref)
    if pix.colorspace and pix.colorspace.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    mask = document.extract_image(xref).get("smask", 0)
    if mask and not pix.alpha:
        pix = fitz.Pixmap(pix, fitz.Pixmap(document, mask))
    return pix.tobytes("png")


def region_png(page, rect, dpi, remove_white):
    if not all(math.isfinite(v) for v in rect):
        raise HTTPException(422, "Select a valid rectangle around the signature.")
    region = fitz.Rect(rect)
    if region.is_empty or not (page.rect * page.derotation_matrix).contains(region):
        raise HTTPException(
            422, "The selected signature region must be inside the page."
        )
    display = region * page.rotation_matrix
    scale = dpi / 72
    if (
        math.ceil(display.width * scale + 2) * math.ceil(display.height * scale + 2)
        > MAX_PIXELS
    ):
        raise HTTPException(
            413,
            "Selected region exceeds the pixel limit. Reduce resolution or select a smaller area.",
        )
    pix = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale), clip=display, alpha=True, annots=True
    )
    if not remove_white:
        return pix.tobytes("png")
    with Image.open(io.BytesIO(pix.tobytes("png"))) as image:
        image = image.convert("RGBA")
        # Explicit opt-in: remove near-white paper, preserving dark/colored ink.
        red, green, blue, alpha = image.split()
        minimum = ImageChops.darker(ImageChops.darker(red, green), blue)
        keep = minimum.point(lambda value: 0 if value >= 240 else 255)
        image.putalpha(ImageChops.multiply(alpha, keep))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()
