#!/usr/bin/env bash
# Optional rootless Debian 13 helpers for the managed cloud machine.
set -euo pipefail
base=/workspace/.studio-system
mkdir -p "$base/lists/partial" "$base/archives/partial" "$base/root" "$base/bin" "$base/tessdata"
cat > "$base/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian-security trixie-security main
SOURCES
options=(-o "Dir::Etc::sourcelist=$base/sources.list" -o Dir::Etc::sourceparts=- -o "Dir::State::lists=$base/lists" -o "Dir::Cache::archives=$base/archives" -o Debug::NoLocking=1)
apt-get "${options[@]}" update
apt-get "${options[@]}" --download-only --no-install-recommends -y install libreoffice-writer tesseract-ocr-ara
for package in "$base"/archives/*.deb; do dpkg-deb -x "$package" "$base/root"; done
python3 - <<'PY'
from pathlib import Path
root=Path('/workspace/.studio-system/root')
for p in root.rglob('*'):
    if p.is_symlink():
        target=p.readlink()
        local=root/str(target).lstrip('/')
        if target.is_absolute() and local.exists():p.unlink();p.symlink_to(local)
program=root/'usr/lib/libreoffice/program'
for p in program.glob('*rc'):
    p.write_text(p.read_text().replace('file:///usr/',root.as_uri()+'/usr/'))
registry=root/'usr/lib/libreoffice/share/registry/main.xcd'
registry.unlink(missing_ok=True)
registry.symlink_to(root/'usr/lib/libreoffice/share/.registry/main.xcd')
(root/'usr/lib/x86_64-linux-gnu/unorc').write_text((program/'unorc').read_text().replace('${ORIGIN}',program.as_uri()))
PY
cp /usr/share/tesseract-ocr/5/tessdata/eng.traineddata /usr/share/tesseract-ocr/5/tessdata/osd.traineddata "$base/tessdata/"
cp "$base/root/usr/share/tesseract-ocr/5/tessdata/ara.traineddata" "$base/tessdata/"
cp -r /usr/share/tesseract-ocr/5/tessdata/configs "$base/tessdata/"
cat > "$base/bin/libreoffice" <<'WRAPPER'
#!/bin/sh
STUDIO_SYSTEM=/workspace/.studio-system/root
export LD_LIBRARY_PATH="$STUDIO_SYSTEM/usr/lib/libreoffice/program:$STUDIO_SYSTEM/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$STUDIO_SYSTEM/usr/lib/libreoffice/program/soffice" "$@"
WRAPPER
chmod +x "$base/bin/libreoffice"
"$base/bin/libreoffice" --version
TESSDATA_PREFIX="$base/tessdata" tesseract --list-langs
