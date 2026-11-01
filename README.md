# PDF Studio Pro

Version **0.2.0** includes a feature review, existing-signature PNG export, repaired OCR, and expanded regression coverage. See [review findings](docs/REVIEW.md).

A local React/TypeScript + FastAPI PDF workspace. Open real PDFs, replace supported native text using actual content redaction, organize pages, insert images/signatures, annotate, convert documents and run local OCR. No account, paid API, telemetry, remote fonts, or external document uploads.

**This is an implemented development application, not a certification of production readiness.** Read [feature coverage and limitations](docs/FEATURES.md) before relying on complex documents or sensitive redactions. PyMuPDF is AGPL/commercial licensed; see [licensing](docs/LICENSES.md) before redistribution.

## Windows 10/11 installation

**Easy Windows setup:** download the GitHub ZIP, extract it, and double-click `Setup-Windows.cmd`. After setup, use the **PDF Studio Pro** desktop shortcut or `Start-PDF-Studio.cmd`. No manual terminal commands are needed. See the [Windows step-by-step guide](docs/WINDOWS.md). The scripts have not yet been executed on Windows.

Install Python 3.12+, Node.js 22+ (24 tested), [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) and [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html). The recommended Setup-Windows.cmd installs checksum-verified `eng` and `ara` data in your user-local app folder. If they are missing, double-click `Install-OCR-Languages.cmd`, then choose **Refresh OCR status** inside the app. The launch script detects the usual Program Files locations; otherwise add the binaries to PATH. Use a standard PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

The browser opens the local service on port 8000. Keep the terminal open; Ctrl+C stops it. Installation needs Internet; built application use does not. Windows scripts are supplied but have not been executed on Windows in this Linux development environment.

## Linux / macOS

Install Python 3.12+, Node 22+, LibreOffice Writer, Tesseract and English/Arabic OCR packs through your OS package manager, then:

```sh
bash scripts/install.sh
bash scripts/start.sh
```

For frontend development, run the backend, then in a second terminal:

```sh
cd frontend
npm run dev
```

Vite proxies `/api` to the loopback backend. The production build is served by FastAPI. Do not bind this service to a public network: it is designed for a single local user, not as a multi-user hosted service.

## Use

- Drop a PDF/DOCX on the dashboard, or choose Open. Encrypted PDFs prompt for their valid password.
- Click a native text span. Edit text/style in Properties, then Apply. Font fallback is explicit, and too-wide text is rejected without changing the revision. Text selection boxes can be moved/resized through point coordinates in Properties. Larger new text blocks support multiple lines; native paragraphs do not reflow automatically.
- To save an existing signature as PNG, choose **Extract signature PNG**, drag tightly around it, then download. Optional near-white paper removal makes the PNG transparent; it can remove faint marks. Select an embedded image and choose **Export selected image as PNG** to preserve its original pixel dimensions and alpha.
- Choose Add text, enter content and drag a box, then Insert. For images, upload then drag the placement rectangle. Drawn, uploaded and typed signatures are placed on the current page immediately, ready to reposition. Undo removes inserted content. Visual signatures are not digital certificates.
- Thumbnails support drag sorting, keyboard sorting (Space, arrows, Space), multi-selection, rotation, deletion, duplication and blank insertion. Add pages imports another PDF with an inclusion/order preview. Split/extract exports the checked pages; repeat for each desired range.
- Annotation tools apply standard PDF annotations. Pick the tool, then drag; comments use the Text content field. Text replacements affect content streams; annotations are separate.
- Convert runs local PDF-to-editable-DOCX reconstruction or LibreOffice DOCX rendering. OCR adds an invisible searchable layer while preserving the original page appearance, including scanned pages with native footers; it reports per-page confidence and review text, and lets you open the result as a new document. Jobs are isolated, report progress and can be cancelled.
- Export / Ctrl+S downloads a new PDF. Source files are never overwritten. An optional export password encrypts the output. Undo/redo works across revisions and page operations.
- Refreshing the browser restores the most recent local working copy. Settings can delete that document immediately. Working directories older than the retention window are removed on server startup; this is not secure disk erasure. Stop the service and remove `.studio-data` to clear all retained files.

## Validation

```sh
.venv/bin/python -m pytest tests -q
cd frontend
npm run build
# With backend running and Chromium installed:
npm run test:e2e
```

Set `CHROMIUM_PATH` to the installed Chromium executable for Playwright. The default on Linux is `/usr/bin/chromium`; Windows uses Playwright-managed Chromium unless CHROMIUM_PATH is specified. Run `npx playwright install chromium` in frontend to install that browser. See [test coverage](docs/TESTING.md), [architecture](docs/ARCHITECTURE.md), and [troubleshooting](docs/TROUBLESHOOTING.md).

## Configuration

Copy values from `.env.example` into your launch environment (files are not loaded automatically). Limits are configurable: 200 MB per upload, 2,000 pages, 24 million pixels per render/image, 40 retained revisions, 180-second conversion timeout (OCR scales by page count), and 24-hour startup retention. Large images/100-page files are rendered lazily; immutable revision snapshots trade disk space for reliable history. This is not a hostile-file sandbox: open trusted documents, and keep parsers and external binaries updated.

## Repository structure

`frontend/src`: typed API, editor workspace, sortable thumbnails and styles. `backend/app`: validated API, workspace/revision storage, PDF operations, isolated jobs and conversion services. `tests`: generated document integration and pixel-preservation tests. `frontend/e2e`: real Chromium edit/export checks. `scripts`: install and launch helpers. `docs`: architecture, license, coverage, validation and troubleshooting notes.
