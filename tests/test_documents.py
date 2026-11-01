import io
import time
import zipfile
from pathlib import Path
import pytest
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from backend.app import core
from backend.app.main import app


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "ROOT", tmp_path)
    import backend.app.main as main

    monkeypatch.setattr(main, "ROOT", tmp_path)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def pdf_bytes(count=10):
    with fitz.open() as d:
        for i in range(count):
            p = d.new_page(width=612, height=792)
            p.insert_text((72, 90), f"Page {i + 1} original secret", fontsize=16)
            p.insert_text((72, 180), "Unrelated content must survive", fontsize=12)
            p.draw_rect(
                fitz.Rect(300, 300, 500, 500), color=(0, 0.5, 0.2), fill=(0.8, 0.9, 0.8)
            )
        return d.tobytes()


def upload(c, data=None, name="sample.pdf", password=""):
    r = c.post(
        "/api/documents",
        files={"file": (name, data or pdf_bytes(), "application/pdf")},
        data={"password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()


def op(c, d, operation, status=200):
    r = c.post(
        f"/api/documents/{d['id']}/operations",
        json={"revision": d["revision"], "operation": operation},
    )
    assert r.status_code == status, r.text
    return r.json()


def exported(c, d, **args):
    r = c.post(f"/api/documents/{d['id']}/export", json=args)
    assert r.status_code == 200, r.text
    return fitz.open(stream=r.content, filetype="pdf")


def objects(c, d, page=0):
    return c.get(
        f"/api/documents/{d['id']}/pages/{d['pages'][page]['id']}/objects"
    ).json()


def wait_job(c, j):
    for _ in range(200):
        result = c.get(f"/api/jobs/{j['id']}").json()
        if result["status"] not in ("queued", "running"):
            return result
        time.sleep(0.1)
    pytest.fail("Job did not finish")


def test_upload_ten_pages_and_render(client):
    d = upload(client)
    assert len(d["pages"]) == 10
    r = client.get(f"/api/documents/{d['id']}/pages/{d['pages'][0]['id']}/render")
    assert r.status_code == 200
    assert Image.open(io.BytesIO(r.content)).size == (612, 792)


def test_true_replacement_removes_secret_and_preserves_pixels(client):
    source = pdf_bytes()
    d = upload(client, source)
    span = objects(client, d, 2)["spans"][0]
    result = op(
        client,
        d,
        {
            "kind": "replace_text",
            "page_id": d["pages"][2]["id"],
            "rect": span["rect"],
            "original": span["text"],
            "text": "Changed",
            "font_size": 16,
        },
    )
    with (
        exported(client, result) as output,
        fitz.open(stream=source, filetype="pdf") as original,
    ):
        assert "Changed" in output[2].get_text()
        assert "original secret" not in output[2].get_text()
        assert "Unrelated content" in output[2].get_text()
        for i in (0, 1, 3, 9):
            assert original[i].get_pixmap().samples == output[i].get_pixmap().samples
        # Everything below the changed line remains byte-identical in raster space.
        clip = fitz.Rect(0, 120, 612, 792)
        assert (
            original[2].get_pixmap(clip=clip).samples
            == output[2].get_pixmap(clip=clip).samples
        )
        streams = b"".join(
            output.xref_stream(i) or b""
            for i in range(1, output.xref_length())
            if output.xref_is_stream(i)
        )
        assert b"original secret" not in streams


def test_failed_edit_is_atomic_and_stale_revision_rejected(client):
    d = upload(client)
    s = objects(client, d)["spans"][0]
    op(
        client,
        d,
        {
            "kind": "replace_text",
            "page_id": d["pages"][0]["id"],
            "rect": s["rect"],
            "original": s["text"],
            "text": "too long " * 100,
            "font_size": 16,
        },
        422,
    )
    assert client.get(f"/api/documents/{d['id']}").json()["revision"] == 0
    with exported(client, d) as out:
        assert "original secret" in out[0].get_text()
    op(client, d, {"kind": "blank"})
    op(client, d, {"kind": "blank"}, 409)


def test_page_operations_history_and_merge_three(client):
    d = upload(client)
    original_ids = [p["id"] for p in d["pages"]]
    d = op(
        client,
        d,
        {"kind": "delete_pages", "page_ids": [original_ids[1], original_ids[4]]},
    )
    assert len(d["pages"]) == 8
    d = op(
        client, d, {"kind": "reorder", "page_ids": [p["id"] for p in d["pages"]][::-1]}
    )
    with exported(client, d) as out:
        assert "Page 10" in out[0].get_text()
        assert "Page 1 " in out[7].get_text()
    r = client.post(
        f"/api/documents/{d['id']}/history",
        json={"revision": d["revision"], "direction": "undo"},
    )
    d = r.json()
    assert d["pages"][0]["id"] == original_ids[0]
    d = client.post(
        f"/api/documents/{d['id']}/history",
        json={"revision": d["revision"], "direction": "redo"},
    ).json()
    assert d["pages"][0]["id"] == original_ids[-1]
    for _ in range(2):
        other = upload(client, pdf_bytes(2))
        d = op(client, d, {"kind": "insert", "source_id": other["id"]})
    with exported(client, d) as out:
        assert len(out) == 12
    d = op(client, d, {"kind": "duplicate", "page_ids": [d["pages"][0]["id"]]})
    assert len(d["pages"]) == 13
    d = op(
        client, d, {"kind": "rotate", "page_ids": [d["pages"][0]["id"]], "angle": 90}
    )
    assert d["pages"][0]["rotation"] == 90
    d = op(client, d, {"kind": "blank", "page_id": d["pages"][0]["id"]})
    with exported(client, d, page_ids=[d["pages"][0]["id"]]) as out:
        assert len(out) == 1


def test_images_signatures_and_annotations(client):
    d = upload(client)
    im = Image.new("RGBA", (80, 30), (255, 0, 0, 180))
    b = io.BytesIO()
    im.save(b, format="PNG")
    a = client.post(
        f"/api/documents/{d['id']}/assets",
        files={"file": ("signature.png", b.getvalue(), "image/png")},
    ).json()
    d = op(
        client,
        d,
        {
            "kind": "image",
            "page_id": d["pages"][0]["id"],
            "rect": [80, 220, 240, 280],
            "asset_id": a["id"],
            "angle": 0,
        },
    )
    d = op(
        client,
        d,
        {
            "kind": "annotation",
            "page_id": d["pages"][0]["id"],
            "rect": [70, 160, 300, 185],
            "annotation": "highlight",
        },
    )
    with exported(client, d) as out:
        assert len(out[0].get_images()) >= 1
        assert len(list(out[0].annots())) == 1
        assert out[0].get_pixmap().pixel(120, 240)[0] > 200
        assert out[0].get_pixmap().pixel(120, 240)[1] < 100


def test_password_and_security(client):
    d = upload(client)
    raw = client.post(
        f"/api/documents/{d['id']}/export", json={"password": "correct horse"}
    ).content
    assert (
        client.post("/api/documents", files={"file": ("a.pdf", raw)}).status_code == 401
    )
    opened = upload(client, raw, password="correct horse")
    assert len(opened["pages"]) == 10
    assert client.get("/api/documents/../../etc/passwd").status_code == 404
    assert (
        client.post(
            "/api/documents", files={"file": ("fake.pdf", b"not pdf")}
        ).status_code
        == 415
    )
    assert (
        client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
    )
    assert (
        client.post(
            "/api/documents",
            headers={"origin": "https://evil.example"},
            files={"file": ("x.pdf", pdf_bytes())},
        ).status_code
        == 403
    )


def test_unicode_arabic_and_crop(client):
    d = upload(client)
    d = op(
        client,
        d,
        {
            "kind": "text",
            "page_id": d["pages"][0]["id"],
            "rect": [70, 550, 500, 680],
            "text": "مرحبا بالعالم",
            "font_size": 22,
            "align": "right",
        },
    )
    with exported(client, d) as out:
        import unicodedata

        text = unicodedata.normalize("NFKC", out[0].get_text())
        assert "مرحبا بالعالم" in text
        assert any("\u0600" <= c <= "\u06ff" for c in text)
        assert out[0].get_pixmap().samples
    d = op(
        client,
        d,
        {"kind": "crop", "page_id": d["pages"][0]["id"], "rect": [20, 20, 590, 770]},
    )
    assert d["pages"][0]["width"] == 570


def test_100_pages_and_metadata(client):
    d = upload(client, pdf_bytes(100))
    assert len(d["pages"]) == 100
    d = op(client, d, {"kind": "metadata", "metadata": {"title": "Studio integration"}})
    with exported(client, d) as out:
        assert out.metadata["title"] == "Studio integration"
        assert len(out) == 100


def test_pdf_to_editable_docx(client):
    from docx import Document

    d = upload(client, pdf_bytes(2))
    j = client.post(
        f"/api/documents/{d['id']}/jobs", json={"kind": "docx", "mode": "editable"}
    ).json()
    result = wait_job(client, j)
    assert result["status"] == "done", result
    r = client.get(f"/api/jobs/{j['id']}/download")
    word = Document(io.BytesIO(r.content))
    assert any("Page 1" in p.text for p in word.paragraphs)
    assert any("Page 2" in p.text for p in word.paragraphs)


def test_ocr_searchable_scan(client):
    im = Image.new("RGB", (1200, 500), "white")
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(
        str(Path(__file__).resolve().parents[1] / "backend/app/fonts/DejaVuSans.ttf"),
        52,
    )
    draw.text((65, 150), "SEARCHABLE DOCUMENT", font=font, fill="black")
    b = io.BytesIO()
    im.save(b, format="PNG")
    with fitz.open() as pdf:
        p = pdf.new_page(width=600, height=250)
        p.insert_image(p.rect, stream=b.getvalue())
        data = pdf.tobytes()
    d = upload(client, data)
    j = client.post(
        f"/api/documents/{d['id']}/jobs", json={"kind": "ocr", "language": "eng"}
    ).json()
    result = wait_job(client, j)
    assert result["status"] == "done", result
    assert result["review"][0]["confidence"] > 50
    r = client.get(f"/api/jobs/{j['id']}/download")
    with fitz.open(stream=r.content, filetype="pdf") as out:
        assert "SEARCHABLE" in out[0].get_text()
        assert len(out) == 1


def test_word_conversion_or_actionable_missing_binary(client):
    from docx import Document

    word = Document()
    word.add_paragraph("Word conversion integration")
    stream = io.BytesIO()
    word.save(stream)
    d = upload(client, stream.getvalue(), "source.docx")
    j = client.post(f"/api/documents/{d['id']}/jobs", json={"kind": "word_pdf"}).json()
    result = wait_job(client, j)
    if client.get("/api/health").json()["libreoffice"]:
        assert result["status"] == "done", result
        r = client.get(f"/api/jobs/{j['id']}/download")
        with fitz.open(stream=r.content, filetype="pdf") as out:
            assert "Word conversion integration" in out[0].get_text()
    else:
        assert result["status"] == "failed"
        assert "LibreOffice" in result["error"]


def test_move_text_and_transform_image(client):
    d = upload(client)
    s = objects(client, d)["spans"][0]
    new = [72, 210, 400, 240]
    d = op(
        client,
        d,
        {
            "kind": "replace_text",
            "page_id": d["pages"][0]["id"],
            "source_rect": s["rect"],
            "rect": new,
            "original": s["text"],
            "text": "Moved text",
            "font_size": 16,
        },
    )
    with exported(client, d) as out:
        assert out[0].search_for("Moved text")[0].y0 > 200
        assert not out[0].search_for("original secret")
    im = Image.new("RGB", (80, 30), "red")
    b = io.BytesIO()
    im.save(b, format="PNG")
    a = client.post(
        f"/api/documents/{d['id']}/assets", files={"file": ("photo.png", b.getvalue())}
    ).json()
    d = op(
        client,
        d,
        {
            "kind": "image",
            "page_id": d["pages"][0]["id"],
            "rect": [80, 300, 240, 360],
            "asset_id": a["id"],
            "angle": 0,
        },
    )
    xref = objects(client, d)["images"][0]["xref"]
    d = op(
        client,
        d,
        {
            "kind": "transform_image",
            "page_id": d["pages"][0]["id"],
            "xref": xref,
            "rect": [100, 600, 260, 660],
            "angle": 0,
            "opacity": 0.5,
        },
    )
    with exported(client, d) as out:
        pix = out[0].get_pixmap()
        assert pix.pixel(120, 320) == (255, 255, 255)  # old image position removed
        assert pix.pixel(120, 620)[0] > 240
        assert 110 < pix.pixel(120, 620)[1] < 150


def test_all_annotations_and_failure_recovery(client):
    d = upload(client)
    for kind in [
        "underline",
        "strikeout",
        "text",
        "rect",
        "circle",
        "line",
        "arrow",
        "ink",
        "stamp",
    ]:
        d = op(
            client,
            d,
            {
                "kind": "annotation",
                "page_id": d["pages"][0]["id"],
                "rect": [50, 550, 200, 600],
                "annotation": kind,
                "points": [[50, 550], [100, 575], [200, 600]],
                "text": "Review note",
            },
        )
    with exported(client, d) as out:
        assert len(list(out[0].annots())) == 9
    before = client.post(f"/api/documents/{d['id']}/export", json={}).content
    assert (
        client.post(
            f"/api/documents/{d['id']}/export", json={"page_ids": ["missing"]}
        ).status_code
        == 422
    )
    after = client.post(f"/api/documents/{d['id']}/export", json={}).content
    with (
        fitz.open(stream=before, filetype="pdf") as a,
        fitz.open(stream=after, filetype="pdf") as b,
    ):
        assert a[0].get_pixmap().samples == b[0].get_pixmap().samples


def test_table_reconstruction_and_layout_mode(client):
    from docx import Document

    with fitz.open() as pdf:
        p = pdf.new_page()
        for x in [60, 200, 340]:
            p.draw_line((x, 100), (x, 180))
        for y in [100, 140, 180]:
            p.draw_line((60, y), (340, y))
        for text, x, y in [
            ("Name", 70, 125),
            ("Count", 210, 125),
            ("Apples", 70, 165),
            ("12", 210, 165),
        ]:
            p.insert_text((x, y), text)
        d = upload(client, pdf.tobytes())
    j = client.post(
        f"/api/documents/{d['id']}/jobs", json={"kind": "docx", "mode": "layout"}
    ).json()
    result = wait_job(client, j)
    assert result["status"] == "done", result
    word = Document(io.BytesIO(client.get(f"/api/jobs/{j['id']}/download").content))
    assert len(word.tables) == 1
    assert word.tables[0].cell(1, 0).text == "Apples"


def test_new_document_and_close(client):
    r = client.post("/api/new")
    assert r.status_code == 200
    d = r.json()
    assert len(d["pages"]) == 1
    assert not d["warnings"]
    assert client.delete(f"/api/documents/{d['id']}").status_code == 200
    assert client.get(f"/api/documents/{d['id']}").status_code == 404


def test_cancellation_leaves_original_intact(client):
    d = upload(client, pdf_bytes(100))
    j = client.post(f"/api/documents/{d['id']}/jobs", json={"kind": "docx"}).json()
    assert client.delete(f"/api/jobs/{j['id']}").status_code == 200
    result = wait_job(client, j)
    assert result["status"] in (
        "cancelled",
        "done",
    )  # Completion may win a cancellation race.
    with exported(client, d) as out:
        assert len(out) == 100
        assert "Page 1 " in out[0].get_text()


def test_arabic_replacement_and_font_families(client):
    import unicodedata

    d = upload(client)
    d = op(
        client,
        d,
        {
            "kind": "text",
            "page_id": d["pages"][0]["id"],
            "rect": [70, 550, 500, 680],
            "text": "مرحبا بالعالم",
            "font_size": 22,
            "align": "right",
        },
    )
    spans = objects(client, d)["spans"]
    s = next(s for s in spans if "مرحبا" in unicodedata.normalize("NFKC", s["text"]))
    d = op(
        client,
        d,
        {
            "kind": "replace_text",
            "page_id": d["pages"][0]["id"],
            "source_rect": s["rect"],
            "rect": [70, 550, 500, 680],
            "original": s["text"],
            "text": "اهلا",
            "font_size": 22,
            "align": "right",
        },
    )
    for font in ["helv", "tiro", "cour"]:
        d = op(
            client,
            d,
            {
                "kind": "text",
                "page_id": d["pages"][1]["id"],
                "rect": [70, 100, 400, 180],
                "text": "Font sample",
                "font_size": 16,
                "font": font,
                "bold": True,
                "italic": True,
            },
        )
    with exported(client, d) as out:
        assert "اهلا" in unicodedata.normalize("NFKC", out[0].get_text())
        assert "مرحبا" not in unicodedata.normalize("NFKC", out[0].get_text())
        assert len(out[1].search_for("Font sample")) > 0
