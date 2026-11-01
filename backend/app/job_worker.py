"""Isolated native processing worker. Progress IPC contains diagnostics, never logs."""

import json
import sys
import time
from pathlib import Path
from threading import Event
from .services.conversion import pdf_to_word, word_to_pdf, ocr_pdf

if __name__ == "__main__":
    source, output, status, kind, language, mode = sys.argv[1:]
    status = Path(status)

    def report(**value):
        temporary = status.with_suffix(".tmp")
        temporary.write_text(json.dumps(value), encoding="utf-8")
        # Windows antivirus/readers can briefly hold the previous file open.
        for attempt in range(40):
            try:
                temporary.replace(status)
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)

    cancel = Event()
    try:
        progress = lambda value: report(progress=value, status="running")
        progress(0)
        extra = {}
        if kind == "word_pdf":
            word_to_pdf(Path(source), Path(output), cancel)
        elif kind == "docx":
            extra["warnings"] = pdf_to_word(source, output, mode, cancel, progress)
        else:
            extra["review"] = ocr_pdf(source, output, language, cancel, progress)
        report(progress=1, status="done", **extra)
    except Exception as exc:
        report(
            status="failed",
            error=str(exc)
            if isinstance(exc, ValueError)
            else "Processing failed. Check the selected document, external binaries, fonts and language packs.",
        )
        sys.exit(1)
