#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI mode — اتصال headless برای تست و اسکریپت‌نویسی"""
import argparse
import sys
import time

from . import nodes as nodes_mod
from . import core as core_mod
from . import sysproxy


def _resolve_node(name_or_index, custom_nodes=None):
    all_nodes = nodes_mod.load_builtin_nodes() + (custom_nodes or [])
    for n in all_nodes:
        if n.name == name_or_index or str(all_nodes.index(n) + 1) == name_or_index:
            return n
    try:
        idx = int(name_or_index) - 1
        return all_nodes[idx]
    except (ValueError, IndexError):
        raise SystemExit(f"سرور «{name_or_index}» پیدا نشد. لیست: nicevpn-cli list")


def cmd_list(args):
    for i, n in enumerate(nodes_mod.load_builtin_nodes(), 1):
        ra = n.real_addr
        print(f"{i:2d}. {n.name:<40} {ra[0]}:{ra[1]}  [{n.type_label}]")
    if args.ping:
        print("\nدر حال تست پینگ (آدرس واقعی اتصال) …")
        for i, n in enumerate(nodes_mod.load_builtin_nodes(), 1):
            ra = n.real_addr
            ms = core_mod.tcp_ping(ra[0], ra[1])
            print(f"{i:2d}. {n.name:<40} {'—' if ms is None else str(ms) + ' ms'}")


def cmd_connect(args):
    core_mod.cleanup_stale()
    node = _resolve_node(args.server)
    core = core_mod.VpnCore(on_state=lambda s, m: print(f"[{s}] {m}"), on_log=lambda l: print("  |", l))
    core.start(node, tun_mode=args.tun)
    if args.proxy:
        ok, err = sysproxy.set_system_proxy(True, http_port=core.http_port,
                                            socks_port=core.socks_port)
        print("پروکسی سیستم:", "فعال شد" if ok else f"خطا: {err}")
    try:
        time.sleep(2)
        ip = core.check_real_ip()
        print(f"IP ظاهری: {ip[0]} ({ip[1]} — {ip[2]})")
    except Exception as e:
        print("تست IP:", e)
    print(f"پورت‌ها: SOCKS {core.socks_port} / HTTP {core.http_port}")
    print("برای قطع: nicevpn-cli disconnect  |  Ctrl+C")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        if args.proxy:
            sysproxy.set_system_proxy(False)
        core.stop()


def cmd_disconnect(args):
    core_mod.cleanup_stale()
    sysproxy.set_system_proxy(False)
    print("قطع شد و پروکسی سیستم بازگردانی شد")


def cmd_status(args):
    alive = core_mod.VpnCore._socks_alive(10808)
    print("پورت SOCKS 10808:", "باز (اتصال فعال)" if alive else "بسته")
    print("پورت SOCKS 20808 (جایگزین):", "باز" if core_mod.VpnCore._socks_alive(20808) else "بسته")


def cmd_addurl(args):
    node = nodes_mod.parse_link(args.url)
    print("کانفیگ پارس شد:", node.name, node.address, node.port)
    print("(افزودن دائمی از طریق GUI → منو ← افزودن کانفیگ)")


def main():
    ap = argparse.ArgumentParser(prog="nice-vpn", description="Nice VPN — کلاینت Xray/VLESS")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="لیست سرورها")
    p.add_argument("--ping", action="store_true", help="تست پینگ TCP")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("connect", help="اتصال به سرور (شماره یا نام)")
    p.add_argument("server", help="شماره یا نام سرور")
    p.add_argument("--proxy", action="store_true", help="پروکسی سیستم هم فعال شود")
    p.add_argument("--tun", action="store_true", help="تونل کامل (pkexec — فقط لینوکس)")
    p.set_defaults(fn=cmd_connect)

    sub.add_parser("disconnect", help="قطع اتصال").set_defaults(fn=cmd_disconnect)
    sub.add_parser("status", help="وضعیت اتصال").set_defaults(fn=cmd_status)

    p = sub.add_parser("addurl", help="تست پارس لینک vless://")
    p.add_argument("url")
    p.set_defaults(fn=cmd_addurl)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
