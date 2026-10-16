#!/usr/bin/env bash
# اجرای مستقیم از سورس (بدون نصب)
cd "$(dirname "$0")"
[ -x bin/xray ] || bash tools/fetch-binaries.sh
exec python3 -m nicevpn "$@"
