# PDF Studio Pro

Version **0.4.0** fixes Word/XML conversion failures, adds current/checked-page conversion and OCR, native embedded-font reuse, scan appearance estimates, clearer page controls, and private phone access configuration. Developed by **Mohamed Seddiq**. See [phone setup](docs/PHONE.md) and [scan editing](docs/SCAN-EDITING.md).

A local React/TypeScript + FastAPI PDF workspace. Open real PDFs, replace supported native text using actual content redaction, organize pages, insert images/signatures, annotate, convert documents and run local OCR. No account, paid API, telemetry, remote fonts, or external document uploads.

**This is an implemented development application, not a certification of production readiness.** Read [feature coverage and limitations](docs/FEATURES.md) before relying on complex documents or sensitive redactions. PyMuPDF is AGPL/commercial licensed; see [licensing](docs/LICENSES.md) before redistribution.

## Windows 10/11 installation

**Easy Windows setup:** download the GitHub ZIP, extract it, and double-click `Setup-Windows.cmd`. After setup, use the **PDF Studio Pro** desktop shortcut or `Start-PDF-Studio.cmd`. No manual terminal commands are needed. See the [Windows step-by-step guide](docs/WINDOWS.md). Application tests and the helper/model scripts passed Windows CI; interactive installer prompts still need validation on your PC.

Install Python 3.12+, Node.js 22+ (24 tested), [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) and [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html). The recommended Setup-Windows.cmd installs checksum-verified `eng` and `ara` data in your user-local app folder. If they are missing, double-click `Install-OCR-Languages.cmd`, then choose **Refresh OCR status** inside the app. The launch script detects the usual Program Files locations; otherwise add the binaries to PATH. Use a standard PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

The desktop shortcut opens the local service on port 8000 without a console. Use **Settings → Quit app** to stop it; closing the browser alone leaves it running. The manual PowerShell developer launcher keeps a terminal and uses Ctrl+C. Installation needs Internet; built application use does not. See the current [validation evidence](docs/VALIDATION.md).

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

Vite proxies `/api` to the loopback backend. The production build is served by FastAPI. The default service accepts loopback only. Optional private phone access uses Tailscale Serve and an explicitly configured HTTPS hostname; see [phone setup](docs/PHONE.md). It remains a single-user workspace, without multi-user authentication.

## Use

- Drop a PDF/DOCX on the dashboard, or choose Open. Encrypted PDFs prompt for their valid password.
- Click a native text span. Edit text/style in Properties, then Apply. Font fallback is explicit. **Fit text to box** shrinks replacements when needed, with a 4 pt minimum; disable it for strict overflow rejection. Move boxes by dragging and resize with any of eight handles (or arrow keys, Shift for larger steps). Coordinates are also editable in Properties. Larger new text blocks support multiple lines; native paragraphs do not reflow automatically.
- For image-based text, choose **Edit scanned field**, draw around the entire visible field, then type the replacement or use **Recognize selected field**. For dates choose **Numbers / dates**, English and 400 DPI. Compare against the original-area preview, correct mistakes, then **Apply scan replacement**. This edits image pixels and adds fallback text; OCR alone only adds an invisible searchable layer. See [scan editing](docs/SCAN-EDITING.md).
- **Discard** restores the initially opened PDF and clears every edit, page change and draft. Confirm before discarding; this reset cannot be undone. Your original file on disk is unchanged.
- To save an existing signature as PNG, choose **Extract signature PNG**, drag tightly around it, then download. Optional near-white paper removal makes the PNG transparent; it can remove faint marks. Select an embedded image and choose **Export selected image as PNG** to preserve its original pixel dimensions and alpha.
- Choose Add text, enter content and drag a box, then Insert. For images, upload then drag the placement rectangle. Drawn, uploaded and typed signatures are placed on the current page immediately, ready to reposition. Undo removes inserted content. Visual signatures are not digital certificates.
- Thumbnails support drag sorting, keyboard sorting (Space, arrows, Space), multi-selection, rotation, deletion, duplication and blank insertion. Add pages imports another PDF with an inclusion/order preview. Split/extract exports the checked pages; repeat for each desired range.
- Annotation tools apply standard PDF annotations. Pick the tool, then drag; comments use the Text content field. Text replacements affect content streams; annotations are separate.
- **Go to page** selects the page you edit. **Convert current page to Word** and **Remove current page** act on that page; the removal confirmation supports Undo. Conversion/OCR dialogs offer current page, checked pages or the whole document, with current page as default.
- Native span selection detects font, size, ink color and style. Reusable embedded Latin fonts are selected automatically; unsupported scripts or missing glyphs require an explicit fallback. Scans have no font metadata: their ink and size are sampled, and recognizing the original text lets **Match scan appearance** compare three available font families. This remains an estimate.
- Convert runs local PDF-to-editable-DOCX reconstruction or LibreOffice DOCX rendering. The scan-recognition checkbox runs OCR first for editable Word output; large scan backgrounds are omitted to avoid duplicating the text. XML-incompatible PDF controls are filtered with a warning. OCR adds an invisible searchable layer while preserving the original page appearance, including scanned pages with native footers; it reports per-page confidence and review text, and lets you open the result as a new document. Jobs are isolated, report progress and can be cancelled.
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
