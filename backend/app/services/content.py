"""Describe selectable text without confusing an invisible OCR layer with ink."""

import pymupdf as fitz


def text_spans(page):
    spans = []
    image_rects = [fitz.Rect(item["bbox"]) for item in page.get_image_info()]
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            direction = line.get("dir", (1, 0))
            angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}.get(
                tuple(round(v) for v in direction), 0
            )
            for span in line["spans"]:
                hidden = span.get("alpha", 255) == 0
                box = fitz.Rect(span["bbox"])
                scan = hidden and any(box.intersects(image) for image in image_rects)
                spans.append(
                    {
                        "text": span["text"],
                        "rect": list(box),
                        "font": span["font"],
                        "size": span["size"],
                        "color": f"#{span['color']:06x}",
                        "flags": span["flags"],
                        "source": "ocr" if scan else "hidden" if hidden else "native",
                        "angle": angle,
                    }
                )
    return spans
