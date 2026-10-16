#!/usr/bin/env bash
# دانلود xray (لینوکس) و فایل‌های geo برای اجرای از سورس
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
  echo "==> hev-socks5-tunnel (حالت TUN) ..."
  T=$(mktemp -d)
  curl -fsSL -o "$T/hev.tar.gz" https://github.com/heiher/hev-socks5-tunnel/releases/latest/download/hev-socks5-tunnel-linux-x86_64.tar.gz 2>/dev/null \
    || curl -fsSL -o "$T/hev" https://github.com/heiher/hev-socks5-tunnel/releases/latest/download/hev-socks5-tunnel-linux-x86_64
  (tar -C "$T" -xzf "$T/hev.tar.gz" 2>/dev/null || true)
  B=$(find "$T" -name "hev-socks5-tunnel" -type f | head -1)
  [ -n "$B" ] && cp "$B" "$ROOT/bin/hev-socks5-tunnel" && chmod 755 "$ROOT/bin/hev-socks5-tunnel" \
    || { curl -fsSL -o "$ROOT/bin/hev-socks5-tunnel" https://github.com/heiher/hev-socks5-tunnel/releases/latest/download/hev-socks5-tunnel-linux-x86_64 && chmod 755 "$ROOT/bin/hev-socks5-tunnel"; }
  rm -rf "$T"
fi

echo "OK: bin/ و data/ آماده است"
