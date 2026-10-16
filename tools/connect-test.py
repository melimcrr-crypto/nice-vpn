#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست اتصال واقعی از مسیر خودِ برنامه (هسته + تأیید ترافیک).
استفاده:  python3 tools/connect-test.py [node_index]   (پیش‌فرض 1)

نکته: سرورهای UFO فقط به IP ایران پاسخ می‌دهند؛ روی رانر CI خروجی مورد انتظار:
«ترافیک رد شد» — این یعنی کد تا مرحله verify درست کار می‌کند.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from nicevpn import nodes as nodes_mod          # noqa: E402
from nicevpn import core as core_mod            # noqa: E402
from nicevpn.core import ST_CONNECTED, ST_FAILED, ST_STOPPED, ST_CONNECTING  # noqa: E402


def main():
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 0
    nodes = nodes_mod.load_builtin_nodes()
    node = nodes[idx]
    real = node.real_addr
    print(f"[*] node: {node.name}  real={real[0]}:{real[1]} [{node.type_label}]")

    core = core_mod.VpnCore(
        on_state=lambda s, m: print(f"[{s}] {m}"),
        on_log=lambda l: print("  |", l))
    core_mod.cleanup_stale()
    try:
        core.start(node, tun_mode=False)
    except core_mod.CoreError as e:
        print("[-] start failed:", e)
        sys.exit(2)

    deadline = time.time() + 60
    while time.time() < deadline:
        if core.state in (ST_CONNECTED, ST_FAILED, ST_STOPPED):
            break
        time.sleep(0.5)

    if core.state == ST_CONNECTED:
        try:
            ip, cc, city = core.check_real_ip()
            print(f"[+] CONNECTED — exit IP: {ip} ({cc} — {city})")
            core.stop()
            return
        except Exception as e:
            print(f"[+] CONNECTED (IP lookup failed: {e})")
            core.stop()
            return
    print(f"[-] result: {core.state} — از این شبکه سرور جواب نمی‌دهد (از ایران تست کنید)")
    try:
        core.stop()
    except Exception:
        pass
    sys.exit(4)


if __name__ == "__main__":
    main()
