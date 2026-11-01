# Troubleshooting

- **Cannot connect / blank application:** launch from repository root with scripts/start.sh or scripts/start.ps1. Build frontend with `npm ci` and `npm run build`. The backend serves the built files; rebuild after frontend edits. Use Vite for live development.
- **LibreOffice not detected:** install LibreOffice Writer, add its `program` directory to PATH and restart the backend. The health endpoint reports detection. Linux cloud setup may use `/workspace/.studio-system/bin/libreoffice`. Do not reuse a profile already open in desktop LibreOffice; conversions create isolated profiles automatically.
- **Missing OCR language pack:** run `tesseract --list-langs`. Install eng and ara data matching the installed Tesseract version. If TESSDATA_PREFIX is set, it must point to the tessdata directory containing both traineddata files and configs (including PDF output config). Restart the service.
- **Arabic text differs:** insertion uses DejaVu Sans with shaping, not an exact copy of the original font. Presentation-form extraction may need Unicode NFKC normalization. Review complex bidirectional text visually and after reopening.
- **Text overflows:** reduce size, enlarge the destination rectangle, shorten the text, or insert a separate larger text block. Nothing commits on overflow. Automatic arbitrary paragraph reflow is unsupported.
- **401 on upload:** the PDF requires a valid password. Password bypass is not supported.
- **409 stale revision:** another action updated the document. Refresh document state or reopen. Avoid concurrent edits in multiple tabs.
- **Shared image cannot move:** the same resource is used more than once. Resource replacement/deletion affects all uses. Insert a separate image instead of transforming the shared resource.
- **413 / pixel limit:** reduce zoom/image dimensions or raise documented STUDIO limits based on available resources. Do not disable safety bounds without measuring memory.
- **Conversion failed:** check binary availability, fonts and selected file. Review DOCX compatibility. Source and previous PDF revision remain safe. Jobs run in separate processes and can be cancelled.
- **No tests run / TestClient stalls in cloud sandbox:** use the execution environment's approved local socket/thread permission path. Do not treat a zero-test run as validation.
- **Port 8000 busy:** stop your previous PDF Studio process. If changing port, also update development proxy and local origin guards. Do not expose the app publicly.
- **Need to clear files:** close/delete in Settings, or stop the server and delete `.studio-data`. Retention cleanup runs at startup. Backups and file recovery outside this app are the user's responsibility.
