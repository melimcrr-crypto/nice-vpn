#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تولید کانفیگ Xray (حالت پروکسی) — پورت‌ها به‌صورت پارامتر تا در صورت اشغال، خودکار جابجا شوند."""
import json
import os

from . import paths

SOCKS_PORT = 10808
HTTP_PORT = 10809
TUN_DEVICE = "nicev0"   # نام اینترفیس TUN (توسط nicevpn-tun مدیریت می‌شود)
DATA_DIR = paths.DATA_DIR


def build_xray_config(node, loglevel="warning", block_ads=True, direct_ir=True,
                      socks_port=None, http_port=None):
    """ساخت کانفیگ کامل Xray برای یک نود مشخص.

    - inbound: SOCKS5 روی 127.0.0.1:socks_port (+UDP) و HTTP روی 127.0.0.1:http_port
    - routing: لوکال و ایران مستقیم، تبلیغات بلاک
    - قوانین geo فقط وقتی فعال می‌شوند که فایل‌های geoip/geosite موجود باشند
    """
    socks_port = int(socks_port or SOCKS_PORT)
    http_port = int(http_port or HTTP_PORT)

    proxy_out = dict(node.outbound)
    proxy_out["tag"] = "proxy"

    outbounds = [
        proxy_out,
        {"tag": "direct", "protocol": "freedom", "settings": {}},
        {"tag": "block", "protocol": "blackhole", "settings": {}},
    ]

    # لیست‌های private بدون نیاز به geoip.dat
    private_ips = ["127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                   "169.254.0.0/16", "100.64.0.0/10", "224.0.0.0/4", "255.255.255.255/32",
                   "::1/128", "fc00::/7", "fe80::/10"]
    rules = [
        {"type": "field", "ip": private_ips, "outboundTag": "direct"},
    ]
    if direct_ir:
        rules.append({"type": "field", "domain": ["geosite:category-ir"], "outboundTag": "direct"})
        rules.append({"type": "field", "ip": ["geoip:ir"], "outboundTag": "direct"})
    if block_ads:
        rules.append({"type": "field", "domain": ["geosite:category-ads-all"], "outboundTag": "block"})

    config = {
        "log": {"loglevel": loglevel},
        "dns": {"servers": ["1.1.1.1", "8.8.8.8", "localhost"]},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True, "ip": "127.0.0.1"},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
            },
            {
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": http_port,
                "protocol": "http",
                "settings": {},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
            },
        ],
        "outbounds": outbounds,
        "routing": {"domainStrategy": "IPIfNonMatch", "rules": rules},
    }
    return config


def has_geo_files():
    return (os.path.isfile(os.path.join(DATA_DIR, "geoip.dat"))
            and os.path.isfile(os.path.join(DATA_DIR, "geosite.dat")))


def write_xray_config(node, cache_dir, block_ads=True, direct_ir=True,
                      socks_port=None, http_port=None):
    path = os.path.join(cache_dir, "xray-config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_xray_config(node, block_ads=block_ads, direct_ir=direct_ir,
                                    socks_port=socks_port, http_port=http_port),
                  f, ensure_ascii=False, indent=2)
    return path
