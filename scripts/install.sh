#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
(cd frontend && npm ci --no-audit --no-fund && npm run build)
printf '%s\n' 'Install LibreOffice Writer and Tesseract (eng/ara language packs) using your OS package manager for local conversion and OCR.'
