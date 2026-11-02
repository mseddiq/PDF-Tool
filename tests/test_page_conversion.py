import io
from pathlib import Path
from threading import Event
import pymupdf as fitz
import pytest
from docx import Document
from PIL import Image, ImageDraw, ImageFont
from test_documents import (
    client,
    workspace,
    upload,
    objects,
    op,
    exported,
    wait_job,
    pdf_bytes,
)
from backend.app.services.conversion import xml_text, pdf_to_word

FONT = Path(__file__).resolve().parents[1] / "backend/app/fonts/DejaVuSans.ttf"


def test_xml_controls_removed_without_losing_arabic_or_emoji():
    assert xml_text("A\x00\x01\x0b\ud800\ufffe العربية 😀\t\n") == "A العربية 😀\t\n"


def test_word_reconstruction_cleans_parser_controls_and_retains_style(
    tmp_path, monkeypatch
):
    source = tmp_path / "input.pdf"
    with fitz.open() as pdf:
        p = pdf.new_page()
        p.insert_text(
            (72, 90),
            "Clean original",
            fontname="tiro",
            fontsize=18,
            color=(0.2, 0.3, 0.4),
        )
        pdf.save(source)
    get_text = fitz.Page.get_text

    def text(page, *args, **kwargs):
        value = get_text(page, *args, **kwargs)
        if isinstance(value, dict) and args and args[0] == "dict":
            value["blocks"][0]["lines"][0]["spans"][0]["text"] += "\x00\x01\x0b"
        return value

    monkeypatch.setattr(fitz.Page, "get_text", text)
    warnings = pdf_to_word(
        source, tmp_path / "out.docx", "editable", Event(), lambda _: None
    )
    result = Document(tmp_path / "out.docx")
    run = next(p for p in result.paragraphs if p.text).runs[0]
    assert run.text == "Clean original"
    assert run.font.name == "Times-Roman"
    assert run.font.size.pt == 18
    assert any("control characters" in w for w in warnings)


@pytest.mark.parametrize("kind", ["docx", "ocr"])
def test_jobs_process_only_requested_pages_without_mutating_source(client, kind):
    d = upload(client, pdf_bytes(3))
    selected = d["pages"][1]["id"]
    r = client.post(
        f"/api/documents/{d['id']}/jobs", json={"kind": kind, "page_ids": [selected]}
    )
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json())
    assert job["status"] == "done", job
    result = client.get(f"/api/jobs/{job['id']}/download")
    if kind == "docx":
        paragraphs = " ".join(
            p.text for p in Document(io.BytesIO(result.content)).paragraphs
        )
        assert "Page 2 original" in paragraphs
        assert "Page 1 original" not in paragraphs
        assert "Page 3 original" not in paragraphs
    else:
        with fitz.open(stream=result.content, filetype="pdf") as output:
            assert len(output) == 1
            assert "Page 2 original" in output[0].get_text()
    state = client.get(f"/api/documents/{d['id']}").json()
    assert state["revision"] == 0 and len(state["pages"]) == 3
    for ids in [[], [selected, selected], ["bad"]]:
        assert (
            client.post(
                f"/api/documents/{d['id']}/jobs", json={"kind": kind, "page_ids": ids}
            ).status_code
            == 422
        )


def test_scan_to_word_ocr_produces_editable_text(client):
    image = Image.new("RGB", (1000, 500), "white")
    ImageDraw.Draw(image).text(
        (90, 150),
        "Scanned document 2048",
        font=ImageFont.truetype(str(FONT), 48),
        fill="black",
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    with fitz.open() as pdf:
        p = pdf.new_page(width=500, height=250)
        p.insert_image(p.rect, stream=stream.getvalue())
        data = pdf.tobytes()
    d = upload(client, data)
    r = client.post(
        f"/api/documents/{d['id']}/jobs",
        json={"kind": "docx", "page_ids": [d["pages"][0]["id"]], "ocr_first": True},
    )
    job = wait_job(client, r.json())
    assert job["status"] == "done", job
    result = Document(io.BytesIO(client.get(f"/api/jobs/{job['id']}/download").content))
    assert "2048" in " ".join(p.text for p in result.paragraphs)
    assert not result.inline_shapes


def test_native_font_size_and_color_can_be_reused(client):
    with fitz.open() as pdf:
        p = pdf.new_page()
        p.insert_text(
            (72, 100),
            "Original 2026",
            fontname="Custom",
            fontfile=str(FONT),
            fontsize=18,
            color=(0.25, 0.35, 0.45),
        )
        data = pdf.tobytes()
    d = upload(client, data)
    s = objects(client, d)["spans"][0]
    assert s["can_reuse_font"]
    d = op(
        client,
        d,
        {
            "kind": "replace_text",
            "page_id": d["pages"][0]["id"],
            "rect": s["rect"],
            "original": s["text"],
            "text": "Original 2027",
            "font": "original",
            "font_size": s["size"],
            "color": s["color"],
        },
    )
    with exported(client, d) as result:
        actual = result[0].get_text("dict")["blocks"][0]["lines"][0]["spans"][0]
        assert actual["text"] == "Original 2027"
        assert actual["font"] == s["font"]
        assert abs(actual["size"] - s["size"]) < 0.1
        assert abs(actual["color"] - int(s["color"][1:], 16)) < 0x10102


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_appearance_estimate_uses_scan_ink_instead_of_default_blue(client, rotation):
    image = Image.new("RGB", (1000, 400), "white")
    ImageDraw.Draw(image).text(
        (80, 100),
        "2026/07/15",
        font=ImageFont.truetype(str(FONT), 50),
        fill=(70, 80, 75),
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    with fitz.open() as pdf:
        p = pdf.new_page(width=500, height=200)
        p.insert_image(p.rect, stream=stream.getvalue())
        p.set_rotation(rotation)
        data = pdf.tobytes()
    d = upload(client, data)
    url = f"/api/documents/{d['id']}/pages/{d['pages'][0]['id']}/appearance"
    r = client.post(
        url, json={"revision": 0, "rect": [35, 45, 230, 85], "text": "2026/07/15"}
    )
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["estimated"]
    channels = [int(a["color"][i : i + 2], 16) for i in (1, 3, 5)]
    assert all(abs(x - y) < 20 for x, y in zip(channels, [70, 80, 75]))
    assert 12 < a["font_size"] < 40
    assert client.get(f"/api/documents/{d['id']}").json()["revision"] == 0


def test_private_phone_hostname_and_origin_are_explicit(client, monkeypatch):
    monkeypatch.setenv("STUDIO_PRIVATE_HOST", "my-pc.example.ts.net")
    assert (
        client.get(
            "/api/health",
            headers={
                "host": "my-pc.example.ts.net",
                "origin": "https://my-pc.example.ts.net",
            },
        ).status_code
        == 200
    )
    assert (
        client.get("/api/health", headers={"host": "other.example.ts.net"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/documents/new",
            headers={"host": "my-pc.example.ts.net", "origin": "https://evil.test"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/health",
            headers={
                "host": "my-pc.example.ts.net",
                "origin": "http://my-pc.example.ts.net",
            },
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/health",
            headers={
                "host": "127.0.0.1:8000",
                "origin": "https://my-pc.example.ts.net",
            },
        ).status_code
        == 200
    )
    monkeypatch.setenv("STUDIO_PRIVATE_HOST", "*")
    assert (
        client.get("/api/health", headers={"host": "my-pc.example.ts.net"}).status_code
        == 403
    )


def test_unavailable_original_font_character_is_rejected_atomically(client):
    with fitz.open() as pdf:
        p = pdf.new_page()
        p.insert_text((72, 100), "111", fontname="Custom", fontfile=str(FONT))
        pdf.subset_fonts()
        data = pdf.tobytes()
    d = upload(client, data)
    s = objects(client, d)["spans"][0]
    r = client.post(
        f"/api/documents/{d['id']}/operations",
        json={
            "revision": 0,
            "operation": {
                "kind": "replace_text",
                "page_id": d["pages"][0]["id"],
                "rect": s["rect"],
                "original": s["text"],
                "text": "ABC",
                "font": "original",
            },
        },
    )
    assert r.status_code == 422, r.text
    assert "fallback" in r.json()["detail"].lower()
    assert client.get(f"/api/documents/{d['id']}").json()["revision"] == 0
