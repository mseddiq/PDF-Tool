# Windows 11 Pro: start here

You do not need Streamlit, hosting, a public website or a GitHub subscription. The app runs on your PC and opens in your browser. Other computers cannot connect to its loopback address.

1. Open https://github.com/mseddiq/PDF-Tool and select **Code > Download ZIP**.
2. Right-click the ZIP and choose **Extract All**. Put the extracted folder somewhere you will keep it, such as `Documents\PDF-Studio`. Do not run the app from inside the ZIP.
3. Open that extracted folder and double-click **Setup-Windows.cmd**. Allow prerequisite installers when Windows asks. This downloads Python and Node.js if needed, builds the app, and creates a **PDF Studio Pro** desktop shortcut. You do not have to create a virtual environment or enter PowerShell commands yourself. Setup can take several minutes.
4. Double-click the **PDF Studio Pro** desktop shortcut, or **Start-PDF-Studio.cmd** in the folder. Your browser opens after the app is ready.
5. Try a sample PDF first. Keep the console window open while using the app. Press **Ctrl+C** in that window to stop it.

Installation needs Internet. Normal PDF editing works offline afterward. Word conversion needs LibreOffice; OCR needs Tesseract and the selected language packs. Setup offers to install these tools through Windows Package Manager (winget). Their installers may ask for administrator permission. This is a source-based setup helper, not a signed standalone EXE installer.

## If setup needs help

- **Setup stops at `python.exe: File "<string>", line 1`:** this was a quoting bug in the first Windows setup helper. Download the latest ZIP, extract it into a new folder, and run its Setup-Windows.cmd. The corrected checks use `--version` for both Python and Node and skip broken candidates without aborting setup.
- **winget missing:** install Microsoft's **App Installer** through Microsoft Store, then rerun Setup-Windows.cmd. Alternatively, install Python 3.12 and Node.js LTS from their official sites first. If optional Office/OCR installation is unavailable, answer `n` to skip it and add those tools later.
- **Arabic OCR unavailable:** install the Arabic `ara.traineddata` language data matching Tesseract and place it in its `tessdata` directory. The OCR dialog lists detected languages; do not assume Arabic is included by the Windows installer.
- **Windows shows a warning:** these source scripts are not digitally signed. Inspect them or ask for help if you are unsure; do not disable Windows security globally.
- **Setup failed:** keep the window open and copy the final error message. Run setup again after fixing the stated prerequisite.
- **Port already used:** close the previous PDF Studio console window before starting another copy.
- **Moved/deleted project folder:** the desktop shortcut points at the extracted folder. Keep it in place, or rerun setup to recreate the shortcut after moving it.
- **Updating from GitHub:** keep a backup of local documents; extract a new copy and run setup in that copy. The new copy's shortcut replaces the old shortcut. Never paste a Linux/cloud `.venv` into Windows.

The scripts target Windows PowerShell 5.1 and Windows 10/11. They were reviewed in Linux but have not been executed on a Windows PC here. The first Windows run is still required to verify installer availability, language packs and machine-specific settings.
