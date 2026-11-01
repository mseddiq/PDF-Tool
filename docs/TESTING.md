# Validation

The backend integration suite generates its own PDF/image/Word fixtures and reopens outputs. It covers 10-page uploads/rendering; content removal on page 3; exact unchanged-page and unrelated-region pixel preservation; failed-edit atomicity and stale revisions; three-document merge; delete/reorder/duplicate/rotate/blank/extract; undo/redo; transparent image/signature insertion; annotation persistence; encryption/passwords; invalid uploads and origin/host guards; Arabic shaping with Unicode normalization; crop; 100-page processing; DOCX text and table reconstruction; real Word rendering when LibreOffice is present; OCR searchability/confidence; moved text; moved/translucent images; all annotation types; failed export recovery; cancellation; and explicit close/cleanup.

Run from repository root:

```sh
.venv/bin/python -m pytest tests -q
```

The Word test checks actionable missing-binary errors if LibreOffice is absent, so report whether real conversion was exercised. In the prepared cloud instance LibreOffice was enabled for the final run. Arabic insertion is exercised; Arabic OCR recognition quality is not tested. The scan fixture is English. 100-page tests verify processing and order, not a full memory/performance benchmark. Test passwords and content are synthetic.

Browser tests exercise dashboard upload, true native-text replacement, undo/redo, page insertion, rotation and downloaded-PDF reopening; plus theme and mobile dashboard rendering. Chromium is started through Playwright using CHROMIUM_PATH or `/usr/bin/chromium`. Start the backend first and run:

```sh
cd frontend
npm run build
npm run test:e2e
```

Tests save workspace/mobile screenshots in docs. Desktop screenshots use generated content rather than customer documents. There is no claim that the full acceptance corpus, Windows, existing digital signatures, RTL OCR or hostile-file handling have been certified. See FEATURES.md.
