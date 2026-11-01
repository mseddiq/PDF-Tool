import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Event
import pymupdf as fitz
from docx import Document
from docx.shared import Pt
from PIL import Image, ImageOps
import pytesseract
from ..core import TIMEOUT, MAX_PIXELS
from .runtime import configure_ocr, office_binary


class Cancelled(Exception):
    pass


def checkpoint(cancel):
    if cancel.is_set():
        raise Cancelled("Job cancelled.")


def word_to_pdf(source, destination, cancel):
    binary = office_binary()
    if not binary:
        raise ValueError(
            "LibreOffice is not installed. Install it and add its program directory to PATH."
        )
    with tempfile.TemporaryDirectory(prefix="studio-office-") as tmp:
        profile = Path(tmp) / "profile"
        command = [
            binary,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            tmp,
            str(source.resolve()),
        ]
        import time

        with subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ) as proc:
            deadline = time.monotonic() + TIMEOUT
            while proc.poll() is None:
                if cancel.wait(0.15) or time.monotonic() > deadline:
                    proc.kill()
                    proc.wait()
                    if cancel.is_set():
                        raise Cancelled("Job cancelled.")
                    raise ValueError("Word conversion timed out.")
            result = Path(tmp) / (source.stem + ".pdf")
            if proc.returncode or not result.exists():
                raise ValueError("LibreOffice could not render this Word document.")
            with fitz.open(result) as check:
                if not len(check):
                    raise ValueError("Word conversion produced no pages.")
            shutil.copyfile(result, destination)


def pdf_to_word(source, destination, mode, cancel, progress):
    out = Document()
    warnings = [
        "PDF-to-Word reconstruction is approximate. Review reading order, tables, fonts, and page breaks."
    ]
    with fitz.open(source) as pdf:
        for n, page in enumerate(pdf):
            checkpoint(cancel)
            section = out.sections[0] if n == 0 else out.add_section()
            section.page_width = Pt(page.rect.width)
            section.page_height = Pt(page.rect.height)
            section.left_margin = section.right_margin = Pt(24)
            section.top_margin = section.bottom_margin = Pt(24)
            tables = page.find_tables().tables
            table_boxes = []
            for found in tables:
                values = found.extract()
                if not values or not values[0]:
                    continue
                table = out.add_table(
                    rows=len(values), cols=max(len(row) for row in values)
                )
                table.style = "Table Grid"
                for row_n, row in enumerate(values):
                    for col_n, value in enumerate(row):
                        table.cell(row_n, col_n).text = value or ""
                table_boxes.append(fitz.Rect(found.bbox))
            blocks = page.get_text("dict", sort=True)["blocks"]
            for block in blocks:
                if block["type"] == 1:
                    try:
                        out.add_picture(
                            io.BytesIO(block["image"]),
                            width=Pt(min(block["width"], page.rect.width - 48)),
                        )
                    except (ValueError, KeyError):
                        warnings.append(
                            f"Image on page {n + 1} could not be reconstructed."
                        )
                    continue
                for line in block.get("lines", []):
                    if any(
                        box.contains(fitz.Rect(line["bbox"])) for box in table_boxes
                    ):
                        continue
                    para = out.add_paragraph()
                    if mode == "layout":
                        para.paragraph_format.left_indent = Pt(
                            max(0, line["bbox"][0] - 24)
                        )
                        para.paragraph_format.space_after = Pt(0)
                    for span in line["spans"]:
                        run = para.add_run(span["text"])
                        run.font.size = Pt(span["size"])
                        run.bold = bool(span["flags"] & 16)
                        run.italic = bool(span["flags"] & 2)
                        from docx.shared import RGBColor

                        run.font.color.rgb = RGBColor.from_string(
                            f"{span['color']:06x}"
                        )
                        if any("\u0600" <= c <= "\u06ff" for c in span["text"]):
                            from docx.oxml import OxmlElement

                            bidi = OxmlElement("w:bidi")
                            para._p.get_or_add_pPr().append(bidi)
            if not page.get_text().strip():
                warnings.append(
                    f"Page {n + 1} has no native text. Run OCR before converting."
                )
            progress((n + 1) / len(pdf))
    out.save(destination)
    return list(dict.fromkeys(warnings))


def ocr_pdf(source, destination, language, cancel, progress):
    """Add invisible Unicode words without rasterizing/replacing original pages.

    TSV requires only traineddata, not Tesseract's optional configs/pdf file.
    OCR image regions even when a scanned page also contains a native footer.
    """
    configure_ocr(language)
    font_path = Path(__file__).resolve().parents[1] / "fonts" / "DejaVuSans.ttf"
    font = fitz.Font(fontfile=str(font_path))
    review = []
    with fitz.open(source) as result:
        for n, page in enumerate(result):
            checkpoint(cancel)
            native_words = page.get_text("words")
            if native_words and not page.get_image_info():
                progress((n + 1) / len(result))
                continue

            def recognize(rotation):
                original_rotation = page.rotation
                try:
                    page.set_rotation(rotation)
                    rendered = fitz.Rect(page.rect)
                    inverse = fitz.Matrix(page.derotation_matrix)
                    scale = min(
                        300 / 72,
                        (MAX_PIXELS / (rendered.width * rendered.height)) ** 0.5,
                    )
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                finally:
                    page.set_rotation(original_rotation)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    data = pytesseract.image_to_data(
                        image,
                        lang=language,
                        output_type=pytesseract.Output.DICT,
                        timeout=TIMEOUT,
                    )
                except pytesseract.TesseractNotFoundError:
                    raise ValueError(
                        "Tesseract could not be started. Rerun Windows setup with OCR tools enabled."
                    ) from None
                except pytesseract.TesseractError:
                    raise ValueError(
                        "Tesseract could not read its language data. Run Install-OCR-Languages.cmd and refresh OCR status."
                    ) from None
                scores = [
                    float(c)
                    for c, t in zip(data["conf"], data["text"])
                    if t.strip() and float(c) >= 0
                ]
                confidence = sum(scores) / len(scores) if scores else 0
                return data, rendered, inverse, rotation, image.size, confidence

            # Scan streams are often upright with rotation stored as metadata;
            # other files need that metadata to compensate a sideways image.
            # Try the alternate interpretation only when recognition is weak.
            recognized = recognize(0)
            if page.rotation and recognized[-1] < 85:
                checkpoint(cancel)
                alternate = recognize(page.rotation)
                if alternate[-1] > recognized[-1]:
                    recognized = alternate
            data, rendered, inverse, ocr_rotation, image_size, _ = recognized
            checkpoint(cancel)
            confidences, words = [], []
            native_rects = [fitz.Rect(word[:4]) for word in native_words]
            sx, sy = rendered.width / image_size[0], rendered.height / image_size[1]
            for i, text in enumerate(data["text"]):
                text = text.strip()
                if not text or float(data["conf"][i]) < 0:
                    continue
                display = fitz.Rect(
                    data["left"][i] * sx,
                    data["top"][i] * sy,
                    (data["left"][i] + data["width"][i]) * sx,
                    (data["top"][i] + data["height"][i]) * sy,
                )
                box = display * inverse
                # Do not duplicate native text or invisible OCR layers.
                if any(
                    (box & existing).get_area() >= box.get_area() * 0.4
                    for existing in native_rects
                ):
                    continue
                # Stretch the invisible glyph advance to the detected word box.
                # A uniform fit made dates selectable only over their left half.
                size = display.height / (font.ascender - font.descender)
                stretch = display.width / max(
                    font.text_length(text, fontsize=size), 0.01
                )
                if size <= 0:
                    continue
                baseline = (
                    fitz.Point(display.x0, display.y0 + size * font.ascender) * inverse
                )
                page.insert_text(
                    baseline,
                    text,
                    fontname="StudioOCR",
                    fontfile=str(font_path),
                    fontsize=size,
                    rotate=ocr_rotation,
                    render_mode=3,
                    morph=(
                        baseline,
                        fitz.Matrix(1, stretch)
                        if ocr_rotation % 180
                        else fitz.Matrix(stretch, 1),
                    ),
                    overlay=True,
                )
                words.append(text)
                confidences.append(float(data["conf"][i]))
            review.append(
                {
                    "page": n + 1,
                    "confidence": round(sum(confidences) / len(confidences), 1)
                    if confidences
                    else 0,
                    "text": " ".join(words),
                    "words_added": len(words),
                }
            )
            progress((n + 1) / len(result))
        result.save(destination, garbage=4, deflate=True)
    return review


def recognize_region(source, page_index, rect, language, dpi, mode, cancel):
    configure_ocr(language)
    checkpoint(cancel)
    with fitz.open(source) as pdf:
        if not 0 <= page_index < len(pdf):
            raise ValueError("Selected page is no longer available.")
        page = pdf[page_index]
        region = fitz.Rect(rect)
        if (
            region.is_empty
            or region.is_infinite
            or not (page.rect * page.derotation_matrix).contains(region)
        ):
            raise ValueError("Select a valid text region inside the page.")
        clip = region * page.rotation_matrix
        scale = dpi / 72
        if (clip.width * scale + 2) * (clip.height * scale + 2) > MAX_PIXELS:
            raise ValueError(
                "Selected region is too large at this resolution. Reduce DPI or select a smaller field."
            )
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        image = ImageOps.autocontrast(
            ImageOps.grayscale(Image.open(io.BytesIO(pix.tobytes("png"))))
        )
    config = "--psm 7" if mode in ("line", "numbers") else "--psm 6"
    if mode == "numbers":
        config += " -c tessedit_char_whitelist=0123456789/.-"
    data = pytesseract.image_to_data(
        image,
        lang=language,
        config=config,
        output_type=pytesseract.Output.DICT,
        timeout=TIMEOUT,
    )
    checkpoint(cancel)
    lines = {}
    scores = []
    for i, text in enumerate(data["text"]):
        if not text.strip() or float(data["conf"][i]) < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(text.strip())
        scores.append(float(data["conf"][i]))
    text = "\n".join(" ".join(words) for words in lines.values())
    return {
        "text": text,
        "confidence": round(sum(scores) / len(scores), 1) if scores else 0,
        "rect": list(region),
        "page_index": page_index,
        "dpi": dpi,
        "warning": "OCR is a suggestion. Check the original image and correct the text before applying.",
    }
