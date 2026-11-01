"""Erase raster samples, retaining original color spaces and image masks."""

import io
import math
import pymupdf as fitz
from PIL import Image


def erase_simple_images(document, page, region):
    images = [
        item
        for item in page.get_image_info(xrefs=True)
        if fitz.Rect(item["bbox"]).intersects(region)
    ]
    prepared = []
    for item in images:
        xref = item["xref"]
        if not xref or not fitz.Matrix(item["transform"]).is_rectilinear:
            return False
        if sum(len(other.get_image_rects(xref)) for other in document) != 1:
            return False
        if document.xref_get_key(xref, "Decode")[0] != "null":
            return False
        pix = fitz.Pixmap(document, xref)
        if pix.alpha or not pix.colorspace or pix.colorspace.n not in (1, 3):
            return False
        if document.xref_get_key(xref, "BitsPerComponent")[1] != "8":
            return False
        mask_xref = document.extract_image(xref).get("smask", 0)
        mask = fitz.Pixmap(document, mask_xref) if mask_xref else None
        mask_kind = (
            "SMask" if document.xref_get_key(xref, "SMask")[0] != "null" else "Mask"
        )
        hard = bool(mask and mask.colorspace is None)
        if mask and (
            mask.n != 1
            or mask.width != pix.width
            or mask.height != pix.height
            or document.xref_get_key(mask_xref, "Decode")[0] != "null"
        ):
            return False
        if mask and document.xref_get_key(mask_xref, "BitsPerComponent")[1] not in (
            "1" if hard else "8",
        ):
            return False
        normalized = region * ~fitz.Matrix(item["transform"])
        normalized &= fitz.Rect(0, 0, 1, 1)
        box = (
            max(0, math.floor(normalized.x0 * pix.width)),
            max(0, math.floor(normalized.y0 * pix.height)),
            min(pix.width, math.ceil(normalized.x1 * pix.width)),
            min(pix.height, math.ceil(normalized.y1 * pix.height)),
        )
        raster = Image.frombytes(
            "RGB" if pix.n == 3 else "L", (pix.width, pix.height), pix.samples
        )
        raster.paste((255, 255, 255) if pix.n == 3 else 255, box)
        stream = io.BytesIO()
        raster.save(stream, format="PNG")
        alpha = None
        if mask:
            alpha = Image.frombytes("L", (mask.width, mask.height), mask.samples)
            alpha.paste(255, box)
            if hard:
                alpha = alpha.point(lambda value: 0 if value else 255, mode="1")
        prepared.append(
            (
                xref,
                stream.getvalue(),
                mask_xref,
                mask_kind,
                alpha,
                document.xref_get_key(xref, "Interpolate"),
                document.xref_get_key(xref, "ColorSpace"),
            )
        )
    for xref, stream, mask_xref, mask_kind, alpha, interpolate, color_space in prepared:
        page.replace_image(xref, stream=stream)
        # Inserting a PNG may otherwise introduce an sRGB ICC profile and
        # change pixels everywhere, even though their samples did not change.
        document.xref_set_key(xref, "ColorSpace", color_space[1])
        document.xref_set_key(xref, "Interpolate", interpolate[1])
        if alpha is not None:
            clone = document.get_new_xref()
            document.update_object(clone, document.xref_object(mask_xref))
            document.xref_set_key(clone, "DecodeParms", "null")
            document.update_stream(clone, alpha.tobytes(), compress=True)
            document.xref_set_key(xref, "SMask", "null")
            document.xref_set_key(xref, "Mask", "null")
            document.xref_set_key(xref, mask_kind, f"{clone} 0 R")
    return True
