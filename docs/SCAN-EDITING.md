# Edit scanned fields (0.3.0)

A scanned page contains pictures of text. OCR adds invisible text for searching and selection; it cannot recover the original font or turn the picture into an editable paragraph.

1. Open the PDF and choose **Edit scanned field**.
2. Drag around the whole visible field, including every digit and a little surrounding paper. Avoid neighboring labels, lines and stamps. Check the **Original scan area** preview.
3. Type the corrected text. Alternatively choose recognition language, mode and DPI, then **Recognize selected field**. For a printed Western-digit date, try English, **Numbers / dates**, 400 DPI. That restricted mode excludes letters and Arabic-Indic digits; use a text mode for those.
4. Compare the result with the original preview, then **Use recognized text** and correct any errors. Confidence is a suggestion, not a correctness guarantee.
5. Drag to reposition, or resize using the eight handles. A focused handle supports arrows; Shift increases the step. Resizing expands the source area until the field is moved, so check the preview again. Once moved, the original erase area stays fixed; choose **Reselect source area** to change it. Numeric coordinates change the destination only.
6. Keep **Fit text to box** enabled to shrink text when needed. Enlarge the box or reduce the maximum size if fitting would make text smaller than 4 pt. Choose the matching paper color for a flat background.
7. Click **Apply scan replacement**, inspect the page, then export a new PDF.

The selected image pixels and overlapping OCR text are removed, and new visible text is inserted using a fallback font. Selecting only half a date leaves the unselected half unchanged. A rectangle can also erase nearby material, so review carefully and use Undo when needed. Full-page OCR remains useful for searching, but regional recognition is usually easier to review for one field.

Simple RGB/gray images retain decoded samples outside the region, together with compatible image masks and color spaces. Complex/shared images use MuPDF image-pixel redaction. Re-encoding layered masks (such as JBIG2) can slightly change edge rendering beyond the field. Exact font, scan texture and background matching are not guaranteed. Editing is not forensic sanitization; the source and local history are retained.

**Discard** restores the initially opened PDF, including original pages and metadata, and clears all drafts and undo/redo. The confirmation is final for that working copy; it does not overwrite the original on disk. For an old password-protected working copy whose initial revision was already pruned, reopen the source once in this version to create its reset baseline.

On Windows, run setup once in the new extracted folder, then use the new desktop shortcut. It runs without a persistent console. Close an old console instance once before launching the update. Use **Settings → Quit app** to stop the background server; closing a browser tab alone leaves it running.
