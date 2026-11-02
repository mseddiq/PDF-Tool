# Windows 11 Pro: start here

You do not need Streamlit, hosting, a public website or a GitHub subscription. The app runs on your PC and opens in your browser. Other computers cannot connect to its loopback address.

1. Open https://github.com/mseddiq/PDF-Tool and select **Code > Download ZIP**.
2. Right-click the ZIP and choose **Extract All**. Put the extracted folder somewhere you will keep it, such as `Documents\PDF-Studio`. Do not run the app from inside the ZIP.
3. Open that extracted folder and double-click **Setup-Windows.cmd**. Allow prerequisite installers when Windows asks. This downloads Python and Node.js if needed, builds the app, and creates a **PDF Studio Pro** desktop shortcut. You do not have to create a virtual environment or enter PowerShell commands yourself. Setup can take several minutes.
4. Double-click the **PDF Studio Pro** desktop shortcut, or **Start-PDF-Studio.cmd** in the folder. Your browser opens after the app is ready.
5. Try a sample PDF first. The desktop shortcut runs without a console. Use **Settings → Quit app** to stop it. Closing the browser alone leaves the local app running. Setup itself keeps a window open until installation finishes.

Installation needs Internet. Normal PDF editing works offline afterward. Word conversion needs LibreOffice; OCR needs Tesseract and the selected language packs. Setup offers to install these tools through Windows Package Manager (winget). Their installers may ask for administrator permission. This is a source-based setup helper, not a signed standalone EXE installer.

## If setup needs help

- **Setup stops at `python.exe: File "<string>", line 1`:** this was a quoting bug in the first Windows setup helper. Download the latest ZIP, extract it into a new folder, and run its Setup-Windows.cmd. The corrected checks use `--version` for both Python and Node and skip broken candidates without aborting setup.
- **winget missing:** install Microsoft's **App Installer** through Microsoft Store, then rerun Setup-Windows.cmd. Alternatively, install Python 3.12 and Node.js LTS from their official sites first. If optional Office/OCR installation is unavailable, answer `n` to skip it and add those tools later.
- **English/Arabic OCR unavailable:** double-click `Install-OCR-Languages.cmd` in the extracted app folder. It installs official checksum-verified language data in `%LOCALAPPDATA%\PDFStudioPro\tessdata`, without requiring administrator access. Return to OCR and click **Refresh OCR status**. The OCR tool itself still requires Tesseract.
- **Windows shows a warning:** these source scripts are not digitally signed. Inspect them or ask for help if you are unsure; do not disable Windows security globally.
- **Setup failed:** keep the window open and copy the final error message. Run setup again after fixing the stated prerequisite.
- **Port already used:** the launcher reopens a recognized running PDF Studio instance. If an older version or another service is using port 8000, close its console window first.
- **Moved/deleted project folder:** the desktop shortcut points at the extracted folder. Keep it in place, or rerun setup to recreate the shortcut after moving it.
- **Updating from GitHub:** keep a backup of local documents; close the old app (close its console once if using an older version), extract a new copy and run setup in that copy. The new copy's shortcut replaces the old shortcut. Never paste a Linux/cloud `.venv` into Windows.

The scripts target Windows PowerShell 5.1 and Windows 10/11. The application feature suites, native prerequisite helper and OCR model installer passed on a GitHub-hosted Windows runner (see VALIDATION.md). The interactive winget/UAC setup and your specific Windows 11 Pro machine policies still need a local run.

## Extract your existing signature as PNG

Open the PDF, choose **Extract signature PNG**, and drag a tight rectangle around your signature. Choose a resolution and download. Enable **Make near-white paper transparent** only if wanted; it can remove faint light marks. This works with signatures that are part of scanned pages or PDF drawings, as well as images. If the signature is a separate embedded image, click it with **Select & edit** and choose **Export selected image as PNG** to retain original pixel dimensions. These exports do not change the PDF.

## Editing a scan

Follow [Edit scanned fields](SCAN-EDITING.md). OCR makes scan text searchable; it does not turn the original image into ordinary editable text. Version 0.3.0 provides a separate scanned-field replacement workflow, with an original-area preview and optional reviewed OCR.

If the app fails to open without a console, inspect `.studio-data/desktop.log` in the extracted folder. The desktop shortcut uses the local `pythonw.exe` directly. `Start-PDF-Studio.cmd` may briefly open a launch window, then exits. Re-run setup after updating to recreate the shortcut.

## Phone and page controls (0.4.0)

Use **Go to page** to edit one page. **Convert current page to Word** and **Remove current page** act on that page; conversion/OCR can use checked pages or the whole document if explicitly selected. Enable scan recognition in the Word dialog for editable text from scanned pages. See [private phone setup](PHONE.md) to access the PC from Android/iPhone through your own Tailscale network.
