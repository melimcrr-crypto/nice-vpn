#!/usr/bin/env bash
# نصب آخرین نسخه RPM فدورا از GitHub Releases — یک دستور:
#   curl -fsSL https://raw.githubusercontent.com/melimcrr-crypto/nice-vpn/main/install-fedora.sh | bash
set -euo pipefail
REPO="melimcrr-crypto/nice-vpn"

echo "==> دریافت آخرین نسخه RPM از Releases ..."
URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | grep -o '"browser_download_url": *"[^"]*\.rpm"' \
  | head -1 | cut -d'"' -f4)

if [ -z "$URL" ]; then
  echo "!! نسخه‌ای پیدا نشد — از https://github.com/$REPO/releases دستی دانلود کنید" >&2
  exit 1
fi

TMP=$(mktemp --suffix=.rpm)
echo "==> دانلود: $URL"
curl -fL --progress-bar -o "$TMP" "$URL"
echo "==> نصب (رمز sudo لازم است) ..."
sudo dnf install -y "$TMP"
rm -f "$TMP"

echo ""
echo "✔ نصب شد! از منوی برنامه‌ها «Nice VPN» را باز کنید یا بزنید: nicevpn"
