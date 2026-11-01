# PDF Studio Pro 0.2.0: feature review

The user's reported signature workflow was **exporting an existing signature from a PDF to PNG**, not just inserting a signature and exporting a PDF. The original application did not expose that workflow adequately.

## Corrections

- Added **Extract signature PNG**: drag a region around an existing signature, choose 144/300/600 DPI, and optionally remove near-white paper. Works with scanned page images, native PDF drawing paths and ink annotations. The PDF and its revision are unchanged.
- Added original-resolution PNG export for a selected embedded image. Soft-mask transparency is preserved, including in bulk image ZIP exports. Large ZIP exports are file-backed rather than accumulated in RAM. White removal uses bounded image operations instead of a Python tuple per pixel.
- Added a non-admin Windows English/Arabic OCR installer using official Tesseract models pinned to a commit and verified with SHA-256. Initial setup includes it when OCR tools are chosen. The standalone installer can be rerun safely.
- OCR checks now distinguish missing executable, missing folder, missing language and corrupt/unreadable data. The UI prevents starting an unavailable language and can refresh tool status without a restart. Runtime discovers common Windows installations and user-local model data.
- Replaced Tesseract PDF reconstruction with a TSV-based invisible Unicode layer added to the original PDF. OCR no longer skips a scanned page merely because it has a native footer. Existing native words are not duplicated. Original images, annotations, rotation, crop and metadata are preserved. Alternate rotation is tried when recognition is weak.
- Drawn, uploaded, typed and reused signatures are placed visibly immediately; they do not inherit a background layer or low annotation opacity. Empty drawings are rejected, transparent margins are trimmed, and saved-signature reuse requires explicit consent.
- Fixed duplication of the last page. Added text-height overflow rejection, precise missing-image errors, original line/arrow direction, horizontal/freehand drawing support, Unicode footers and rotated footer positioning.
- Failed metadata/merge/watermark operations keep their dialogs open. Pending text/image placement cannot be silently omitted from PDF download. Document-specific assets and selections are cleared when switching documents. Selected-page export follows the preview's document order.
- Fixed print popup preparation so it starts during the user's click. Compression now shows before/after sizes. Thumbnail aspect ratios reserve space to avoid excessive eager requests on a 100-page document.
- Local working-copy IDs persist in the browser and are restored on refresh. Explicit close deletes the workspace and clears the remembered document. Finished job metadata is cleared when closing a document.
- Added retries for transient Windows file-sharing errors in worker status exchange. Read-only PDF tools reject DOCX input clearly instead of failing with an internal error.
- The Windows launcher can reopen a recognized running instance. It remains bound to loopback. Added an automated Linux/Windows feature-check workflow; a configured workflow is not proof that its remote run succeeded.

## Scope of evidence

See VALIDATION.md for executed commands and outcomes, TESTING.md for reproduction, and FEATURES.md for the remaining limitations. Tests use generated documents and reopen actual PDF, PNG, ZIP and DOCX outputs. Passing those cases does not guarantee every customer document, font, scan orientation, Word feature or signature encoding will work. This is not a certified digital-signature or forensic redaction product.
