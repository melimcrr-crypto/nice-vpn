#!/usr/bin/env bash
# ساخت RPM فدورا — روی هر لینوکسی با rpmbuild (روی CI: ubuntu با apt install rpm)
# خروجی: dist/nicevpn-<ver>-1.<arch>.rpm
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(python3 -c "import sys;sys.path.insert(0,'$ROOT');from nicevpn import __version__;print(__version__)")"
DIST="$ROOT/dist"
mkdir -p "$DIST"
TMP="$(mktemp -d)"
STAGE="$TMP/nicevpn-$VER"
mkdir -p "$STAGE/bin" "$STAGE/data"

echo "==> app package ..."
cp -r "$ROOT/nicevpn" "$STAGE/"
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> xray linux ..."
if [ -x "$ROOT/bin/xray" ]; then
  cp "$ROOT/bin/xray" "$STAGE/bin/xray"
else
  curl -fsSL -o "$TMP/xray-linux.zip" https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip
  python3 -m zipfile -e "$TMP/xray-linux.zip" "$TMP/xray-linux/"
  cp "$TMP/xray-linux/xray" "$STAGE/bin/xray"
fi
chmod 755 "$STAGE/bin/xray"

echo "==> geo files ..."
if [ ! -f "$ROOT/data/geoip.dat" ] || [ ! -f "$ROOT/data/geosite.dat" ]; then
  curl -fsSL -o "$STAGE/data/geoip.dat" https://github.com/v2fly/geoip/releases/latest/download/geoip.dat
  curl -fsSL -o "$STAGE/data/geosite.dat" https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat
else
  cp "$ROOT/data/geoip.dat" "$ROOT/data/geosite.dat" "$STAGE/data/"
fi

echo "==> tarball ..."
tar -C "$TMP" -czf "$TMP/nicevpn-$VER.tar.gz" "nicevpn-$VER"

echo "==> rpmbuild ..."
# debug_package=nil  : به find-debuginfo نیاز ندارد
# _dbpath            : دیتابیس موقت (روی روت بدون /var/lib/rpm هم کار می‌کند)
rpmbuild -bb \
  --define "debug_package %{nil}" \
  --define "_dbpath $TMP/rpmdb" \
  --define "_topdir $TMP/rpmb" \
  --define "_sourcedir $TMP" \
  --define "_rpmdir $DIST" \
  --define "_builddir $TMP/rpmb/BUILD" \
  --define "_srcrpmdir $DIST" \
  "$ROOT/packaging/rpm/nicevpn.spec"

# rpmbuild خروجی را در dist/x86_64 می‌گذارد — به dist منتقل کن
if [ -d "$DIST/x86_64" ]; then
  mv "$DIST"/x86_64/*.rpm "$DIST/"
  rmdir "$DIST/x86_64"
fi

rm -rf "$TMP"
echo "OK -> $DIST/"
