#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تولید کانفیگ Xray (حالت پروکسی) و کانفیگ hev-socks5-tunnel (حالت TUN لینوکس)."""
import json
import os

from . import paths

SOCKS_PORT = 10808
HTTP_PORT = 10809
DATA_DIR = paths.DATA_DIR
TUN_CONFIG = """tunnel:
  name: nicev0
  mtu: 8500

socks5:
  address: 127.0.0.1
  port: %(socks)d
  udp: udp
  tcp: tcp

dns:
  upstream:
    - udp://1.1.1.1:53
    - tcp://8.8.8.8:53

misc:
  log-level: warn
""" % {"socks": SOCKS_PORT}


def build_xray_config(node, loglevel="warning", block_ads=True, direct_ir=True):
    """ساخت کانفیگ کامل Xray برای یک نود مشخص.

    - inbound: SOCKS5 روی 127.0.0.1:10808 (+UDP) و HTTP روی 127.0.0.1:10809
    - routing: لوکال و ایران مستقیم، تبلیغات بلاک
    - قوانین geo فقط وقتی فعال می‌شوند که فایل‌های geoip/geosite موجود باشند
    """
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
                "port": SOCKS_PORT,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True, "ip": "127.0.0.1"},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
            },
            {
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": HTTP_PORT,
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


def write_xray_config(node, cache_dir, block_ads=True, direct_ir=True):
    path = os.path.join(cache_dir, "xray-config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build_xray_config(node, block_ads=block_ads, direct_ir=direct_ir),
                  f, ensure_ascii=False, indent=2)
    return path


def write_tun_config(cache_dir):
    path = os.path.join(cache_dir, "hev-tunnel.yml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TUN_CONFIG)
    return path
