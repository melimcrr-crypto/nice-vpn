#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست اتصال واقعی: xray بالا می‌آید، curl از داخل تونل IP را می‌گیرد.
استفاده:  python3 tools/connect-test.py [node_index]   (پیش‌فرض 1)
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from nicevpn import nodes as nodes_mod          # noqa: E402
from nicevpn import xrayconf                    # noqa: E402

XRAY = os.path.join(ROOT, "bin", "xray.exe" if os.name == "nt" else "xray")


def main():
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 0
    nodes = nodes_mod.load_builtin_nodes()
    node = nodes[idx]
    print(f"[*] node: {node.name}  {node.address}:{node.port} [{node.type_label}]")

    cfg = xrayconf.write_xray_config(node, "/tmp")
    tenv = dict(os.environ)
    if xrayconf.has_geo_files():
        tenv["XRAY_LOCATION_ASSET"] = xrayconf.DATA_DIR
    r = subprocess.run([XRAY, "run", "-test", "-c", cfg], capture_output=True, text=True, timeout=30, env=tenv)
    ok_line = (r.stdout + r.stderr).strip().splitlines()
    print("[*] xray -test:", ok_line[-1] if ok_line else "?")
    if r.returncode != 0:
        print("[-] config test FAILED")
        sys.exit(2)

    env = dict(os.environ)
    if xrayconf.has_geo_files():
        env["XRAY_LOCATION_ASSET"] = xrayconf.DATA_DIR
    proc = subprocess.Popen([XRAY, "run", "-c", cfg], stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT, env=env)
    try:
        # صبر تا ساکت شدن پورت
        import socket
        alive = False
        for _ in range(30):
            try:
                s = socket.create_connection(("127.0.0.1", xrayconf.SOCKS_PORT), timeout=1)
                s.close()
                alive = True
                break
            except Exception:
                time.sleep(0.3)
        if not alive:
            print("[-] socks port did not open")
            sys.exit(3)
        print("[*] socks5 127.0.0.1:%d is up" % xrayconf.SOCKS_PORT)

        r = subprocess.run(
            ["curl", "-s", "--max-time", "15", "--socks5-hostname",
             f"127.0.0.1:{xrayconf.SOCKS_PORT}", "http://ip-api.com/json/?fields=query,countryCode,city"],
            capture_output=True, text=True, timeout=25)
        if r.returncode == 0 and r.stdout.strip():
            j = json.loads(r.stdout)
            print(f"[+] CONNECTED — exit IP: {j.get('query')} ({j.get('countryCode')} — {j.get('city')})")
            return
        # فال‌بک https
        r = subprocess.run(
            ["curl", "-s", "--max-time", "15", "--socks5-hostname",
             f"127.0.0.1:{xrayconf.SOCKS_PORT}", "https://api.ipify.org"],
            capture_output=True, text=True, timeout=25)
        if r.returncode == 0 and r.stdout.strip():
            print(f"[+] CONNECTED — exit IP: {r.stdout.strip()}")
            return
        print("[-] tunnel up but no HTTP response (server unreachable from this network?)")
        sys.exit(4)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
