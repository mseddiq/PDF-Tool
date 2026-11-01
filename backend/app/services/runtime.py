"""Discover local tools in both installer-managed and custom installations."""

import os
import re
import shutil
import subprocess
from pathlib import Path
import pytesseract


def tesseract_binary():
    explicit = os.getenv("STUDIO_TESSERACT_CMD")
    if explicit:
        return shutil.which(explicit) or (
            explicit if Path(explicit).is_file() else None
        )
    found = shutil.which("tesseract")
    if found:
        return found
    for base in (
        os.getenv("ProgramFiles"),
        os.getenv("ProgramFiles(x86)"),
        os.getenv("LOCALAPPDATA"),
    ):
        if base:
            for suffix in (
                "Tesseract-OCR/tesseract.exe",
                "Programs/Tesseract-OCR/tesseract.exe",
            ):
                candidate = Path(base) / suffix
                if candidate.is_file():
                    return str(candidate)
    return None


def tessdata_directory():
    explicit = os.getenv("STUDIO_TESSDATA_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    base = os.getenv("LOCALAPPDATA")
    if base:
        managed = Path(base) / "PDFStudioPro" / "tessdata"
        if all(
            (managed / (lang + ".traineddata")).is_file() for lang in ("eng", "ara")
        ):
            return managed.resolve()
    inherited = os.getenv("TESSDATA_PREFIX")
    return Path(inherited).expanduser().resolve() if inherited else None


def ocr_status():
    binary = tesseract_binary()
    data = tessdata_directory()
    status = {
        "available": bool(binary),
        "languages": [],
        "data_directory": str(data) if data else None,
        "error": None,
    }
    if not binary:
        status["error"] = (
            "Tesseract is not installed or cannot be found. Rerun Setup-Windows.cmd and choose the OCR tools."
        )
        return status
    if data and not data.is_dir():
        status["error"] = (
            "The configured OCR data folder does not exist. Run Install-OCR-Languages.cmd or correct STUDIO_TESSDATA_DIR."
        )
        return status
    command = [binary, "--list-langs"]
    if data:
        command += ["--tessdata-dir", str(data)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            raise ValueError()
        if not data:
            match = re.search(
                r'"([^"]+)"', result.stdout.splitlines()[0] if result.stdout else ""
            )
            if match:
                status["data_directory"] = match.group(1)
        status["languages"] = sorted(
            {
                line.strip()
                for line in result.stdout.splitlines()[1:]
                if re.fullmatch(r"[a-zA-Z0-9_]+", line.strip())
            }
        )
        if not status["languages"]:
            status["error"] = (
                "No OCR language data was found. Double-click Install-OCR-Languages.cmd, then refresh OCR status."
            )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        status["available"] = False
        status["error"] = (
            "Tesseract could not start. Check its installation and OCR data directory."
        )
    return status


def configure_ocr(language):
    status = ocr_status()
    if not status["available"] or status["error"]:
        raise ValueError(status["error"])
    missing = sorted(set(language.split("+")) - set(status["languages"]))
    if missing:
        raise ValueError(
            "Missing OCR language data: "
            + ", ".join(missing)
            + ". Double-click Install-OCR-Languages.cmd, then refresh OCR status."
        )
    pytesseract.pytesseract.tesseract_cmd = tesseract_binary()
    directory = tessdata_directory()
    if directory:
        # No shell quoting needed, including for Windows user names with spaces.
        os.environ["TESSDATA_PREFIX"] = str(directory)
    return status


def office_binary():
    found = shutil.which("libreoffice") or shutil.which("soffice")
    if found:
        return found
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.getenv(variable):
            path = Path(os.environ[variable]) / "LibreOffice/program/soffice.exe"
            if path.is_file():
                return str(path)
    return None
