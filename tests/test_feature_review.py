"""Regression coverage for each shipped PDF operation and real output artifacts."""

import io
import json
import time
import unicodedata
import zipfile
from pathlib import Path
from threading import Event
import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont
from test_documents import (
    client,
    workspace,
    upload,
    op,
    exported,
    objects,
    pdf_bytes,
    wait_job,
)
from backend.app.services import runtime, conversion

FONT = Path(__file__).resolve().parents[1] / "backend/app/fonts/DejaVuSans.ttf"


def scanned_pdf(native_footer=False, rotation=0, arabic=False):
    im = Image.new("RGB", (1400, 900), "white")
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(FONT), 70)
    draw.text((100, 180), "SEARCHABLE DOCUMENT", font=font, fill="black")
    if arabic:
        draw.text((300, 400), "مرحبا بالعالم", font=font, fill="black", direction="rtl")
    data = io.BytesIO()
    im.save(data, format="PNG")
    with fitz.open() as pdf:
        p = pdf.new_page(width=700, height=450)
        p.insert_image(p.rect, stream=data.getvalue())
        if native_footer:
            p.insert_text((50, 420), "Native footer preserved", fontsize=12)
        a = p.add_text_annot((600, 30), "Keep original annotation")
        a.update()
        p.set_rotation(rotation)
        pdf.set_metadata({"title": "Keep OCR metadata"})
        return pdf.tobytes()


def perform_job(client, d, kind, **args):
    r = client.post(f"/api/documents/{d['id']}/jobs", json={"kind": kind, **args})
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json())
    assert job["status"] == "done", job
    r = client.get(f"/api/jobs/{job['id']}/download")
    assert r.status_code == 200, r.text
    return r.content, job


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_ocr_preserves_pixels_annotations_and_recognizes_scan_with_native_footer(
    client, rotation
):
    source = scanned_pdf(native_footer=True, rotation=rotation)
    d = upload(client, source)
    data, job = perform_job(client, d, "ocr", language="eng")
    with (
        fitz.open(stream=source, filetype="pdf") as original,
        fitz.open(stream=data, filetype="pdf") as result,
    ):
        assert "SEARCHABLE" in result[0].get_text(), result[0].get_text()
        assert result[0].get_text().count("Native footer preserved") == 1
        assert result[0].rotation == rotation
        assert result[0].get_pixmap().samples == original[0].get_pixmap().samples
        assert len(list(result[0].annots())) == 1
        assert result.metadata["title"] == "Keep OCR metadata"
    assert job["review"][0]["words_added"] >= 2


def test_real_bilingual_ocr_and_native_page_passthrough(client):
    source = scanned_pdf(arabic=True)
    with fitz.open(stream=source, filetype="pdf") as pdf:
        p = pdf.new_page()
        p.insert_text((72, 90), "Native page untouched")
        source = pdf.tobytes()
    d = upload(client, source)
    data, job = perform_job(client, d, "ocr", language="eng+ara")
    with fitz.open(stream=data, filetype="pdf") as out:
        text = out[0].get_text()
        assert "SEARCHABLE" in text
        assert any("\u0600" <= c <= "\u06ff" for c in text), text
        assert out[1].get_text().count("Native page untouched") == 1
    assert len(job["review"]) == 1


def test_missing_language_identified_precisely_and_refresh_not_cached(
    client, tmp_path, monkeypatch
):
    original_directory = Path(client.get("/api/health").json()["ocr"]["data_directory"])
    data_dir = tmp_path / "OCR packs with spaces"
    data_dir.mkdir()
    # Prefer an explicit, isolated empty directory over system packs.
    monkeypatch.setenv("STUDIO_TESSDATA_DIR", str(data_dir))
    status = client.get("/api/health").json()
    assert not status["ocr_languages"]
    assert status["ocr"]["error"]
    # Actual recognition must not require configs/pdf, only traineddata.
    source = original_directory / "eng.traineddata"
    (data_dir / "eng.traineddata").write_bytes(source.read_bytes())
    status = client.get("/api/health").json()
    assert status["ocr_languages"] == ["eng"]
    with pytest.raises(ValueError, match="ara") as exc:
        runtime.configure_ocr("eng+ara")
    assert "eng," not in str(exc.value)
    d = upload(client, scanned_pdf())
    data, _ = perform_job(client, d, "ocr", language="eng")
    with fitz.open(stream=data, filetype="pdf") as pdf:
        assert "SEARCHABLE" in pdf[0].get_text()


def test_missing_tesseract_executable_is_actionable(client, monkeypatch):
    monkeypatch.setenv("STUDIO_TESSERACT_CMD", "/no/such/tesseract.exe")
    status = client.get("/api/health").json()
    assert not status["ocr"]["available"]
    assert "Tesseract" in status["ocr"]["error"]
    d = upload(client, scanned_pdf())
    j = client.post(f"/api/documents/{d['id']}/jobs", json={"kind": "ocr"}).json()
    result = wait_job(client, j)
    assert result["status"] == "failed"
    assert "Tesseract" in result["error"]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_signature_region_png_matches_render_on_cropped_rotated_page(client, rotation):
    with fitz.open() as pdf:
        p = pdf.new_page(width=500, height=600)
        p.draw_rect(p.rect, color=None, fill=(1, 1, 1))
        p.draw_polyline(
            [(120, 270), (150, 310), (180, 270), (240, 300)], color=(0, 0, 0), width=3
        )
        p.insert_text((40, 80), "Unrelated private heading")
        p.set_cropbox(fitz.Rect(20, 30, 480, 570))
        p.set_rotation(rotation)
        source = pdf.tobytes()
    d = upload(client, source)
    region = [90, 220, 250, 300]
    endpoint = f"/api/documents/{d['id']}/pages/{d['pages'][0]['id']}/region-png"
    response = client.post(endpoint, json={"revision": 0, "rect": region, "dpi": 144})
    assert response.status_code == 200, response.text
    image = Image.open(io.BytesIO(response.content)).convert("RGBA")
    with fitz.open(stream=source, filetype="pdf") as pdf:
        p = pdf[0]
        expected = p.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            clip=fitz.Rect(region) * p.rotation_matrix,
            alpha=True,
        )
        assert (
            image.tobytes()
            == Image.open(io.BytesIO(expected.tobytes("png"))).convert("RGBA").tobytes()
        )
    assert any(
        r < 100 and g < 100 and b < 100 and a > 0 for r, g, b, a in image.getdata()
    )
    transparent = client.post(
        endpoint, json={"revision": 0, "rect": region, "dpi": 144, "remove_white": True}
    )
    rgba = Image.open(io.BytesIO(transparent.content)).convert("RGBA")
    assert rgba.getchannel("A").getextrema() == (0, 255)
    assert client.get(f"/api/documents/{d['id']}").json()["revision"] == 0
    assert (
        client.post(
            endpoint, json={"revision": 0, "rect": [-20, 0, 80, 80]}
        ).status_code
        == 422
    )
    assert (
        client.post(endpoint, json={"revision": 1, "rect": region}).status_code == 409
    )


def signature_image():
    image = Image.new("RGBA", (160, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line(
        [(20, 40), (40, 20), (70, 60), (130, 30)], fill=(10, 20, 30, 255), width=5
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_embedded_signature_png_and_zip_preserve_alpha_and_resolution(client):
    d = upload(client)
    image = signature_image()
    asset = client.post(
        f"/api/documents/{d['id']}/assets", files={"file": ("sig.png", image)}
    ).json()
    d = op(
        client,
        d,
        {
            "kind": "image",
            "page_id": d["pages"][0]["id"],
            "rect": [72, 250, 232, 330],
            "asset_id": asset["id"],
        },
    )
    xref = objects(client, d)["images"][0]["xref"]
    r = client.get(
        f"/api/documents/{d['id']}/pages/{d['pages'][0]['id']}/images/{xref}"
    )
    assert r.status_code == 200
    png = Image.open(io.BytesIO(r.content)).convert("RGBA")
    assert png.size == (160, 80)
    assert png.getchannel("A").getextrema() == (0, 255)
    original = Image.open(io.BytesIO(image)).convert("RGBA")
    # Color values under fully transparent pixels are unspecified; visible ink must match.
    assert png.getpixel((40, 20)) == original.getpixel((40, 20))
    response = client.get(f"/api/documents/{d['id']}/images")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        extracted = Image.open(io.BytesIO(archive.read(archive.namelist()[0]))).convert(
            "RGBA"
        )
        assert extracted.getchannel("A").getextrema() == (0, 255)


def test_signature_assets_crop_empty_margins_and_reject_blank(client):
    d = upload(client)
    r = client.post(
        f"/api/documents/{d['id']}/assets",
        data={"signature": "true"},
        files={"file": ("sig.png", signature_image())},
    )
    assert r.status_code == 200
    assert r.json()["width"] < 160
    assert r.json()["height"] < 80
    blank = Image.new("RGBA", (30, 30))
    b = io.BytesIO()
    blank.save(b, format="PNG")
    assert (
        client.post(
            f"/api/documents/{d['id']}/assets",
            data={"signature": "true"},
            files={"file": ("blank.png", b.getvalue())},
        ).status_code
        == 422
    )


def test_signature_is_visible_even_with_inherited_background_and_opacity(client):
    with fitz.open() as pdf:
        p = pdf.new_page()
        p.draw_rect(p.rect, fill=(1, 1, 1), color=None)
        source = pdf.tobytes()
    d = upload(client, source)
    image = Image.new("RGB", (30, 30), "red")
    b = io.BytesIO()
    image.save(b, format="PNG")
    a = client.post(
        f"/api/documents/{d['id']}/assets", files={"file": ("sig.png", b.getvalue())}
    ).json()
    d = op(
        client,
        d,
        {
            "kind": "image",
            "page_id": d["pages"][0]["id"],
            "rect": [72, 72, 102, 102],
            "asset_id": a["id"],
            "signature": True,
            "behind": True,
            "opacity": 0,
        },
    )
    with exported(client, d) as out:
        assert out[0].get_pixmap().pixel(80, 80) == (255, 0, 0)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_typed_signature_on_rotated_page_persists(client, rotation):
    d = upload(client, pdf_bytes(1))
    pid = d["pages"][0]["id"]
    d = op(client, d, {"kind": "rotate", "page_ids": [pid], "angle": rotation})
    d = op(
        client,
        d,
        {
            "kind": "text",
            "page_id": pid,
            "rect": [100, 200, 300, 400],
            "text": "My Signature",
            "italic": True,
            "font": "tiro",
            "font_size": 20,
            "angle": rotation,
        },
    )
    with exported(client, d) as out:
        assert "My Signature" in out[0].get_text()


def test_read_tools_reject_docx_without_internal_errors(client):
    from docx import Document

    doc = Document()
    doc.add_paragraph("Word")
    stream = io.BytesIO()
    doc.save(stream)
    d = upload(client, stream.getvalue(), "sample.docx")
    assert client.post(f"/api/documents/{d['id']}/export", json={}).status_code == 422
    assert client.get(f"/api/documents/{d['id']}/images").status_code == 422
    assert client.get(f"/api/documents/{d['id']}/search?q=Word").status_code == 422


def test_text_height_overflow_and_missing_image_are_atomic(client):
    d = upload(client)
    span = objects(client, d)["spans"][0]
    op(
        client,
        d,
        {
            "kind": "replace_text",
            "page_id": d["pages"][0]["id"],
            "rect": span["rect"],
            "original": span["text"],
            "text": "A",
            "font_size": 100,
            "fit_text": False,
        },
        422,
    )
    asset = client.post(
        f"/api/documents/{d['id']}/assets",
        files={"file": ("sig.png", signature_image())},
    ).json()
    d = op(
        client,
        d,
        {
            "kind": "image",
            "page_id": d["pages"][0]["id"],
            "rect": [72, 250, 232, 330],
            "asset_id": asset["id"],
        },
    )
    xref = objects(client, d)["images"][0]["xref"]
    op(
        client,
        d,
        {
            "kind": "replace_image",
            "page_id": d["pages"][0]["id"],
            "xref": xref,
            "asset_id": "a" * 32,
        },
        404,
    )
    with exported(client, d) as out:
        assert "original secret" in out[0].get_text()


def test_utilities_watermark_numbers_compression_and_repeated_crop(client):
    d = upload(client, pdf_bytes(2))
    d = op(
        client,
        d,
        {
            "kind": "watermark",
            "text": "PRIVATE",
            "font_size": 12,
            "color": "#aa1111",
            "opacity": 0.5,
        },
    )
    d = op(client, d, {"kind": "numbers", "font_size": 10})
    d = op(
        client,
        d,
        {
            "kind": "metadata",
            "metadata": {
                "title": "عنوان",
                "author": "A User",
                "subject": "Review",
                "keywords": "test",
            },
        },
    )
    with exported(client, d) as before:
        pixels = [p.get_pixmap().samples for p in before]
        assert "PRIVATE" in before[0].get_text()
        assert "2" in before[1].get_text()
    d = op(client, d, {"kind": "compress"})
    with exported(client, d) as out:
        assert out.metadata["title"] == "عنوان"
        assert [p.get_pixmap().samples for p in out] == pixels
    pid = d["pages"][0]["id"]
    d = op(client, d, {"kind": "crop", "page_id": pid, "rect": [20, 20, 590, 770]})
    d = op(client, d, {"kind": "crop", "page_id": pid, "rect": [10, 10, 500, 700]})
    assert d["pages"][0]["width"] == 490
    assert d["pages"][0]["height"] == 690


def test_annotation_pages_survive_reorder_duplicate_and_export(client):
    d = upload(client, pdf_bytes(2))
    pid = d["pages"][0]["id"]
    d = op(
        client,
        d,
        {
            "kind": "annotation",
            "page_id": pid,
            "rect": [100, 200, 200, 260],
            "annotation": "text",
            "text": "Keep note",
        },
    )
    d = op(
        client, d, {"kind": "reorder", "page_ids": [p["id"] for p in d["pages"]][::-1]}
    )
    d = op(client, d, {"kind": "duplicate", "page_ids": [pid]})
    with exported(client, d) as out:
        assert len(out) == 3
        assert len(list(out[1].annots())) == 1
        assert len(list(out[2].annots())) == 1


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_supported_image_formats_replace_and_delete(client, format):
    d = upload(client, pdf_bytes(1))
    image = Image.new("RGB", (60, 40), "red")
    stream = io.BytesIO()
    image.save(stream, format=format)
    a = client.post(
        f"/api/documents/{d['id']}/assets",
        files={"file": ("source." + format.lower(), stream.getvalue())},
    )
    assert a.status_code == 200
    d = op(
        client,
        d,
        {
            "kind": "image",
            "page_id": d["pages"][0]["id"],
            "asset_id": a.json()["id"],
            "rect": [72, 250, 192, 330],
        },
    )
    xref = objects(client, d)["images"][0]["xref"]
    image = Image.new("RGB", (60, 40), "blue")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    replacement = client.post(
        f"/api/documents/{d['id']}/assets",
        files={"file": ("new.png", stream.getvalue())},
    ).json()
    d = op(
        client,
        d,
        {
            "kind": "replace_image",
            "page_id": d["pages"][0]["id"],
            "xref": xref,
            "asset_id": replacement["id"],
        },
    )
    with exported(client, d) as out:
        assert out[0].get_pixmap().pixel(100, 280) == (0, 0, 255)
    d = op(
        client,
        d,
        {"kind": "delete_image", "page_id": d["pages"][0]["id"], "xref": xref},
    )
    with exported(client, d) as out:
        assert out[0].get_pixmap().pixel(100, 280) == (255, 255, 255)


def test_shared_image_transform_is_rejected_without_losing_any_use(client):
    d = upload(client, pdf_bytes(1))
    a = client.post(
        f"/api/documents/{d['id']}/assets",
        files={"file": ("sig.png", signature_image())},
    ).json()
    for y in [250, 400]:
        d = op(
            client,
            d,
            {
                "kind": "image",
                "page_id": d["pages"][0]["id"],
                "asset_id": a["id"],
                "rect": [72, y, 232, y + 80],
            },
        )
    image = objects(client, d)["images"][0]
    op(
        client,
        d,
        {
            "kind": "transform_image",
            "page_id": d["pages"][0]["id"],
            "xref": image["xref"],
            "rect": [100, 100, 260, 180],
        },
        422,
    )
    assert len(objects(client, d)["images"]) == 2


def test_unicode_watermarks_and_numbers_on_rotated_pages(client):
    d = upload(client, pdf_bytes(2))
    d = op(
        client, d, {"kind": "rotate", "page_ids": [d["pages"][1]["id"]], "angle": 90}
    )
    d = op(client, d, {"kind": "watermark", "text": "سري", "font_size": 14})
    d = op(client, d, {"kind": "numbers", "font_size": 10})
    with exported(client, d) as out:
        assert all("سري" in unicodedata.normalize("NFKC", p.get_text()) for p in out)
        assert "2" in out[1].get_text()


def test_upload_validation_limits_history_branch_and_signed_warning(
    client, monkeypatch
):
    import backend.app.main as main
    from docx import Document

    monkeypatch.setattr(main, "MAX_BYTES", 10)
    assert (
        client.post(
            "/api/documents", files={"file": ("large.pdf", pdf_bytes(1))}
        ).status_code
        == 413
    )
    monkeypatch.setattr(main, "MAX_BYTES", 200 * 1024 * 1024)
    assert (
        client.post("/api/documents", files={"file": ("empty.pdf", b"")}).status_code
        == 415
    )
    assert (
        client.post(
            "/api/documents", files={"file": ("bad.pdf", b"%PDF-1.7\ninvalid")}
        ).status_code
        == 422
    )
    with fitz.open() as pdf:
        page = pdf.new_page()
        widget = fitz.Widget()
        widget.field_name = "Existing signature"
        widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
        widget.rect = fitz.Rect(50, 50, 200, 100)
        page.add_widget(widget)
        source = pdf.tobytes()
    d = upload(client, source)
    assert any("signature" in w.lower() for w in d["warnings"])
    d = op(client, d, {"kind": "blank"})
    d = client.post(
        f"/api/documents/{d['id']}/history",
        json={"revision": d["revision"], "direction": "undo"},
    ).json()
    d = op(client, d, {"kind": "numbers"})
    assert not d["can_redo"]
    doc = Document()
    b = io.BytesIO()
    doc.save(b)
    word = upload(client, b.getvalue(), "source.docx")
    op(client, d, {"kind": "insert", "source_id": word["id"]}, 422)


def test_line_direction_is_preserved(client):
    d = upload(client, pdf_bytes(1))
    d = op(
        client,
        d,
        {
            "kind": "annotation",
            "page_id": d["pages"][0]["id"],
            "rect": [99, 199, 261, 241],
            "annotation": "arrow",
            "points": [[260, 240], [100, 200]],
        },
    )
    with exported(client, d) as out:
        page = out[0]
        vertices = next(page.annots()).vertices
        assert vertices[0] == (260, 240)
        assert vertices[-1] == (100, 200)


@pytest.mark.parametrize("source_kind", ["scan", "annotation"])
def test_signature_region_export_from_scan_and_ink_annotation(client, source_kind):
    with fitz.open() as pdf:
        page = pdf.new_page(width=400, height=400)
        page.draw_rect(page.rect, color=None, fill=(1, 1, 1))
        points = [(120, 150), (150, 120), (180, 180)]
        if source_kind == "scan":
            image = Image.new("RGB", (400, 400), "white")
            ImageDraw.Draw(image).line(points, fill="black", width=4)
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            page.insert_image(page.rect, stream=stream.getvalue())
        else:
            annot = page.add_ink_annot([points])
            annot.set_colors(stroke=(0, 0, 0))
            annot.set_border(width=3)
            annot.update()
        source = pdf.tobytes()
    d = upload(client, source)
    response = client.post(
        f"/api/documents/{d['id']}/pages/{d['pages'][0]['id']}/region-png",
        json={
            "revision": 0,
            "rect": [100, 100, 200, 200],
            "dpi": 144,
            "remove_white": True,
        },
    )
    assert response.status_code == 200, response.text
    image = Image.open(io.BytesIO(response.content)).convert("RGBA")
    assert image.size == (200, 200)
    assert image.getchannel("A").getextrema() == (0, 255)
    assert (
        sum(1 for r, g, b, a in image.getdata() if max(r, g, b) < 100 and a > 0) > 100
    )
    assert client.get(f"/api/documents/{d['id']}").json()["revision"] == 0
