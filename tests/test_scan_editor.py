import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont, ImageChops
from test_documents import (
    client,
    workspace,
    upload,
    op,
    exported,
    objects,
    wait_job,
    pdf_bytes,
)
from backend.app import core

FONT = Path(__file__).resolve().parents[1] / "backend/app/fonts/DejaVuSans.ttf"


def scan_pdf(hidden=False, rotation=0, alpha=False):
    image = Image.new(
        "RGBA" if alpha else "RGB",
        (1224, 1584),
        (255, 255, 255, 0) if alpha else "white",
    )
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 36)
    draw.text(
        (800, 350), "2026/07/15", font=font, fill=(0, 0, 0, 255) if alpha else "black"
    )
    draw.line(
        [(120, 1000), (160, 1040), (200, 1000)],
        fill=(20, 40, 180, 255) if alpha else "blue",
        width=5,
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    with fitz.open() as doc:
        p = doc.new_page(width=612, height=792)
        p.insert_image(p.rect, stream=stream.getvalue())
        if hidden:
            p.insert_text(
                (400, 192),
                "2026/07/15",
                fontname="OCR",
                fontfile=str(FONT),
                fontsize=12,
                render_mode=3,
            )
        p.set_rotation(rotation)
        doc.set_metadata({"title": "Original scan"})
        p = doc.new_page()
        p.insert_text((72, 90), "Untouched native page")
        return doc.tobytes()


@pytest.mark.parametrize("hidden", [False, True])
def test_scan_provenance_and_true_pixel_replacement(client, hidden):
    source = scan_pdf(hidden)
    d = upload(client, source)
    o = objects(client, d)
    assert o["scanned"]
    assert all(i["background"] for i in o["images"])
    assert o["has_ocr"] == hidden
    if hidden:
        span = o["spans"][0]
        assert span["source"] == "ocr"
        op(
            client,
            d,
            {
                "kind": "replace_text",
                "page_id": d["pages"][0]["id"],
                "rect": span["rect"],
                "original": span["text"],
                "text": "Corrected",
            },
            422,
        )
    region = [395, 170, 525, 205]
    d = op(
        client,
        d,
        {
            "kind": "replace_scan",
            "page_id": d["pages"][0]["id"],
            "source_rect": region,
            "rect": region,
            "text": "2026/08/01",
            "font_size": 35,
        },
    )
    with (
        exported(client, d) as result,
        fitz.open(stream=source, filetype="pdf") as original,
    ):
        assert "2026/08/01" in result[0].get_text()
        assert "2026/07/15" not in result[0].get_text()
        assert result[1].get_pixmap().samples == original[1].get_pixmap().samples
        a = original[0].get_pixmap()
        b = result[0].get_pixmap()
        diff = ImageChops.difference(
            Image.frombytes("RGB", (a.width, a.height), a.samples),
            Image.frombytes("RGB", (b.width, b.height), b.samples),
        )
        diff.paste((0, 0, 0), (393, 168, 527, 207))
        assert diff.getbbox() is None
        # Verify the old ink was erased from the image stream, not merely painted over.
        info = next(i for i in result[0].get_images() if i[2] == 1224)
        pix = fitz.Pixmap(result, info[0])
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        assert image.crop((790, 340, 1050, 410)).getextrema() == (
            (255, 255),
            (255, 255),
            (255, 255),
        )


def test_layered_scan_soft_mask_preserves_every_other_pixel(client):
    source = scan_pdf(alpha=True)
    d = upload(client, source)
    d = op(
        client,
        d,
        {
            "kind": "replace_scan",
            "page_id": d["pages"][0]["id"],
            "source_rect": [395, 170, 525, 205],
            "rect": [395, 170, 525, 205],
            "text": "Correct date",
            "font_size": 30,
        },
    )
    with (
        exported(client, d) as result,
        fitz.open(stream=source, filetype="pdf") as original,
    ):
        a = original[0].get_pixmap()
        b = result[0].get_pixmap()
        diff = ImageChops.difference(
            Image.frombytes("RGB", (a.width, a.height), a.samples),
            Image.frombytes("RGB", (b.width, b.height), b.samples),
        )
        diff.paste((0, 0, 0), (393, 168, 527, 207))
        assert diff.getbbox() is None


def test_layered_scan_hard_mask_keeps_color_space_and_unedited_samples(client):
    with fitz.open(stream=scan_pdf(alpha=True), filetype="pdf") as source:
        xref, mask_xref, *_ = source[0].get_images()[0]
        mask = fitz.Pixmap(source, mask_xref)
        alpha = Image.frombytes("L", (mask.width, mask.height), mask.samples)
        bits = alpha.point(lambda value: 0 if value else 255, mode="1")
        source.update_object(
            mask_xref,
            f"<< /Type /XObject /Subtype /Image /Width {mask.width} /Height {mask.height} /ImageMask true /BitsPerComponent 1 >>",
        )
        source.update_stream(mask_xref, bits.tobytes(), compress=True)
        source.xref_set_key(xref, "SMask", "null")
        source.xref_set_key(xref, "Mask", f"{mask_xref} 0 R")
        source.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
        data = source.tobytes()
    d = upload(client, data)
    d = op(
        client,
        d,
        {
            "kind": "replace_scan",
            "page_id": d["pages"][0]["id"],
            "source_rect": [395, 170, 525, 205],
            "rect": [395, 170, 525, 205],
            "text": "Corrected",
            "font_size": 18,
        },
    )
    with (
        exported(client, d) as result,
        fitz.open(stream=data, filetype="pdf") as original,
    ):
        xref, mask_xref, *_ = result[0].get_images()[0]
        assert result.xref_get_key(xref, "ColorSpace")[1] == "/DeviceRGB"
        assert result.xref_get_key(xref, "SMask")[0] == "null"
        assert result.xref_get_key(xref, "Mask")[0] == "xref"
        assert result.xref_get_key(mask_xref, "ImageMask")[1] == "true"
        for old_xref, new_xref in [
            (original[0].get_images()[0][0], xref),
            (original[0].get_images()[0][1], mask_xref),
        ]:
            a, b = fitz.Pixmap(original, old_xref), fitz.Pixmap(result, new_xref)
            mode = "RGB" if a.n == 3 else "L"
            diff = ImageChops.difference(
                Image.frombytes(mode, (a.width, a.height), a.samples),
                Image.frombytes(mode, (b.width, b.height), b.samples),
            )
            diff.paste(0, (789, 339, 1051, 411))
            assert diff.getbbox() is None
        a, b = original[0].get_pixmap(), result[0].get_pixmap()
        diff = ImageChops.difference(
            Image.frombytes("RGB", (a.width, a.height), a.samples),
            Image.frombytes("RGB", (b.width, b.height), b.samples),
        )
        diff.paste(0, (393, 168, 527, 207))
        assert diff.getbbox() is None


def test_tight_ocr_box_auto_fits_instead_of_height_failure(client):
    d = upload(client, scan_pdf(hidden=True))
    span = objects(client, d)["spans"][0]
    d = op(
        client,
        d,
        {
            "kind": "replace_scan",
            "page_id": d["pages"][0]["id"],
            "source_rect": [395, 170, 525, 205],
            "rect": span["rect"],
            "text": "2026/08/01",
            "font_size": 30,
            "fit_text": True,
        },
    )
    with exported(client, d) as out:
        span = next(
            s
            for b in out[0].get_text("dict")["blocks"]
            for l in b.get("lines", [])
            for s in l["spans"]
            if "2026/08/01" in s["text"]
        )
        assert 4 <= span["size"] < 30


def test_discard_restores_original_after_history_pruning(client, monkeypatch):
    monkeypatch.setattr(core, "MAX_HISTORY", 2)
    source = scan_pdf()
    d = upload(client, source)
    original_ids = [p["id"] for p in d["pages"]]
    for n in range(5):
        d = op(client, d, {"kind": "numbers", "font_size": 10})
    d = op(client, d, {"kind": "blank"})
    d = op(
        client, d, {"kind": "rotate", "page_ids": [d["pages"][0]["id"]], "angle": 90}
    )
    r = client.post(
        f"/api/documents/{d['id']}/discard", json={"revision": d["revision"]}
    )
    assert r.status_code == 200, r.text
    restored = r.json()
    assert not restored["can_undo"]
    assert not restored["can_redo"]
    assert [p["id"] for p in restored["pages"]] == original_ids
    with (
        exported(client, restored) as out,
        fitz.open(stream=source, filetype="pdf") as original,
    ):
        assert len(out) == len(original)
        assert all(
            a.get_pixmap().samples == b.get_pixmap().samples
            for a, b in zip(original, out)
        )
        assert out.metadata["title"] == "Original scan"
    assert (
        client.post(
            f"/api/documents/{d['id']}/discard", json={"revision": d["revision"]}
        ).status_code
        == 409
    )


def test_discard_password_opened_document(client):
    source = pdf_bytes(1)
    with fitz.open(stream=source, filetype="pdf") as pdf:
        encrypted = pdf.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="valid", owner_pw="valid"
        )
    d = upload(client, encrypted, password="valid")
    d = op(client, d, {"kind": "blank"})
    restored = client.post(
        f"/api/documents/{d['id']}/discard", json={"revision": d["revision"]}
    ).json()
    with exported(client, restored) as out:
        assert len(out) == 1
        assert "original secret" in out[0].get_text()


def test_region_ocr_job_is_readonly_reviewable_and_downloadable(client):
    d = upload(client, scan_pdf())
    j = client.post(
        f"/api/documents/{d['id']}/jobs",
        json={
            "kind": "ocr_region",
            "page_id": d["pages"][0]["id"],
            "rect": [395, 170, 525, 205],
            "language": "eng",
            "dpi": 400,
            "recognition_mode": "numbers",
        },
    )
    assert j.status_code == 200, j.text
    result = wait_job(client, j.json())
    assert result["status"] == "done", result
    assert result["region"]["text"] == "2026/07/15"
    assert result["revision"] == 0
    assert result["page_id"] == d["pages"][0]["id"]
    assert client.get(f"/api/documents/{d['id']}").json()["revision"] == 0
    response = client.get(f"/api/jobs/{result['id']}/download")
    assert response.status_code == 200
    assert response.json()["text"] == "2026/07/15"


def test_ocr_word_geometry_spans_the_detected_date(client):
    d = upload(client, scan_pdf())
    j = client.post(
        f"/api/documents/{d['id']}/jobs", json={"kind": "ocr", "language": "eng"}
    ).json()
    job = wait_job(client, j)
    assert job["status"] == "done", job
    data = client.get(f"/api/jobs/{job['id']}/download").content
    with fitz.open(stream=data, filetype="pdf") as out:
        boxes = out[0].search_for("2026/07/15")
        assert boxes
        assert (
            boxes[0].width > 95
        )  # The old uniformly fitted OCR glyphs covered only part of the date.


def test_discard_migrates_a_legacy_working_copy(client):
    d = upload(client, pdf_bytes(1))
    folder = core.folder(d["id"])
    state = core.load(d["id"])
    state.pop("baseline")
    core.store(d["id"], state)
    (folder / "baseline.pdf").unlink()
    d = op(client, d, {"kind": "blank"})
    r = client.post(
        f"/api/documents/{d['id']}/discard", json={"revision": d["revision"]}
    )
    assert r.status_code == 200
    assert len(r.json()["pages"]) == 1


def test_background_server_can_quit_without_a_console(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "STUDIO_PORT": str(port),
        "STUDIO_DATA": str(tmp_path / "desktop-data"),
    }
    root = Path(__file__).resolve().parents[1]
    with (tmp_path / "desktop.log").open("wb") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "backend.app.desktop_server"],
            cwd=root,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        url = f"http://127.0.0.1:{port}"
        try:
            status = None
            for _ in range(100):
                if proc.poll() is not None:
                    pytest.fail("Desktop server exited before readiness")
                try:
                    with opener.open(url + "/api/health", timeout=0.5) as response:
                        status = json.load(response)
                    break
                except OSError:
                    time.sleep(0.1)
            assert status and status["desktop_mode"]
            if os.name == "nt":
                assert status["console_attached"] is False
            with opener.open(
                urllib.request.Request(url + "/api/shutdown", method="POST"), timeout=3
            ) as response:
                assert json.load(response)["stopping"]
            assert proc.wait(timeout=10) == 0
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
