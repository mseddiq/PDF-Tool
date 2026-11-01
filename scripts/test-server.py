"""Start the built app for cross-platform Playwright CI, using the test venv."""

import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
port = str(int(os.environ.get("STUDIO_TEST_PORT", "8000")))
raise SystemExit(
    subprocess.call(
        [
            str(python),
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            port,
        ],
        cwd=root,
    )
)
