import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
import pymupdf as fitz
from fastapi import HTTPException

ROOT = Path(os.getenv("STUDIO_DATA", ".studio-data")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
MAX_BYTES = int(os.getenv("STUDIO_MAX_MB", "200")) * 1024 * 1024
MAX_PAGES = int(os.getenv("STUDIO_MAX_PAGES", "2000"))
MAX_PIXELS = int(os.getenv("STUDIO_MAX_PIXELS", "24000000"))
MAX_HISTORY = int(os.getenv("STUDIO_MAX_HISTORY", "40"))
TIMEOUT = int(os.getenv("STUDIO_TIMEOUT", "180"))
RETENTION = int(os.getenv("STUDIO_RETENTION_HOURS", "24")) * 3600
LOCKS: dict[str, threading.RLock] = {}
GUARD = threading.Lock()
ENGINE_LOCK = threading.RLock()


def identifier(value):
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise HTTPException(404, "Document or asset not found.")
    return value


def folder(doc_id):
    path = ROOT / identifier(doc_id)
    if not path.is_dir():
        raise HTTPException(
            404, "Document expired or was closed. Reopen the original file."
        )
    return path


def load(doc_id):
    return json.loads((folder(doc_id) / "state.json").read_text("utf-8"))


def store(doc_id, state):
    path = folder(doc_id)
    tmp = path / "state.tmp"
    tmp.write_text(json.dumps(state), "utf-8")
    tmp.replace(path / "state.json")


def lock_for(doc_id):
    identifier(doc_id)
    with GUARD:
        return LOCKS.setdefault(doc_id, threading.RLock())


@contextmanager
def locked(doc_id):
    with ENGINE_LOCK, lock_for(doc_id):
        yield


def current(doc_id, state=None):
    state = state or load(doc_id)
    if state["kind"] != "pdf":
        raise HTTPException(
            422, "Convert this Word document to PDF before using PDF tools."
        )
    return folder(doc_id) / state["history"][state["cursor"]]["file"]


def page_ids(state):
    if state["kind"] != "pdf":
        raise HTTPException(
            422, "Convert this Word document to PDF before using PDF tools."
        )
    return state["history"][state["cursor"]]["pages"]


def commit(doc_id, doc, ids, state):
    if not 0 < len(ids) <= MAX_PAGES:
        raise HTTPException(422, f"A document must have 1–{MAX_PAGES} pages.")
    name = uuid.uuid4().hex + ".pdf"
    path = folder(doc_id) / name
    doc.save(path, garbage=4, deflate=True)
    # Reopen before promoting the revision: failed writes never change current state.
    with fitz.open(path) as check:
        if len(check) != len(ids):
            path.unlink(missing_ok=True)
            raise HTTPException(422, "Export verification failed.")
    old_history = state["history"]
    history = old_history[: state["cursor"] + 1] + [{"file": name, "pages": ids}]
    history = history[-MAX_HISTORY:]
    next_state = {
        **state,
        "history": history,
        "cursor": len(history) - 1,
        "revision": state["revision"] + 1,
    }
    store(doc_id, next_state)
    retained = {h["file"] for h in history}
    for h in old_history:
        if h["file"] not in retained:
            (folder(doc_id) / h["file"]).unlink(missing_ok=True)
    return next_state


def expect(state, revision):
    if state["revision"] != revision:
        raise HTTPException(409, "Document changed. Refresh before editing again.")


def cleanup():
    for path in ROOT.iterdir():
        if path.is_file() and re.fullmatch(r"export-[a-f0-9]{32}\.zip", path.name):
            if time.time() - path.stat().st_mtime > RETENTION:
                path.unlink(missing_ok=True)
            continue
        if path.is_dir() and re.fullmatch(r"[a-f0-9]{32}", path.name):
            if time.time() - path.stat().st_mtime > RETENTION:
                with lock_for(path.name):
                    shutil.rmtree(path, ignore_errors=True)
