#!/usr/bin/env bash
# دانلود xray + tun2socks (لینوکس) و فایل‌های geo برای اجرای از سورس
# استفاده:  bash tools/fetch-binaries.sh [--with-tun]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/bin" "$ROOT/data"

if [ ! -x "$ROOT/bin/xray" ]; then
  echo "==> xray-linux-64 ..."
  T=$(mktemp -d)
  curl -fsSL -o "$T/xray.zip" https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip
  python3 -m zipfile -e "$T/xray.zip" "$T/xray/"
  cp "$T/xray/xray" "$ROOT/bin/xray"
  chmod 755 "$ROOT/bin/xray"
  rm -rf "$T"
else
  echo "==> bin/xray موجود است"
fi

if [ ! -f "$ROOT/data/geoip.dat" ]; then
  echo "==> geoip.dat ..."
  curl -fsSL -o "$ROOT/data/geoip.dat" https://github.com/v2fly/geoip/releases/latest/download/geoip.dat
fi
if [ ! -f "$ROOT/data/geosite.dat" ]; then
  echo "==> geosite.dat ..."
  curl -fsSL -o "$ROOT/data/geosite.dat" https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat
  mv "$ROOT/data/dlc.dat" "$ROOT/data/geosite.dat" 2>/dev/null || true
fi

if [ "${1:-}" = "--with-tun" ]; then
  echo "==> tun2socks (تونل کامل) ..."
  T2=$(mktemp -d)
  curl -fsSL -o "$T2/t2s.zip" https://github.com/xjasonlyu/tun2socks/releases/download/v2.7.0/tun2socks-linux-amd64.zip
  python3 -m zipfile -e "$T2/t2s.zip" "$T2/t2s/"
  cp "$T2/t2s/tun2socks-linux-amd64" "$ROOT/bin/tun2socks"
  chmod 755 "$ROOT/bin/tun2socks"
  rm -rf "$T2"
fi

echo "OK: bin/ و data/ آماده است"
