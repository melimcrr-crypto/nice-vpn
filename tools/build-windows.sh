#!/usr/bin/env bash
# ساخت پکیج پرتابل ویندوز Nice VPN — روی لینوکس (یا CI) اجرا می‌شود
# خروجی: dist/NiceVPN-<ver>-Windows-x64.zip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(python3 -c "import sys;sys.path.insert(0,'$ROOT');from nicevpn import __version__;print(__version__)")"
DIST="$ROOT/dist"
mkdir -p "$DIST"
TMP="$(mktemp -d)"
STAGE="$TMP/NiceVPN-$VER"
mkdir -p "$STAGE/bin" "$STAGE/data" "$STAGE/runtime"

echo "==> [1/7] xray-windows-64 ..."
curl -fsSL -o "$TMP/xray-win.zip" https://github.com/XTLS/Xray-core/releases/latest/download/Xray-windows-64.zip
python3 -m zipfile -e "$TMP/xray-win.zip" "$TMP/xray-win/"
cp "$TMP/xray-win/xray.exe" "$STAGE/bin/"

echo "==> [2/7] geo files ..."
cp "$ROOT/data/geoip.dat" "$ROOT/data/geosite.dat" "$STAGE/data/"

echo "==> [3/7] python 3.11 embeddable ..."
curl -fsSL -o "$TMP/pyembed.zip" https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
python3 -m zipfile -e "$TMP/pyembed.zip" "$STAGE/runtime/"

echo "==> [4/7] PySide6 wheels (win_amd64) ..."
python3 -m pip download --quiet \
  --platform win_amd64 --python-version 3.11 --implementation cp --only-binary=:all: \
  -d "$TMP/wheels" "PySide6-Essentials==6.12.0" "shiboken6==6.12.0"
mkdir -p "$STAGE/runtime/Lib/site-packages"
for w in "$TMP/wheels"/*.whl; do
  python3 -m zipfile -e "$w" "$STAGE/runtime/Lib/site-packages/"
done

echo "==> [5/7] app package ..."
cp -r "$ROOT/nicevpn" "$STAGE/runtime/Lib/site-packages/nicevpn"
cat > "$STAGE/runtime/python311._pth" <<'EOF'
python311.zip
.
Lib/site-packages
import site
EOF

echo "==> [6/7] launchers ..."
cp "$ROOT/packaging/windows/NiceVPN.bat" "$STAGE/"
cp "$ROOT/packaging/windows/NiceVPN-debug.bat" "$STAGE/"
cp "$ROOT/packaging/windows/MakeShortcut.bat" "$STAGE/"
# README با BOM برای نمایش درست فارسی در Notepad قدیمی
printf '\xEF\xBB\xBF' > "$STAGE/README-Windows.txt"
cat "$ROOT/packaging/windows/README-Windows.txt" >> "$STAGE/README-Windows.txt"
# فایل لایسنس
cp "$ROOT/LICENSE" "$STAGE/" 2>/dev/null || true

find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> [7/7] zip ..."
cd "$TMP"
zip -qr "$DIST/NiceVPN-$VER-Windows-x64.zip" "NiceVPN-$VER"
rm -rf "$TMP"
echo "OK -> $DIST/NiceVPN-$VER-Windows-x64.zip"
