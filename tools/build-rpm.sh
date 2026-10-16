#!/usr/bin/env bash
# ساخت RPM خودکفای فدورا — پایتون و PySide6 داخل خود بسته‌اند
# (هیچ وابستگی سیستم لازم نیست؛ علت خطاهای «چیزی نصب نیست» در v1.0.0 همین بود)
# خروجی: dist/nicevpn-<ver>-1.x86_64.rpm
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(python3 -c "import sys;sys.path.insert(0,'$ROOT');from nicevpn import __version__;print(__version__)")"
DIST="$ROOT/dist"
mkdir -p "$DIST"
TMP="$(mktemp -d)"
export HOME="$TMP"   # pip cache بدون دست‌زدن به home واقعی
STAGE="$TMP/nicevpn-$VER"
mkdir -p "$STAGE/bin" "$STAGE/data" "$STAGE/runtime/lib/python3.11/site-packages"
trap 'rm -rf "$TMP"' EXIT

echo "==> [1/7] app package -> runtime site-packages"
cp -r "$ROOT/nicevpn" "$STAGE/runtime/lib/python3.11/site-packages/"

echo "==> [2/7] xray linux"
if [ -x "$ROOT/bin/xray" ]; then
  cp "$ROOT/bin/xray" "$STAGE/bin/xray"
else
  curl -fsSL -o "$TMP/xray-linux.zip" https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip
  python3 -m zipfile -e "$TMP/xray-linux.zip" "$TMP/xray-linux/"
  cp "$TMP/xray-linux/xray" "$STAGE/bin/xray"
fi
chmod 755 "$STAGE/bin/xray"

echo "==> [3/7] tun2socks (تونل کامل لینوکس)"
if [ -x "$ROOT/bin/tun2socks" ]; then
  cp "$ROOT/bin/tun2socks" "$STAGE/bin/tun2socks"
else
  curl -fsSL -o "$TMP/t2s.zip" https://github.com/xjasonlyu/tun2socks/releases/download/v2.7.0/tun2socks-linux-amd64.zip
  python3 -m zipfile -e "$TMP/t2s.zip" "$TMP/t2s/"
  cp "$TMP/t2s/tun2socks-linux-amd64" "$STAGE/bin/tun2socks"
fi
chmod 755 "$STAGE/bin/tun2socks"

echo "==> [4/7] اسکریپت روت تونل"
install -m 755 "$ROOT/packaging/linux/nicevpn-tun" "$STAGE/bin/nicevpn-tun"

echo "==> [5/7] geo files"
if [ -f "$ROOT/data/geoip.dat" ] && [ -f "$ROOT/data/geosite.dat" ]; then
  cp "$ROOT/data/geoip.dat" "$ROOT/data/geosite.dat" "$STAGE/data/"
else
  curl -fsSL -o "$STAGE/data/geoip.dat" https://github.com/v2fly/geoip/releases/latest/download/geoip.dat
  curl -fsSL -o "$STAGE/data/geosite.dat" https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat
fi

echo "==> [6/7] runtime python 3.11 + PySide6"
PB_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.11.17%2B20261013-x86_64-unknown-linux-gnu-install_only.tar.gz"
curl -fsSL -o "$TMP/pbp.tar.gz" "$PB_URL"
tar -C "$STAGE/runtime" --strip-components=1 -xzf "$TMP/pbp.tar.gz"
export PIP_DISABLE_PIP_VERSION_CHECK=1
"$STAGE/runtime/bin/python3" -m pip install --quiet --no-warn-script-location \
  --target "$STAGE/runtime/lib/python3.11/site-packages" \
  "PySide6-Essentials==6.12.0" "shiboken6==6.12.0"

find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> [6/7] run.sh + نسخه پرتابل لینوکس (جایگزین در صورت مشکل RPM)"
cat > "$STAGE/run.sh" <<'EOF'
#!/bin/bash
# Nice VPN — اجرای نسخه پرتابل (بدون نیاز به نصب)
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/runtime/bin/python3" -m nicevpn "$@"
EOF
chmod 755 "$STAGE/run.sh"
tar -C "$TMP" -czf "$DIST/NiceVPN-$VER-Linux-portable.tar.gz" "nicevpn-$VER"
echo "   portable -> $DIST/NiceVPN-$VER-Linux-portable.tar.gz"

echo "==> [7/7] tarball + rpmbuild"
tar -C "$TMP" -czf "$TMP/nicevpn-$VER.tar.gz" "nicevpn-$VER"

# debug_package=nil  : به find-debuginfo نیاز ندارد
# _dbpath            : دیتابیس موقت (روی روت بدون /var/lib/rpm هم کار می‌کند)
rpmbuild -bb \
  --define "debug_package %{nil}" \
  --define "_dbpath $TMP/rpmdb" \
  --define "_tmppath $TMP/rpmtmp" \
  --define "_topdir $TMP/rpmb" \
  --define "_sourcedir $TMP" \
  --define "_rpmdir $DIST" \
  --define "_builddir $TMP/rpmb/BUILD" \
  --define "_srcrpmdir $DIST" \
  "$ROOT/packaging/rpm/nicevpn.spec"

if [ -d "$DIST/x86_64" ]; then
  mv "$DIST"/x86_64/*.rpm "$DIST/"
  rmdir "$DIST/x86_64"
fi

echo "OK -> $DIST/"
