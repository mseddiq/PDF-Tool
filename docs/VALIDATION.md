# Validation evidence — 0.2.0 review

Executed in the Linux managed cloud environment on 2026-11-01, followed by successful GitHub-hosted Windows and Linux verification:

| Check                        | Observed outcome                                                                                                                  |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Backend suite                | **48 passed**, no failures/skips; one upstream Starlette/AnyIO deprecation warning                                                |
| Full Chromium suite          | **32 passed** in one final run; uncaught page errors fail tests                                                                   |
| Keyboard organizer stability | **5 additional repeated runs passed** after waiting for the sensor's initialization frame                                         |
| Production build             | TypeScript and Vite build passed                                                                                                  |
| Python static checks         | Ruff E9/F63/F7/F82 checks passed                                                                                                  |
| Windows scripts              | All PowerShell scripts parsed successfully with PowerShell 7.5.4                                                                  |
| Windows prerequisite helper  | Real Python/Node, failed executable, missing path, old Node and paths with spaces passed with legacy argument handling            |
| OCR language installer       | Actual official eng/ara download and SHA-256 checks passed in an isolated directory with spaces; repeat run verified/reused files |
| Runtime health               | App/version PDF Studio Pro 0.2.0; LibreOffice available; eng/ara OCR available; no OCR configuration error                        |
| Repository whitespace        | git diff --check passed                                                                                                           |

The backend run used Python 3.12.14, local LibreOffice 25.2.3.2 and Tesseract with English/Arabic data. The browser used the installed Chromium against a fresh server on loopback port 8001 with the production frontend. The documented start script was also used to run version 0.2.0 on port 8000.

Artifacts were reopened with PyMuPDF, Pillow, zipfile and python-docx. Verified outcomes include actual removed/replacement text, visible signatures in exported PDFs, PNG signature crops from scans/vector drawings/ink annotations, original embedded image resolution and alpha, preserved source pixels after OCR, real bilingual OCR text, actual Word conversions, page ordering, every shipped annotation type, password handling and failure recovery. TESTING.md gives commands and coverage. REVIEW.md explains the fixes.

## Remote Windows and Linux results

[GitHub run 41334348363](https://github.com/mseddiq/PDF-Tool/actions/runs/41334348363), application commit `15bd5a9`, completed with **Success**. Both the `ubuntu-24.04` and `windows-latest` jobs succeeded. Each job installs real document tools, runs the backend suite, builds the frontend and executes the browser suite against a fresh local server using the runner's Chrome. Windows also executes the native prerequisite regression script and the checksum-verified OCR model installer.

The first CI attempt exposed a browser installation environment failure and a Windows interpreter-selection failure. Linux now uses the supported Ubuntu 24.04 runner and its installed Chrome. Windows creates the virtual environment using the explicit setup-python path, avoiding LibreOffice's bundled Python. The Windows setup helper likewise excludes that bundled interpreter. Earlier failed runs are not counted as passes.

## Limits of these results

These are representative generated fixtures, not a complete corpus of customer documents. They do not certify arbitrary font matching, paragraph reflow, perfect Word reconstruction, forensic redaction, cryptographic signatures or hostile-document sandboxing. The 100-page checks are functional/lazy-rendering checks, not a full native-memory or disk-exhaustion benchmark.

Successful Windows CI verifies the application on a hosted Windows runner; it does not establish every interactive Windows 11 Pro installer prompt or machine configuration. Winget/UAC behavior, local antivirus and machine policies still need validation on the target PC. Do not describe those as passed based solely on this report.
