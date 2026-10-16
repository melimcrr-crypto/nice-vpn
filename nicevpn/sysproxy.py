#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تنظیم/بازگردانی پروکسی سیستم — KDE Plasma (kioslaverc)، GNOME (gsettings) و ویندوز (رجیستری)"""
import os
import shutil
import subprocess

from . import paths, xrayconf


def desktop_env():
    if paths.IS_WIN:
        return "windows"
    xdg = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
    if "kde" in xdg or os.environ.get("KDE_FULL_SESSION"):
        return "kde"
    if "gnome" in xdg:
        return "gnome"
    return "unknown"


def _kwriteconfig():
    for c in ("kwriteconfig6", "kwriteconfig5"):
        p = shutil.which(c)
        if p:
            return p
    return None


def _dbus_reload_kde():
    # بروزرسانی زنده KIO بدون ری‌لاگین (بهترین تلاش)
    cmds = [
        ["dbus-send", "--session", "--type=signal", "/KIO/Scheduler",
         "org.kde.KIO.Scheduler.reparseConfiguration", "string:"],
        ["gdbus", "call", "--session", "--dest", "org.kde.kio.Scheduler",
         "--object-path", "/KIO/Scheduler", "--method", "org.kde.KIO.Scheduler.reparseConfiguration", ""],
    ]
    for c in cmds:
        try:
            if subprocess.run(c, capture_output=True, timeout=5).returncode == 0:
                return True
        except Exception:
            continue
    return False


def set_kde_proxy(on, http_port=None, socks_port=None):
    http_port = http_port or xrayconf.HTTP_PORT
    socks_port = socks_port or xrayconf.SOCKS_PORT
    kw = _kwriteconfig()
    if not kw:
        return False, "kwriteconfig پیدا نشد (kde-cli-tools را نصب کنید: sudo dnf install kde-cli-tools)"
    http = f"http://127.0.0.1:{http_port}"
    socks = f"socks://127.0.0.1:{socks_port}"
    cmds = [
        [kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType", "1" if on else "0"],
    ]
    if on:
        cmds += [
            [kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "httpProxy", http],
            [kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "httpsProxy", http],
            [kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ftpProxy", http],
            [kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "socksProxy", socks],
            [kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ReversedException", "false"],
        ]
    ok = True
    for c in cmds:
        r = subprocess.run(c, capture_output=True, text=True)
        if r.returncode != 0:
            ok = False
    _dbus_reload_kde()
    return ok, None


def set_gnome_proxy(on, http_port=None, socks_port=None):
    http_port = http_port or xrayconf.HTTP_PORT
    socks_port = socks_port or xrayconf.SOCKS_PORT

    def g(*args):
        return subprocess.run(["gsettings", *args], capture_output=True, text=True).returncode == 0

    if not shutil.which("gsettings"):
        return False, "gsettings پیدا نشد"
    if on:
        mode_ok = g("set", "org.gnome.system.proxy", "mode", "'manual'")
        g("set", "org.gnome.system.proxy.http", "host", "127.0.0.1")
        g("set", "org.gnome.system.proxy.http", "port", str(http_port))
        g("set", "org.gnome.system.proxy.https", "host", "127.0.0.1")
        g("set", "org.gnome.system.proxy.https", "port", str(http_port))
        g("set", "org.gnome.system.proxy.ftp", "host", "127.0.0.1")
        g("set", "org.gnome.system.proxy.ftp", "port", str(http_port))
        g("set", "org.gnome.system.proxy.socks", "host", "127.0.0.1")
        g("set", "org.gnome.system.proxy.socks", "port", str(socks_port))
        g("set", "org.gnome.system.proxy", "use-same-proxy", "false")
        return mode_ok, None
    g("set", "org.gnome.system.proxy", "mode", "'none'")
    return True, None


def set_windows_proxy(on, http_port=None):
    http_port = http_port or xrayconf.HTTP_PORT
    """پروکسی ویندوز از طریق رجیستری (WinINET) — همه برنامه‌هایی که پروکسی سیستم را رعایت کنند."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 1 if on else 0)
            if on:
                winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{http_port}")
                winreg.SetValueEx(k, "ProxyOverride", 0, winreg.REG_SZ,
                                  "localhost;127.*;10.*;172.16.*;192.168.*;<local>")
        # اطلاع‌رسانی به سیستم برای اعمال فوری
        import ctypes
        internet_set_option = ctypes.windll.wininet.InternetSetOptionW
        internet_set_option(None, 39, None, 0)   # INTERNET_OPTION_SETTINGS_CHANGED
        internet_set_option(None, 37, None, 0)   # INTERNET_OPTION_REFRESH
        return True, None
    except Exception as e:
        return False, str(e)


def set_system_proxy(on, http_port=None, socks_port=None):
    """فعال/غیرفعال کردن پروکسی سیستم. برگرداندن (ok, err)."""
    env = desktop_env()
    if env == "windows":
        return set_windows_proxy(on, http_port=http_port)
    if env == "kde":
        return set_kde_proxy(on, http_port=http_port, socks_port=socks_port)
    if env == "gnome":
        return set_gnome_proxy(on, http_port=http_port, socks_port=socks_port)
    # خارج از دسکتاپ‌های شناخته‌شده: gsettings را هم امتحان کن
    if shutil.which("gsettings"):
        return set_gnome_proxy(on, http_port=http_port, socks_port=socks_port)
    return False, "محیط دسکتاپ پشتیبانی نمی‌شود (KDE/GNOME). از حالت تونل کامل یا تنظیم دستی استفاده کنید."


def env_export_hint(http_port=None, socks_port=None):
    http_port = http_port or xrayconf.HTTP_PORT
    socks_port = socks_port or xrayconf.SOCKS_PORT
    if paths.IS_WIN:
        return (
            f"set http_proxy=http://127.0.0.1:{http_port}\r\n"
            f"set https_proxy=http://127.0.0.1:{http_port}\r\n"
        )
    return (
        f"export http_proxy=http://127.0.0.1:{http_port}\n"
        f"export https_proxy=http://127.0.0.1:{http_port}\n"
        f"export all_proxy=socks5://127.0.0.1:{socks_port}"
    )
