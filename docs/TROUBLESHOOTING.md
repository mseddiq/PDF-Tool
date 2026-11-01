# Troubleshooting

- **Cannot connect / blank application:** launch from repository root with scripts/start.sh or scripts/start.ps1. Build frontend with `npm ci` and `npm run build`. The backend serves the built files; rebuild after frontend edits. Use Vite for live development.
- **LibreOffice not detected:** install LibreOffice Writer, add its `program` directory to PATH and restart the backend. The health endpoint reports detection. Linux cloud setup may use `/workspace/.studio-system/bin/libreoffice`. Do not reuse a profile already open in desktop LibreOffice; conversions create isolated profiles automatically.
- **Missing OCR language pack:** run `tesseract --list-langs`. Install eng and ara data matching the installed Tesseract version. Double-click Install-OCR-Languages.cmd to install verified eng/ara models in the user-local app folder, then click Refresh OCR status. This version uses TSV and does not require Tesseract configs/pdf. STUDIO_TESSDATA_DIR overrides model discovery; an incorrect value must be corrected.
- **Arabic text differs:** insertion uses DejaVu Sans with shaping, not an exact copy of the original font. Presentation-form extraction may need Unicode NFKC normalization. Review complex bidirectional text visually and after reopening.
- **Text overflows:** enable **Fit text to box** (default), enlarge the destination rectangle, shorten the text, or reduce size. Automatic fitting stops at 4 pt. Nothing commits on overflow. Automatic arbitrary paragraph reflow is unsupported.
- **401 on upload:** the PDF requires a valid password. Password bypass is not supported.
- **409 stale revision:** another action updated the document. Refresh document state or reopen. Avoid concurrent edits in multiple tabs.
- **Shared image cannot move:** the same resource is used more than once. Resource replacement/deletion affects all uses. Insert a separate image instead of transforming the shared resource.
- **413 / pixel limit:** reduce zoom/image dimensions or raise documented STUDIO limits based on available resources. Do not disable safety bounds without measuring memory.
- **Conversion failed:** check binary availability, fonts and selected file. Review DOCX compatibility. Source and previous PDF revision remain safe. Jobs run in separate processes and can be cancelled.
- **No tests run / TestClient stalls in cloud sandbox:** use the execution environment's approved local socket/thread permission path. Do not treat a zero-test run as validation.
- **Port 8000 busy:** stop your previous PDF Studio process. If changing port, also update development proxy and local origin guards. Do not expose the app publicly.
- **Need to clear files:** close/delete in Settings, or stop the server and delete `.studio-data`. Retention cleanup runs at startup. Backups and file recovery outside this app are the user's responsibility.

- **Need a PNG of an existing signature:** use Extract signature PNG and draw a rectangle around it. Extract images only finds embedded raster resources, not all scanned or vector signatures.

- **Scan text cannot be selected / OCR edits leave the old date visible:** choose **Edit scanned field**, select the complete visible field, review the original-area preview, then type or recognize the replacement. Older OCR boxes may cover only part of the ink; reselect the full field. See [scan editing](SCAN-EDITING.md).
- **OCR gets a date wrong:** select only the date with a small margin (include all digits), English, Numbers / dates, 400 DPI. Compare with the original preview and correct it before applying. Higher confidence is not proof of correctness.
- **Resize is hard:** use the larger edge/corner handles; focus a handle and use arrows, or Shift+arrows for 10-point steps. Fit text to box avoids tiny OCR-box overflow.
- **Console still open after update:** stop the old console instance once, run Setup-Windows.cmd in the new extracted folder, then launch using the new desktop shortcut. Setup and the developer PowerShell launcher still use consoles.
- **Want to start over:** toolbar **Discard**, then confirm **Discard all changes**. This restores the initially opened PDF and clears undo/redo.
