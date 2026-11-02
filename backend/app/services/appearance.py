"""Estimate scan ink and candidate typography; never claim a recovered font."""

import io
import statistics
import pymupdf as fitz
from PIL import Image, ImageOps, ImageChops, ImageStat


def estimate_appearance(data, rect, text):
    rgba = Image.open(io.BytesIO(data)).convert("RGBA")
    image = Image.new("RGBA", rgba.size, "white")
    image.alpha_composite(rgba)
    image = image.convert("RGB")
    image.thumbnail((900, 900))
    gray = ImageOps.grayscale(image)
    low, high = gray.getextrema()
    if high - low < 30:
        raise ValueError(
            "No clear text was found. Select a tighter field containing visible ink."
        )
    threshold = low + (high - low) * 0.55
    mask = gray.point(lambda v: 255 if v < threshold else 0)
    box = mask.getbbox()
    if not box:
        raise ValueError("No text pixels found in the selected area.")
    samples = list(image.getdata())
    ink = [p for p, m in zip(samples, mask.getdata()) if m]
    paper = [p for p, m in zip(samples, mask.getdata()) if not m]

    def color(values):
        return "#" + "".join(
            f"{int(statistics.median(p[c] for p in values)):02x}" for c in range(3)
        )

    point_height = (box[3] - box[1]) * (rect[3] - rect[1]) / image.height
    target = mask.crop(box).resize((240, 60))
    scores = []
    if text.strip() and "\n" not in text and all(ord(c) < 256 for c in text):
        for family in ("helv", "tiro", "cour"):
            font = fitz.Font(fontname=family)
            with fitz.open() as doc:
                page = doc.new_page(
                    width=max(100, font.text_length(text, fontsize=40) + 8), height=80
                )
                page.insert_text((4, 50), text, fontname=family, fontsize=40)
                pix = page.get_pixmap(alpha=False)
                glyphs = ImageOps.grayscale(
                    Image.open(io.BytesIO(pix.tobytes("png")))
                ).point(lambda v: 255 if v < 150 else 0)
                glyph_box = glyphs.getbbox()
                if glyph_box:
                    score = ImageStat.Stat(
                        ImageChops.difference(
                            target, glyphs.crop(glyph_box).resize((240, 60))
                        )
                    ).mean[0]
                    scores.append(
                        (
                            score,
                            family,
                            max(
                                font.glyph_bbox(ord(c)).height
                                for c in text
                                if not c.isspace()
                            ),
                        )
                    )
    _, family, capital = min(scores) if scores else (0, "helv", 0.729)
    return {
        "font": family,
        "font_size": round(max(4, min(300, point_height / max(capital, 0.4))), 1),
        "color": color(ink),
        "background_color": color(paper) if paper else "#ffffff",
        "ink_rect": [
            rect[0] + box[0] * (rect[2] - rect[0]) / image.width,
            rect[1] + box[1] * (rect[3] - rect[1]) / image.height,
            rect[0] + box[2] * (rect[2] - rect[0]) / image.width,
            rect[1] + box[3] * (rect[3] - rect[1]) / image.height,
        ],
        "estimated": True,
        "warning": "Estimated from scan pixels and available font candidates. The original font cannot be identified exactly; compare before exporting.",
    }
