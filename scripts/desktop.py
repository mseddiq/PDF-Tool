"""Launch with pythonw on Windows; the application never needs a console."""

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.version import VERSION

URL = "http://127.0.0.1:8000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def health():
    try:
        with OPENER.open(URL + "/api/health", timeout=0.8) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def error(message):
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "PDF Studio Pro", 0x10)
    else:
        print(message, file=sys.stderr)


def open_existing(status):
    if status.get("app") != "PDF Studio Pro":
        raise RuntimeError(
            "Another service is using port 8000. Close it before starting PDF Studio Pro."
        )
    if status.get("version") != VERSION:
        raise RuntimeError(
            "An older PDF Studio Pro instance is still running. Close its console window (or use Quit app in its Settings), then start this version again."
        )
    webbrowser.open(URL)


def main():
    mutex = None
    try:
        if os.name == "nt":
            kernel = ctypes.windll.kernel32
            kernel.CreateMutexW.restype = ctypes.c_void_p
            mutex = kernel.CreateMutexW(None, False, "Local\\PDFStudioProLauncher")
            if kernel.GetLastError() == 183:
                for _ in range(120):
                    existing = health()
                    if existing:
                        open_existing(existing)
                        return
                    time.sleep(0.5)
                raise RuntimeError(
                    "Another launch is still in progress. Try again shortly."
                )
        existing = health()
        if existing:
            open_existing(existing)
            return
        python = (
            ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        if not python.is_file() or not (ROOT / "frontend/dist/index.html").is_file():
            raise RuntimeError("Run Setup-Windows.cmd once before opening the app.")
        log_dir = ROOT / ".studio-data"
        log_dir.mkdir(exist_ok=True)
        log = log_dir / "desktop.log"
        if log.exists() and log.stat().st_size > 1024 * 1024:
            log.replace(log.with_suffix(".old.log"))
        environment = os.environ.copy()
        environment["STUDIO_DESKTOP"] = "1"
        with log.open("ab") as output:
            process = subprocess.Popen(
                [str(python), "-m", "backend.app.desktop_server"],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError(
                    "The local server could not start. Check whether an older app is running. Technical details are in .studio-data/desktop.log."
                )
            existing = health()
            if existing:
                open_existing(existing)
                return
            time.sleep(0.5)
        process.terminate()
        raise RuntimeError(
            "The app took too long to start. Try again; technical details are in .studio-data/desktop.log."
        )
    except Exception as exc:
        error(str(exc))
    finally:
        if mutex:
            ctypes.windll.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
