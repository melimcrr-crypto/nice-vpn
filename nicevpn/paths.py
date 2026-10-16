#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسیرهای برنامه — مستقل از نوع نصب (dev / RPM فدورا / پکیج پرتابل ویندوز)"""
import os
import sys

IS_WIN = sys.platform.startswith("win")
XRAY_NAME = "xray.exe" if IS_WIN else "xray"


def _has_core(base):
    return os.path.isfile(os.path.join(base, "bin", XRAY_NAME))


def _find_app_dir():
    """پیدا کردن ریشه برنامه که پوشه‌های bin/ و data/ داخلش هستند."""
    cands = []
    env = os.environ.get("NICEVPN_HOME")
    if env:
        cands.append(env)
    # مسیرهای نصب استاندارد
    cands += ["/usr/share/nicevpn", "/usr/local/share/nicevpn"]
    # از پوشه پکیج به بالا برو (dev و پکیج پرتابل هر دو پوشش داده می‌شوند)
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        cands.append(d)
        p = os.path.dirname(d)
        if p == d:
            break
        d = p
    for c in cands:
        if _has_core(c):
            return c
    # حالت توسعه بدون باینری — ریشه پروژه
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_DIR = _find_app_dir()
BIN_DIR = os.path.join(APP_DIR, "bin")
DATA_DIR = os.path.join(APP_DIR, "data")
XRAY_BIN = os.path.join(BIN_DIR, XRAY_NAME)
TUN_BIN = os.path.join(BIN_DIR, "hev-socks5-tunnel")

if IS_WIN:
    _base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    CACHE_DIR = os.path.join(_base, "NiceVPN")
else:
    CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "nicevpn")
RUN_DIR = os.path.join(CACHE_DIR, "run")


def ensure_dirs():
    for d in (CACHE_DIR, RUN_DIR):
        os.makedirs(d, exist_ok=True)
