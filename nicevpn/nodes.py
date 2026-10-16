#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nodes.py — کانفیگ‌های داخلی Nice VPN
(استخراج‌شده از UFO VPN v2.6.39 Mod — فایل assets/fallback/fast_nodes.txt داخل APK.
 نسخه دیکود‌شده: nicevpn/nodes.json — نسخه خام Base64: configs/fallback-fast_nodes.b64.txt
 هیچ کانال ریموت‌کانفیگی وجود ندارد؛ لیست سرورها کاملاً آفلاین و داخل خود برنامه است.)
"""
import base64
import json
import os
import urllib.parse
import urllib.request

_ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
_NODES_JSON = os.path.join(_ASSETS_DIR, "nodes.json")

_COUNTRY_FLAGS = {"DE": "🇩🇪", "NL": "🇳🇱", "FI": "🇫🇮", "TR": "🇹🇷", "US": "🇺🇸", "AE": "🇦🇪",
                  "GB": "🇬🇧", "FR": "🇫🇷", "RU": "🇷🇺", "AT": "🇦🇹", "SE": "🇸🇪", "CH": "🇨🇭"}

_TYPE_NAMES = {
    "xhttp_reality": "Reality XHTTP",
    "vless_ws": "VLESS WS",
    "grpc_raw": "gRPC",
}


class Node:
    __slots__ = ("name", "address", "port", "city", "country", "cc", "ptype",
                 "protocol", "outbound", "custom")

    def __init__(self, name, address, port, city, country, cc, ptype, protocol, outbound, custom=False):
        self.name = name
        self.address = address
        self.port = port
        self.city = city
        self.country = country
        self.cc = cc
        self.ptype = ptype
        self.protocol = protocol
        self.outbound = outbound  # dict کامل outbound ایکس‌ری
        self.custom = custom

    @property
    def flag(self):
        return _COUNTRY_FLAGS.get(self.cc, "🌐")

    @property
    def type_label(self):
        return _TYPE_NAMES.get(self.ptype, self.ptype)

    def to_dict(self):
        return {
            "name": self.name, "address": self.address, "port": self.port,
            "city": self.city, "country": self.country, "cc": self.cc,
            "ptype": self.ptype, "protocol": self.protocol,
            "outbound": self.outbound, "custom": self.custom,
        }

    @staticmethod
    def from_dict(d):
        return Node(d["name"], d["address"], d["port"], d.get("city", ""),
                    d.get("country", ""), d.get("cc", ""), d.get("ptype", ""),
                    d.get("protocol", "vless"), d["outbound"], d.get("custom", False))


def load_builtin_nodes():
    """خواندن نودهای داخلی از nodes.json (استخراج‌شده از APK)."""
    with open(_NODES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    nodes = []
    for d in data:
        try:
            ob = dict(d["outbound"])
            ob.setdefault("protocol", d.get("protocol", "vless"))
            nodes.append(Node(d["name"], d["address"], int(d["port"]),
                              d.get("city", ""), d.get("country", ""), d.get("cc", ""),
                              d.get("ptype", ""), d.get("protocol", "vless"), ob))
        except Exception:
            continue
    return nodes


# ------------------------------------------------------------------
# ورود کانفیگ دستی (vless:// و vmess://)
# ------------------------------------------------------------------
def parse_vless_url(url):
    """پارس کردن لینک vless:// به یک Node ایکس‌ری."""
    if not url.startswith("vless://"):
        raise ValueError("فقط لینک vless:// پشتیبانی می‌شود")
    body = url[len("vless://"):]
    frag = ""
    if "#" in body:
        body, frag = body.split("#", 1)
    name = urllib.parse.unquote(frag) or "کانفیگ دستی"

    userinfo, _, hostport_q = body.partition("@")
    uuid = userinfo
    netloc, _, query = hostport_q.partition("?")
    host, _, port_s = netloc.rpartition(":")
    # IPv6 ساده پشتیبانی نمی‌شود
    host = host.strip("[]")
    port = int(port_s) if port_s.isdigit() else 443
    q = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

    net = q.get("type", "tcp")
    security = q.get("security", "none")
    stream = {"network": net, "security": security}
    if net == "ws":
        ws = {"path": q.get("path", "/") or "/"}
        if q.get("host"):
            ws["headers"] = {"Host": q["host"]}
        stream["wsSettings"] = ws
    elif net == "grpc":
        stream["grpcSettings"] = {"serviceName": q.get("serviceName", ""),
                                  "multiMode": q.get("mode", "") == "multi"}
    elif net == "http":
        stream["httpSettings"] = {"host": [q.get("host", "")], "path": q.get("path", "/")}
    elif net == "httpupgrade":
        stream["httpupgradeSettings"] = {"host": q.get("host", ""), "path": q.get("path", "/")}
    elif net == "xhttp":
        stream["xhttpSettings"] = {"host": q.get("host", ""), "path": q.get("path", "/"),
                                   "mode": q.get("mode", "auto")}
    if security == "reality":
        stream["realitySettings"] = {
            "serverName": q.get("sni", ""),
            "publicKey": q.get("pbk", ""),
            "shortId": q.get("sid", ""),
            "fingerprint": q.get("fp", "chrome"),
        }
    elif security == "tls":
        stream["tlsSettings"] = {"serverName": q.get("sni", q.get("host", "")),
                                 "fingerprint": q.get("fp", "chrome"),
                                 "allowInsecure": q.get("allowInsecure", "0") == "1"}

    outbound = {
        "protocol": "vless",
        "settings": {"vnext": [{"address": host, "port": port,
                                "users": [{"id": uuid, "encryption": "none", "flow": q.get("flow", "")}]}]},
        "streamSettings": stream,
    }
    return Node(f"⭐ {name}", host, port, "", "", "", "custom_vless", "vless", outbound, custom=True)


def parse_vmess_url(url):
    """پارس ساده vmess:// (base64 json)."""
    b64 = url[len("vmess://"):].strip()
    b64 += "=" * (-len(b64) % 4)
    d = json.loads(base64.b64decode(b64).decode("utf-8", "replace"))
    host = d.get("add", "")
    port = int(d.get("port", 443))
    stream = {"network": d.get("net", "tcp"), "security": d.get("tls", "") or "none"}
    if d.get("net") == "ws":
        ws = {"path": d.get("path", "/")}
        if d.get("host"):
            ws["headers"] = {"Host": d["host"]}
        stream["wsSettings"] = ws
    elif d.get("net") == "grpc":
        stream["grpcSettings"] = {"serviceName": d.get("path", "")}
    if (d.get("tls") or "").lower() == "tls":
        stream["tlsSettings"] = {"serverName": d.get("sni", d.get("host", "")),
                                 "allowInsecure": str(d.get("allowInsecure", "0")) == "1"}
        stream["security"] = "tls"
    outbound = {
        "protocol": "vmess",
        "settings": {"vnext": [{"address": host, "port": port,
                                "users": [{"id": d.get("id", ""), "encryption": "auto",
                                           "flow": d.get("flow", "")}]}]},
        "streamSettings": stream,
    }
    return Node(f"⭐ {d.get('ps', 'vmess')}", host, port, "", "", "", "custom_vmess", "vmess", outbound, custom=True)


def parse_link(url):
    url = url.strip()
    if url.startswith("vless://"):
        return parse_vless_url(url)
    if url.startswith("vmess://"):
        return parse_vmess_url(url)
    raise ValueError("لینک پشتیبانی نمی‌شود (vless:// یا vmess://)")


def fetch_subscription(url):
    """دریافت سابسکریپشن (base64 یا متنی) و پارس همه لینک‌ها."""
    req = urllib.request.Request(url, headers={"User-Agent": "NiceVPN/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    text = None
    try:
        b64 = data.decode("ascii").strip()
        b64 += "=" * (-len(b64) % 4)
        text = base64.b64decode(b64).decode("utf-8", "replace")
        if "://" not in text:
            text = data.decode("utf-8", "replace")
    except Exception:
        text = data.decode("utf-8", "replace")
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vless://") or line.startswith("vmess://"):
            try:
                nodes.append(parse_link(line))
            except Exception:
                pass
    return nodes


if __name__ == "__main__":
    for n in load_builtin_nodes():
        print(n.name, "|", n.address, n.port, "|", n.type_label)
