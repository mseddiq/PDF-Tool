"""Describe selectable text without confusing an invisible OCR layer with ink."""

import re
import pymupdf as fitz


def text_spans(page):
    spans = []
    reusable = {}
    image_rects = [fitz.Rect(item["bbox"]) for item in page.get_image_info()]
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            direction = line.get("dir", (1, 0))
            angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}.get(
                tuple(round(v) for v in direction), 0
            )
            for span in line["spans"]:
                hidden = span.get("alpha", 255) == 0
                if span["font"] not in reusable:
                    reusable[span["font"]] = bool(original_font(page, span["font"]))
                box = fitz.Rect(span["bbox"])
                scan = hidden and any(box.intersects(image) for image in image_rects)
                spans.append(
                    {
                        "text": span["text"],
                        "rect": list(box),
                        "font": span["font"],
                        "can_reuse_font": not hidden
                        and reusable[span["font"]]
                        and all(ord(c) <= 255 for c in span["text"]),
                        "size": span["size"],
                        "color": f"#{span['color']:06x}",
                        "flags": span["flags"],
                        "source": "ocr" if scan else "hidden" if hidden else "native",
                        "angle": angle,
                    }
                )
    return spans


def original_font(page, name):
    """Return an extractable face matching the span, never a client-supplied xref."""

    def canonical(value):
        value = re.sub(r"[^a-z0-9]", "", value.split("+", 1)[-1].lower())
        return re.sub(r"(?:book|regular)$", "", value)

    name = canonical(name)
    for entry in page.get_fonts(full=True):
        if canonical(entry[3]) == name:
            extracted = page.parent.extract_font(entry[0])
            if extracted[3]:
                return extracted[3]
    return None
