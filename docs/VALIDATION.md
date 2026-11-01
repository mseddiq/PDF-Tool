# Current validation evidence

Validated on Linux in the managed cloud environment on 2026-11-01:

- Python 3.12.14; Node.js 24.19.0.
- `pytest tests -q`: **17 passed**, one upstream Starlette/AnyIO deprecation warning.
- `npm run test:e2e`: **2 passed** using installed Chromium.
- `npm run build`: TypeScript and Vite production build passed.
- `bash scripts/install.sh`: repeated successfully using Python and npm lockfiles.
- `bash scripts/cloud-system.sh`: repeated successfully; signed Debian packages, local prefix, LibreOffice 25.2.3.2; OCR packs ara, eng and osd detected.
- `bash scripts/start.sh`: started the application; health response reported status ok, LibreOffice true, OCR ara/eng/osd, 200 MB upload limit and 2,000-page limit.
- `git diff --check`: passed. Generated dependencies, working PDFs and build output are ignored. Source changes were not committed or pushed.

The backend suite reopened actual exports, checked native text removal, compared unchanged pixels, exercised Arabic replacement and supported font families, and ran real Word conversion and English OCR. See TESTING.md for coverage and FEATURES.md for unvalidated cases. Browser screenshots use synthetic content.

Cloud configuration `install_script` and `start_skill` were saved as a draft. Saving does not publish or verify restoration in a new task. Windows execution and production certification are outstanding.
