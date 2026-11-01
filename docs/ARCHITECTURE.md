# Architecture and decisions

PDF Studio Pro is a local browser client and a loopback FastAPI service. Documents never leave the machine. React and TypeScript provide the editing workspace; PyMuPDF renders, extracts and changes PDF content. python-docx reconstructs editable Word documents; LibreOffice converts DOCX to PDF; Tesseract supplies OCR. No remote conversion service is used.

## Licensing decision

PyMuPDF 1.26.6 is offered under AGPL-3.0 or a commercial Artifex license. This implementation uses its AGPL distribution. Redistribution or offering this application over a network requires a deliberate AGPL compliance review (including corresponding source) or an appropriate commercial license. This repository does not grant a commercial PyMuPDF license or declare the author's work licensed on their behalf. Do not distribute a proprietary bundle with this dependency without resolving those obligations. See LICENSES.md for sources and other components. pdf2docx is intentionally not required: its PyMuPDF dependency does not avoid these obligations and its layout reconstruction cannot promise exact fidelity.

## State and coordinates

The server stores each original upload and immutable PDF revisions in a random per-document workspace. A document has a revision cursor; mutations produce a new revision, undo/redo moves the cursor. A new mutation truncates the redo branch. Page IDs survive reorder, rotate, edits and history. Duplicates and imported/blank pages receive new IDs. Clients send a revision number to reject stale writes. Source uploads are never overwritten. Export rewrites the selected revision with garbage collection; replacement text is removed with PDF redaction, not hidden under paint.

Coordinates are unrotated PDF points (72 per inch), top-left origin, x right, y down, matching PyMuPDF. Render dimensions reflect the page rotation. The UI obtains a rotation matrix and its inverse for screen-to-document mapping. Normalized mouse positions map into the rendered rectangle and through the inverse matrix. Crop and text/image rectangles use unrotated coordinates. Native text replacement uses the selected span's box, explicitly detects overflow, and falls back to a bundled PDF base font for Latin. Complex-script insertion uses MuPDF HTML shaping; font availability and extraction must still be checked on representative files.

## Modules and implementation sequence

1. Storage, validated uploads, snapshots, render API and workspace.
2. Stable-page organizer and export.
3. Native span redaction/replacement, text, images, annotations and signatures.
4. Local conversion, OCR and utilities.
5. API integration, reopen/visual tests, Windows scripts and documentation.

Operations are discriminated JSON contracts, validated by Pydantic and dispatched by the PDF engine. Each operation opens a working revision; errors discard the mutation. A per-document lock serializes state changes. Conversion runs in isolated temporary directories with argument arrays and timeouts. File, page, pixel, history and time limits are configurable. Rendering happens lazily per requested page. OCR/conversion use cancellable background jobs. The service only accepts loopback Host headers and same-origin requests; the Vite development proxy keeps the client same-origin. Production serves the compiled frontend from FastAPI.
