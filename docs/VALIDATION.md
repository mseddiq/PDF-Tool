# Validation evidence — 0.4.0 page, conversion and appearance update

Validated locally on 2026-11-02 using the existing Linux Python 3.12, LibreOffice and English/Arabic Tesseract setup.

- Full browser suite: **43 passed**. New cases exercise page selector → one-page Word conversion → one-page removal, detected embedded font/size/color and replacement export, developer credit, and a 390-pixel responsive phone viewport.
- Full backend suite: **72 passed** (one upstream Starlette/AnyIO deprecation warning). New coverage includes XML filtering while preserving printable Unicode/Arabic/emoji; reopened Word style/text; page-limited Word/OCR output and invalid selections; OCR-before-Word editable scan text; original embedded-font reuse and atomic missing-glyph errors; scan ink/size estimates on four page rotations; private hostname/HTTPS-origin enforcement, including a reverse proxy that rewrites Host to loopback.
- TypeScript/Vite production build, Ruff E9/F63/F7/F82, PowerShell parsing/native prerequisites and git diff --check passed.
- The supplied nine-page PDF converted successfully and reopened with nine Word sections. Its XML-control filtering warning was observed. Date-region estimates chose a serif candidate and sampled the scan's gray ink. This validation ran locally; no supplied PDF, extracted content, Word output or page image is committed or uploaded to CI.

Font matching on scans compares three available candidates and remains approximate; ink bounds/colors can include nearby marks. Native embedded-font reuse is limited to compatible Latin text and available glyphs. Word reconstruction is approximate and can omit large scan backgrounds when using OCR text to avoid duplicate visible content. Review output.

Phone testing covers responsive desktop-browser emulation and HTTP access-policy checks. Actual Android/iOS file workflows, home-screen installation and the PC-to-phone Tailscale connection require testing on the owner's hardware. No private network or public deployment was activated by this change. The owner must configure Tailscale membership/access policy; the app has no multi-user login. See [phone instructions](PHONE.md).

## Remote Windows and Linux results for 0.4.0

[GitHub run 41437233239](https://github.com/mseddiq/PDF-Tool/actions/runs/41437233239), application commit `59c75ca`, completed with **Success** in 7m 24s. Both Ubuntu 24.04 and Windows jobs passed all **72 backend tests**, the production build and all **43 browser tests**. Windows also passed its native prerequisite helper and checksum-verified OCR model installation. Only upstream GitHub Action Node runtime deprecation warnings were reported.

This verifies the application on hosted Windows and Linux runners. Interactive winget/UAC installation, actual Android/iOS hardware and a real user-owned Tailscale connection remain outside those automated results.

## Earlier release evidence

### 0.3.0 scan and desktop update

Local validation completed on 2026-11-02:

| Check                | Observed outcome                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------ |
| Backend suite        | **60 passed**, no failures/skips; one upstream Starlette/AnyIO deprecation warning                           |
| Full browser suite   | **40 passed** against a fresh production server; uncaught JavaScript errors fail tests                       |
| Production build     | TypeScript and Vite passed                                                                                   |
| Python static checks | Ruff E9/F63/F7/F82 passed                                                                                    |
| PowerShell           | All scripts parsed; native prerequisite regression passed with real Python/Node and legacy argument handling |
| Whitespace           | git diff --check passed                                                                                      |

The new backend checks cover actual scan-pixel removal, soft/hard masks, retained color spaces, OCR provenance and word geometry, field recognition, tight-box fitting, baseline reset after history pruning, password-protected sources, legacy migration, and background server startup/shutdown. New browser checks exercise scan selection, pointer resize, regional recognition/review/correction/export, Discard, keyboard resize on all quarter-turn page rotations, and the desktop Quit interface. Existing conversion, signature, annotation, history, organizer, password and utility regressions also passed.

A user-supplied nine-page PDF was checked **locally only**. Focused numeric-date recognition matched the displayed date; the changed date persisted after export; the other eight pages rendered identically; full-page OCR preserved the original page pixels. The edited first page uses a layered hard image mask. Its re-encoding produced small edge-rendering differences outside the selected field (mean absolute RGB channel difference approximately 0.10 on a 0–255 scale at the default render scale). Compatible decoded samples outside the field were preserved; this is not a claim of pixel-identical rendering of the edited page. The supplied file, page images and extracted contents are not committed or uploaded to CI. Tests use generated fixtures.

## Remote verification for 0.3.0

[GitHub run 41354375836](https://github.com/mseddiq/PDF-Tool/actions/runs/41354375836), application commit `a00accd`, completed with **Success** in 4m 44s. Both Ubuntu 24.04 and Windows jobs passed the backend suite, production build, and full 40-case browser suite. The Windows backend run exercises the background service's no-attached-console assertion and graceful shutdown; native prerequisite checks and verified OCR model installation also passed. The final application commit `519c258`, including the empty-page guidance correction, also passed both jobs in [GitHub run 41354650760](https://github.com/mseddiq/PDF-Tool/actions/runs/41354650760), **Success** in 3m 44s. That final run includes all 60 backend and 40 browser tests on both operating systems.

Successful hosted Windows checks do not certify every interactive winget/UAC prompt or the user's particular PC. The private supplied PDF was tested locally, not in CI.

## Previous release evidence

### 0.2.0 review

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
