# Feature validation

Tests generate synthetic PDFs, scans, signatures, PNG/JPEG/WebP images and Word documents. They reopen downloaded artifacts and assert content, page order, alpha, pixels, annotations and metadata. No customer documents are committed or sent to remote services.

## Backend

From the repository root, with local LibreOffice and Tesseract (eng/ara) available:

```sh
.venv/bin/python -m pytest tests -q
```

The prepared Linux cloud instance uses:

```sh
PATH=/workspace/.studio-system/bin:$PATH \
TESSDATA_PREFIX=/workspace/.studio-system/tessdata \
.venv/bin/python -m pytest tests -q
```

Coverage includes native text removal, Unicode/Arabic text, font families, overflow, all page operations and history branching, 10/100-page files, merge three PDFs, image formats/replacement/transformation/shared resources, image ZIP alpha, visual signatures, every annotation type and line direction, crop on rotated pages, metadata/watermarks/numbers/compression, password round trips, invalid uploads/limits, native signature-field warnings, DOCX misuse errors, failure recovery and cancellation. OCR cases include real English/Arabic recognition, scanned pages with native footers, all quarter-turn page rotations, preserved source pixels/annotations/metadata, missing models, missing executable and data paths containing spaces. Signature-region PNG tests cover scans, native drawing paths, ink annotations and embedded images with soft masks.

The Word test verifies real LibreOffice rendering when installed, or its actionable missing-binary error otherwise. Confirm tool health before describing the former as exercised. A passing synthetic OCR test is not an accuracy guarantee for real handwriting, low-resolution scans or arbitrary reading order. The 100-page cases demonstrate processing and lazy loading, not exhaustive native-memory benchmarking.

## Browser

Build the frontend and start the backend, then:

```sh
cd frontend
npm ci
npm run build
npm run test:e2e
```

On Linux the default browser is `/usr/bin/chromium`; override `CHROMIUM_PATH` if needed. On Windows install a Playwright browser with `npx playwright install chromium`, or specify `CHROMIUM_PATH`. Fixture generation uses the platform's `.venv` Python; override `STUDIO_TEST_PYTHON` for another Python 3.12 environment.

CI mode starts a fresh test server automatically. For example, against the installed Linux Chromium on a separate loopback port:

```sh
CI=true STUDIO_TEST_PORT=8001 CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e
```

Browser checks cover actual upload/edit/export/undo/redo, existing-signature region and resource PNG downloads, four signature input paths, new text and unapplied-draft protection, image placement/movement/replacement/deletion and ZIP export, every annotation tool, keyboard page sorting, merge preview and subset export, Word conversions, bilingual OCR and opening results, missing-tool preflight, utilities/search/printing, password prompts, failed-operation dialogs, working-copy restore, Arabic text, theme, mobile inspector, zoom/fit/crop and 100-page thumbnail loading. Uncaught browser JavaScript errors fail the suite. Test artifacts are written under frontend/test-results, not tracked documentation.

The 0.3.0 scan suite additionally checks native/OCR provenance, real raster-pixel removal, soft and hard masks, retained color spaces, automatic fitting, regional numeric OCR, correct OCR word widths, baseline restoration after history pruning, encrypted input, legacy migration, and the background desktop service lifecycle. Windows asserts that this service has no attached console. Browser cases cover scan replacement, region OCR review/correction, Discard, eight resize handles and keyboard resizing on all four page rotations, and the Quit interface.

## Windows helpers

```powershell
powershell -NoProfile -File tests/windows-prerequisites.ps1 -PythonPath C:\Path\To\Python312\python.exe -NodePath C:\Path\To\node.exe
```

This exercises real native version calls, invalid candidates, stderr failures, unsupported Node versions, paths with spaces and error-preference restoration. Under PowerShell 7 it explicitly uses legacy native argument passing. The OCR model installer can be tested in an isolated folder:

```powershell
powershell -NoProfile -File scripts/install-ocr-languages.ps1 -DataDirectory "C:\Temp\OCR models test"
```

Repeat to check checksum verification and reuse. The workflow in .github/workflows/verify.yml configures Linux and Windows backend/browser checks using actual document tools and retains synthetic artifacts. Its remote results must be observed before claiming Windows CI passed. CI does not exercise every interactive winget installer prompt, machine policy, antivirus product or Windows 11 Pro desktop setting.

## 0.4.0 additions

New checks cover printable Unicode versus forbidden XML controls, real DOCX reconstruction with injected parser controls, detected Word font styling, page-scoped Word and OCR output, invalid page selections, OCR-before-Word editable output, reusable embedded fonts and missing-glyph atomic rejection, scan appearance on all four rotations, and explicit private HTTPS hostname/origin guards. Browser cases cover page selection → Word download → single-page removal, automatic embedded face/size/color, developer credit and a 390-pixel phone viewport. These responsive tests do not substitute for real Android/iOS and Tailscale device testing.
