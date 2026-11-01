#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Cloud onboarding may retain user-local binaries outside the checkout.
if [[ -x /workspace/.studio-system/bin/libreoffice ]]; then
 export PATH="/workspace/.studio-system/bin:$PATH"
 export TESSDATA_PREFIX=/workspace/.studio-system/tessdata
fi
exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
