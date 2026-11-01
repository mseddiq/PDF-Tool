import io
import json
import logging
import os
import shutil
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import pymupdf as fitz
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from .core import (
    ROOT,
    MAX_BYTES,
    MAX_PAGES,
    MAX_PIXELS,
    TIMEOUT,
    ENGINE_LOCK,
    cleanup,
    folder,
    load,
    store,
    locked,
    current,
    page_ids,
    expect,
    identifier,
    commit,
    ensure_baseline,
    discard_changes,
)
from .schemas import (
    Mutation,
    HistoryRequest,
    ExportRequest,
    JobRequest,
    RegionExport,
    DiscardRequest,
)
from .services.pdf import apply, index
from .services.content import text_spans
from .services.runtime import ocr_status, office_binary
from .services.extraction import embedded_png, region_png
from .services.conversion import word_to_pdf, pdf_to_word, ocr_pdf, Cancelled

from .version import VERSION

log = logging.getLogger("studio")
POOL = ThreadPoolExecutor(max_workers=2)
JOBS = {}
JOBS_LOCK = threading.Lock()
SHUTDOWN_EVENT = threading.Event()


@asynccontextmanager
async def lifespan(app):
    cleanup()
    yield
    for job in JOBS.values():
        job["cancel"].set()


app = FastAPI(title="PDF Studio Pro", version=VERSION, lifespan=lifespan)


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    if host not in ("localhost", "127.0.0.1", "testserver"):
        return JSONResponse(
            {"detail": "This service accepts local connections only."}, status_code=403
        )
    origin = request.headers.get("origin")
    if origin and origin not in (
        f"http://{request.headers.get('host')}",
        f"http://{host}:5173",
        f"http://{host}:8000",
        f"http://{host}",
    ):
        return JSONResponse(
            {"detail": "Cross-origin requests are not allowed."}, status_code=403
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def unexpected(request, exc):
    # Log exception type only: parser errors can contain private document text.
    log.error("Request failed: %s", type(exc).__name__)
    import errno

    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return JSONResponse(
            {
                "detail": "Not enough disk space. Free space or close old documents. Your previous PDF revision is safe."
            },
            status_code=507,
        )
    return JSONResponse(
        {
            "detail": "The operation failed. Your previous revision is safe. Check the file or retry with a simpler selection."
        },
        status_code=500,
    )


@app.get("/api/health")
def health():
    ocr = ocr_status()
    return {
        "status": "ok",
        "app": "PDF Studio Pro",
        "version": VERSION,
        "desktop_mode": os.getenv("STUDIO_DESKTOP") == "1",
        "console_attached": bool(
            __import__("ctypes").windll.kernel32.GetConsoleWindow()
        )
        if os.name == "nt" and os.getenv("STUDIO_DESKTOP") == "1"
        else False,
        "libreoffice": bool(office_binary()),
        "ocr_languages": ocr["languages"],
        "ocr": ocr,
        "max_mb": MAX_BYTES // 1024 // 1024,
        "max_pages": MAX_PAGES,
    }


async def read_upload(file):
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(
                413,
                f"File exceeds the configured {MAX_BYTES // 1024 // 1024} MB limit.",
            )
    return bytes(data)


@app.post("/api/new")
def new_document():
    doc_id = uuid.uuid4().hex
    path = ROOT / doc_id
    path.mkdir()
    with ENGINE_LOCK, fitz.open() as pdf:
        pdf.new_page(width=595, height=842)
        pdf.save(path / "initial.pdf")
    state = {
        "id": doc_id,
        "name": "Untitled.pdf",
        "kind": "pdf",
        "revision": 0,
        "cursor": 0,
        "history": [{"file": "initial.pdf", "pages": [uuid.uuid4().hex]}],
        "warnings": [],
    }
    store(doc_id, state)
    ensure_baseline(doc_id, state)
    return describe(doc_id)


@app.post("/api/documents")
async def upload(file: UploadFile = File(...), password: str = Form("")):
    data = await read_upload(file)
    doc_id = uuid.uuid4().hex
    path = ROOT / doc_id
    path.mkdir()
    name = Path((file.filename or "document").replace("\\", "/")).name[:180]
    try:
        if data.lstrip().startswith(b"%PDF-"):
            with ENGINE_LOCK, fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass and not pdf.authenticate(password):
                    raise HTTPException(401, "This PDF requires a valid password.")
                if not 0 < len(pdf) <= MAX_PAGES:
                    raise HTTPException(
                        422, "Document exceeds the page limit or contains no pages."
                    )
                warnings = []
                if pdf.get_sigflags() > 0:
                    warnings.append(
                        "This document contains signature fields. Modifications can invalidate digital signatures."
                    )
                if pdf.is_repaired:
                    warnings.append(
                        "The PDF required repair. Check the exported document carefully."
                    )
                pdf.save(
                    path / "initial.pdf",
                    garbage=4,
                    deflate=True,
                    encryption=fitz.PDF_ENCRYPT_NONE,
                )
            (path / "original.pdf").write_bytes(data)
            with fitz.open(path / "initial.pdf") as pdf:
                ids = [uuid.uuid4().hex for _ in pdf]
            state = {
                "id": doc_id,
                "name": name,
                "kind": "pdf",
                "revision": 0,
                "cursor": 0,
                "history": [{"file": "initial.pdf", "pages": ids}],
                "warnings": warnings,
            }
        elif zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist()) > MAX_BYTES * 4:
                    raise HTTPException(
                        413, "Expanded Word document exceeds the configured limit."
                    )
                if "word/document.xml" not in z.namelist():
                    raise HTTPException(415, "Upload a PDF or DOCX document.")
            from docx import Document

            Document(io.BytesIO(data))
            (path / "original.docx").write_bytes(data)
            state = {
                "id": doc_id,
                "name": name,
                "kind": "docx",
                "revision": 0,
                "cursor": 0,
                "history": [],
                "warnings": [],
            }
        else:
            raise HTTPException(415, "File contents are not a PDF or DOCX document.")
        store(doc_id, state)
        if state["kind"] == "pdf":
            ensure_baseline(doc_id, state)
        return describe(doc_id)
    except Exception as e:
        shutil.rmtree(path, ignore_errors=True)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(422, "The document is damaged or unsupported.") from None


@app.get("/api/documents/{doc_id}")
def describe(doc_id: str):
    with locked(doc_id):
        state = load(doc_id)
        base = {k: state[k] for k in ("id", "name", "kind", "revision", "warnings")}
        if state["kind"] == "docx":
            return {**base, "pages": [], "can_undo": False, "can_redo": False}
        with fitz.open(current(doc_id, state)) as pdf:
            pages = []
            for n, pid in enumerate(page_ids(state)):
                p = pdf[n]
                pages.append(
                    {
                        "id": pid,
                        "number": n + 1,
                        "width": p.rect.width,
                        "height": p.rect.height,
                        "rotation": p.rotation,
                        "bounds": list(p.rect * p.derotation_matrix),
                        "inverse": list(p.derotation_matrix),
                        "matrix": list(p.rotation_matrix),
                    }
                )
            return {
                **base,
                "pages": pages,
                "size": current(doc_id, state).stat().st_size,
                "metadata": pdf.metadata,
                "can_undo": state["cursor"] > 0,
                "can_redo": state["cursor"] < len(state["history"]) - 1,
            }


@app.get("/api/documents/{doc_id}/pages/{pid}/render")
def render(doc_id: str, pid: str, scale: float = 1):
    if not 0.1 <= scale <= 3:
        raise HTTPException(422, "Render scale must be between 0.1 and 3.")
    with locked(doc_id):
        state = load(doc_id)
        with fitz.open(current(doc_id, state)) as pdf:
            p = pdf[index(page_ids(state), pid)]
            if p.rect.width * p.rect.height * scale * scale > MAX_PIXELS:
                raise HTTPException(413, "Render exceeds pixel limit; reduce zoom.")
            return Response(
                p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes(
                    "png"
                ),
                media_type="image/png",
            )


@app.get("/api/documents/{doc_id}/pages/{pid}/objects")
def objects(doc_id: str, pid: str):
    with locked(doc_id):
        state = load(doc_id)
        with fitz.open(current(doc_id, state)) as pdf:
            p = pdf[index(page_ids(state), pid)]
            spans = text_spans(p)
            bounds = p.rect * p.derotation_matrix
            images = [
                {
                    "xref": i["xref"],
                    "rect": list(i["bbox"]),
                    "width": i["width"],
                    "height": i["height"],
                    "background": (fitz.Rect(i["bbox"]) & bounds).get_area()
                    / bounds.get_area()
                    > 0.65,
                }
                for i in p.get_image_info(xrefs=True)
            ]
            return {
                "spans": spans,
                "images": images,
                "scanned": any(i["background"] for i in images)
                or (bool(images) and not any(s["source"] == "native" for s in spans)),
                "has_ocr": any(s["source"] == "ocr" for s in spans),
                "warning": "OCR text is a recognition aid, not the visible scan. Review it before replacing an image region.",
            }


@app.post("/api/documents/{doc_id}/operations")
def mutate(doc_id: str, body: Mutation):
    source = body.operation.source_id
    # Acquire cross-document locks in stable order to prevent deadlocks during inserts.
    from contextlib import ExitStack

    with ExitStack() as stack:
        for key in sorted(set([doc_id] + ([source] if source else []))):
            stack.enter_context(locked(key))
        state = load(doc_id)
        expect(state, body.revision)
        if state["kind"] != "pdf":
            raise HTTPException(
                422, "Convert this Word document to PDF before editing."
            )
        with fitz.open(current(doc_id, state)) as pdf:
            ids = apply(pdf, page_ids(state), body.operation, doc_id)
            commit(doc_id, pdf, ids, state)
        return describe(doc_id)


@app.post("/api/documents/{doc_id}/discard")
def discard(doc_id: str, body: DiscardRequest):
    with locked(doc_id):
        state = load(doc_id)
        expect(state, body.revision)
        if state["kind"] != "pdf":
            raise HTTPException(422, "There are no PDF edits to discard.")
        discard_changes(doc_id, state)
        with JOBS_LOCK:
            for job in JOBS.values():
                if job["doc_id"] == doc_id and job["status"] in ("queued", "running"):
                    job["cancel"].set()
        return describe(doc_id)


@app.post("/api/shutdown")
def shutdown():
    if os.getenv("STUDIO_DESKTOP") != "1":
        raise HTTPException(409, "Stop the development server from its terminal.")
    SHUTDOWN_EVENT.set()
    return {"stopping": True}


@app.post("/api/documents/{doc_id}/history")
def history(doc_id: str, body: HistoryRequest):
    with locked(doc_id):
        state = load(doc_id)
        expect(state, body.revision)
        cursor = state["cursor"] + (-1 if body.direction == "undo" else 1)
        if not 0 <= cursor < len(state["history"]):
            raise HTTPException(422, "No further history available.")
        state["cursor"] = cursor
        state["revision"] += 1
        store(doc_id, state)
        return describe(doc_id)


@app.post("/api/documents/{doc_id}/assets")
async def asset(
    doc_id: str, file: UploadFile = File(...), signature: bool = Form(False)
):
    folder(doc_id)
    data = await read_upload(file)
    try:
        with Image.open(io.BytesIO(data)) as image:
            if (
                image.format not in ("PNG", "JPEG", "WEBP")
                or image.width * image.height > MAX_PIXELS
            ):
                raise ValueError()
            image = image.convert("RGBA")
            if signature:
                bounds = image.getchannel("A").getbbox()
                if not bounds:
                    raise ValueError()
                image = image.crop(bounds)
            aid = uuid.uuid4().hex
            image.save(folder(doc_id) / f"asset-{aid}.png")
            return {"id": aid, "width": image.width, "height": image.height}
    except (UnidentifiedImageError, ValueError, Image.DecompressionBombError):
        raise HTTPException(
            422,
            "Use a valid PNG, JPEG, or WebP within the pixel limit. Draw or upload a non-empty signature.",
        )


@app.post("/api/documents/{doc_id}/export")
def export(doc_id: str, body: ExportRequest):
    with locked(doc_id):
        state = load(doc_id)
        with fitz.open(current(doc_id, state)) as pdf:
            if body.page_ids is not None:
                if not body.page_ids:
                    raise HTTPException(422, "Select at least one page.")
                pdf.select([index(page_ids(state), pid) for pid in body.page_ids])
            opts = {"garbage": 4, "deflate": True}
            if body.password:
                opts.update(
                    encryption=fitz.PDF_ENCRYPT_AES_256,
                    owner_pw=body.password,
                    user_pw=body.password,
                )
            data = pdf.tobytes(**opts)
        return Response(
            data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="PDF-Studio-export.pdf"'
            },
        )


@app.get("/api/documents/{doc_id}/pages/{pid}/images/{xref}")
def export_embedded_image(doc_id: str, pid: str, xref: int):
    with locked(doc_id):
        state = load(doc_id)
        with fitz.open(current(doc_id, state)) as pdf:
            data = embedded_png(pdf, pdf[index(page_ids(state), pid)], xref)
        return Response(
            data,
            media_type="image/png",
            headers={
                "Content-Disposition": 'attachment; filename="signature-image.png"'
            },
        )


@app.post("/api/documents/{doc_id}/pages/{pid}/region-png")
def export_region(doc_id: str, pid: str, body: RegionExport):
    with locked(doc_id):
        state = load(doc_id)
        expect(state, body.revision)
        with fitz.open(current(doc_id, state)) as pdf:
            data = region_png(
                pdf[index(page_ids(state), pid)], body.rect, body.dpi, body.remove_white
            )
        return Response(
            data,
            media_type="image/png",
            headers={"Content-Disposition": 'attachment; filename="signature.png"'},
        )


@app.get("/api/documents/{doc_id}/images")
def extract_images(doc_id: str):
    path = ROOT / f"export-{uuid.uuid4().hex}.zip"
    try:
        with locked(doc_id):
            state = load(doc_id)
            with (
                fitz.open(current(doc_id, state)) as pdf,
                zipfile.ZipFile(path, "w") as archive,
            ):
                seen = set()
                for page in pdf:
                    for item in page.get_images():
                        xref = item[0]
                        if xref in seen:
                            continue
                        seen.add(xref)
                        archive.writestr(
                            f"image-{xref}.png", embedded_png(pdf, page, xref)
                        )
        return FileResponse(
            path,
            media_type="application/zip",
            filename="images.zip",
            background=BackgroundTask(path.unlink, missing_ok=True),
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise


@app.get("/api/documents/{doc_id}/search")
def search(doc_id: str, q: str):
    if not q or len(q) > 500:
        raise HTTPException(422, "Enter 1–500 search characters.")
    with locked(doc_id):
        state = load(doc_id)
        with fitz.open(current(doc_id, state)) as pdf:
            return [
                {"page_id": pid, "rect": list(r)}
                for pid, p in zip(page_ids(state), pdf)
                for r in p.search_for(q)
            ][:5000]


@app.delete("/api/documents/{doc_id}")
def close(doc_id: str):
    with locked(doc_id):
        with JOBS_LOCK:
            for j in JOBS.values():
                if j["doc_id"] == doc_id and j["status"] in ("queued", "running"):
                    raise HTTPException(
                        409, "Cancel and wait for running jobs before closing."
                    )
        with JOBS_LOCK:
            for jid in [key for key, job in JOBS.items() if job["doc_id"] == doc_id]:
                JOBS.pop(jid, None)
        shutil.rmtree(folder(doc_id))
    return {"closed": True}


@app.post("/api/documents/{doc_id}/jobs")
def create_job(doc_id: str, body: JobRequest):
    with locked(doc_id):
        state = load(doc_id)
        if (body.kind == "word_pdf") != (state["kind"] == "docx"):
            raise HTTPException(422, "Choose a conversion matching the document type.")
        if body.kind == "ocr_region":
            if not body.page_id or not body.rect:
                raise HTTPException(422, "Select a page region first.")
            page_index = index(page_ids(state), body.page_id)
        with JOBS_LOCK:
            if sum(j["status"] in ("queued", "running") for j in JOBS.values()) >= 8:
                raise HTTPException(429, "Job queue is full. Wait for a job to finish.")
            jid = uuid.uuid4().hex
            job = {
                "id": jid,
                "doc_id": doc_id,
                "status": "queued",
                "progress": 0,
                "cancel": threading.Event(),
                "kind": body.kind,
                "page_index": page_index if body.kind == "ocr_region" else None,
                "page_id": body.page_id,
                "revision": state["revision"],
                "warnings": [],
            }
            JOBS[jid] = job
        source = (
            folder(doc_id)
            / f"job-{jid}-input{'.docx' if body.kind == 'word_pdf' else '.pdf'}"
        )
        shutil.copyfile(
            folder(doc_id) / "original.docx"
            if body.kind == "word_pdf"
            else current(doc_id, state),
            source,
        )
        POOL.submit(run_job, job, source, body, state["revision"])
    return public_job(job)


def public_job(j):
    snapshot = j.copy()
    snapshot.pop("cancel", None)
    return snapshot


def run_job(job, source, body, revision):
    import subprocess
    import sys
    import signal
    import time

    output = (
        folder(job["doc_id"])
        / f"job-{job['id']}.{'docx' if body.kind == 'docx' else 'region.json' if body.kind == 'ocr_region' else 'pdf'}"
    )
    status = folder(job["doc_id"]) / f"job-{job['id']}.json"
    job["status"] = "running"

    def terminate(proc):
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait()

    try:
        if job["cancel"].is_set():
            raise Cancelled()
        command = [
            sys.executable,
            "-m",
            "backend.app.job_worker",
            str(source.resolve()),
            str(output.resolve()),
            str(status.resolve()),
            body.kind,
            body.language,
            body.mode,
            json.dumps({**body.model_dump(), "page_index": job.get("page_index")}),
        ]
        with subprocess.Popen(
            command,
            cwd=Path(__file__).resolve().parents[2],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ) as proc:
            deadline = time.monotonic() + TIMEOUT * max(
                1, len(page_ids(load(job["doc_id"]))) if body.kind == "ocr" else 1
            )
            while proc.poll() is None:
                if job["cancel"].wait(0.15):
                    terminate(proc)
                    raise Cancelled()
                if time.monotonic() > deadline:
                    terminate(proc)
                    raise ValueError(
                        "Processing timed out. Increase STUDIO_TIMEOUT or split the document."
                    )
                if status.exists():
                    try:
                        update = json.loads(status.read_text("utf-8"))
                        if "progress" in update:
                            job["progress"] = round(update["progress"], 3)
                    except (PermissionError, FileNotFoundError, json.JSONDecodeError):
                        pass  # Retry transient IPC sharing violations on the next poll.
            if job["cancel"].is_set():
                raise Cancelled()
            result = {
                "status": "failed",
                "error": "The isolated document processor stopped unexpectedly.",
            }
            for attempt in range(40):
                try:
                    if status.exists():
                        result = json.loads(status.read_text("utf-8"))
                    break
                except (PermissionError, json.JSONDecodeError):
                    if attempt == 39:
                        raise
                    time.sleep(0.05)
            job.update(result)
            if proc.returncode or job["status"] != "done":
                output.unlink(missing_ok=True)
                job["status"] = "failed"
    except Cancelled:
        output.unlink(missing_ok=True)
        job["status"] = "cancelled"
    except Exception as exc:
        output.unlink(missing_ok=True)
        job.update(
            status="failed",
            error=str(exc)
            if isinstance(exc, ValueError)
            else "Processing failed. Check external binaries and document compatibility.",
        )
    finally:
        source.unlink(missing_ok=True)
        status.unlink(missing_ok=True)


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    identifier(jid)
    if jid not in JOBS:
        raise HTTPException(404, "Job not found.")
    return public_job(JOBS[jid])


@app.delete("/api/jobs/{jid}")
def cancel_job(jid: str):
    get_job(jid)
    JOBS[jid]["cancel"].set()
    return {"requested": True}


@app.get("/api/jobs/{jid}/download")
def download_job(jid: str):
    j = get_job(jid)
    if j["status"] != "done":
        raise HTTPException(409, "Job has not completed successfully.")
    ext = (
        "docx"
        if j["kind"] == "docx"
        else "region.json"
        if j["kind"] == "ocr_region"
        else "pdf"
    )
    return FileResponse(
        folder(j["doc_id"]) / f"job-{jid}.{ext}", filename=f"PDF-Studio-converted.{ext}"
    )


STATIC = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if STATIC.is_dir():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="frontend")
