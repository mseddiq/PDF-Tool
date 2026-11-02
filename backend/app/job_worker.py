"""Isolated native processing worker. Progress IPC contains diagnostics, never logs."""

import json
import sys
import time
from pathlib import Path
from threading import Event
from .services.conversion import pdf_to_word, word_to_pdf, ocr_pdf, recognize_region

if __name__ == "__main__":
    source, output, status, kind, language, mode, *arguments = sys.argv[1:]
    options = json.loads(arguments[0]) if arguments else {}
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
            if options.get("ocr_first"):
                recognized = Path(output).with_suffix(".ocr-input.pdf")
                try:
                    ocr_pdf(
                        source,
                        recognized,
                        language,
                        cancel,
                        lambda value: progress(value * 0.6),
                    )
                    extra["warnings"] = pdf_to_word(
                        recognized,
                        output,
                        mode,
                        cancel,
                        lambda value: progress(0.6 + value * 0.4),
                    )
                finally:
                    recognized.unlink(missing_ok=True)
            else:
                extra["warnings"] = pdf_to_word(source, output, mode, cancel, progress)
        elif kind == "ocr_region":
            extra["region"] = recognize_region(
                source,
                options["page_index"],
                options["rect"],
                language,
                options.get("dpi", 300),
                options.get("recognition_mode", "auto"),
                cancel,
            )
            Path(output).write_text(json.dumps(extra["region"]), encoding="utf-8")
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
