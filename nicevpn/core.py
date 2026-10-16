#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""هسته مدیریت Xray — مستقل از UI (لینوکس + ویندوز)"""
import os
import signal
import socket
import subprocess
import sys
import threading
import time

from . import paths
from . import xrayconf

if not paths.IS_WIN:
    import shutil  # noqa: F401  (برای pkill در لینوکس)

ST_STOPPED = "stopped"
ST_CONNECTING = "connecting"
ST_CONNECTED = "connected"


def ensure_dirs():
    paths.ensure_dirs()


class CoreError(Exception):
    pass


def tcp_ping(address, port, timeout=4.0):
    """TCP ping (زمان اتصال) برحسب ms — None یعنی ناموفق."""
    t0 = time.time()
    try:
        s = socket.create_connection((address, port), timeout=timeout)
        s.close()
        return int((time.time() - t0) * 1000)
    except Exception:
        return None


class VpnCore:
    """مدیریت چرخه حیات xray (و در لینوکس: اختیاری hev-socks5-tunnel برای TUN).

    callback ها:
        on_state(state:str, message:str)
        on_log(line:str)
    """

    def __init__(self, on_state=None, on_log=None):
        self.on_state = on_state or (lambda s, m: None)
        self.on_log = on_log or (lambda l: None)
        self.xray_proc = None
        self.tun_proc = None
        self.node = None
        self.tun_mode = False
        self._log_thread = None
        self._monitor_thread = None
        self._stop_flag = threading.Event()

    # ---------------- state helpers ----------------
    @property
    def state(self):
        if self.xray_proc and self.xray_proc.poll() is None:
            return ST_CONNECTED if self._socks_alive() else ST_CONNECTING
        return ST_STOPPED

    @staticmethod
    def _socks_alive():
        try:
            s = socket.create_connection(("127.0.0.1", xrayconf.SOCKS_PORT), timeout=1.5)
            s.close()
            return True
        except Exception:
            return False

    # ---------------- start / stop ----------------
    def start(self, node, tun_mode=False):
        if self.state != ST_STOPPED:
            raise CoreError("هسته همین حالا در حال اجراست")
        ensure_dirs()
        if not os.path.isfile(paths.XRAY_BIN):
            raise CoreError(
                "باینری xray پیدا نشد!\n"
                "اگر از سورس اجرا می‌کنید اول این را اجرا کنید:\n"
                "    bash tools/fetch-binaries.sh\n"
                "یا بسته نصبی (RPM/ZIP) را نصب کنید."
            )
        self.node = node
        # حالت TUN فقط در لینوکس معنا دارد
        self.tun_mode = bool(tun_mode) and not paths.IS_WIN
        self._stop_flag.clear()
        self.on_state(ST_CONNECTING, f"در حال اتصال به {node.name} …")

        geo_ok = xrayconf.has_geo_files()

        cfg_path = xrayconf.write_xray_config(node, paths.CACHE_DIR, block_ads=geo_ok, direct_ir=geo_ok)
        env = dict(os.environ)
        if geo_ok:
            env["XRAY_LOCATION_ASSET"] = paths.DATA_DIR

        try:
            kwargs = {}
            if not paths.IS_WIN:
                kwargs["start_new_session"] = True
            self.xray_proc = subprocess.Popen(
                [paths.XRAY_BIN, "run", "-c", cfg_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, **kwargs,
            )
        except OSError as e:
            raise CoreError(f"اجرای xray ناموفق بود: {e}")

        self._log_thread = threading.Thread(target=self._pump_logs, daemon=True)
        self._log_thread.start()

        # حالت TUN (فقط لینوکس): تونل کامل با hev-socks5-tunnel (نیازمند root از طریق pkexec)
        if self.tun_mode:
            tun_cfg = xrayconf.write_tun_config(paths.CACHE_DIR)
            if not os.path.isfile(paths.TUN_BIN):
                self.stop()
                raise CoreError("باینری hev-socks5-tunnel نصب نیست.\nبا install.sh --with-tun نصبش کنید.")
            try:
                self.tun_proc = subprocess.Popen(
                    ["pkexec", paths.TUN_BIN, "-c", tun_cfg],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except OSError as e:
                self.stop()
                raise CoreError(f"اجرای تونل TUN ناموفق بود: {e}")

        # مانیتور: صبر تا ساکت شدن پورت ساکس
        self._monitor_thread = threading.Thread(target=self._monitor_start, daemon=True)
        self._monitor_thread.start()

    def _pump_logs(self):
        proc = self.xray_proc
        if not proc or not proc.stdout:
            return
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    self.on_log(line)
        except Exception:
            pass

    def _monitor_start(self):
        deadline = time.time() + 12
        while time.time() < deadline and not self._stop_flag.is_set():
            if self.xray_proc.poll() is not None:
                self.on_state(ST_STOPPED, "پروسه xray بسته شد — کانفیگ یا شبکه را بررسی کنید")
                return
            if self._socks_alive():
                self.on_state(ST_CONNECTED, "اتصال برقرار است")
                if self.tun_mode and self.tun_proc:
                    t = threading.Thread(target=self._pump_tun_logs, daemon=True)
                    t.start()
                return
            time.sleep(0.4)
        if not self._stop_flag.is_set():
            self.on_state(ST_STOPPED, "اتصال زمان‌بر شد (تایم‌اوت) — سرور دیگری را امتحان کنید")

    def _pump_tun_logs(self):
        proc = self.tun_proc
        if not proc or not proc.stdout:
            return
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    self.on_log("[tun] " + line)
        except Exception:
            pass

    def stop(self):
        self._stop_flag.set()
        for proc in (self.tun_proc, self.xray_proc):
            if proc and proc.poll() is None:
                if paths.IS_WIN:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                else:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except Exception:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
        # صبر برای خروج تمیز
        deadline = time.time() + 4
        for proc in (self.tun_proc, self.xray_proc):
            while proc and proc.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
        if not paths.IS_WIN:
            # pkexec ممکن است پروسه والد جدا بگذارد
            subprocess.run(["pkill", "-f", "hev-socks5-tunnel"], capture_output=True)
        self.xray_proc = None
        self.tun_proc = None
        self.on_state(ST_STOPPED, "قطع شد")

    # ---------------- ابزار تست ----------------
    def check_real_ip(self, timeout=15):
        """برای تست اتصال: IP ظاهری از طریق ساکس (با curl)."""
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", str(timeout),
                 "--socks5-hostname", f"127.0.0.1:{xrayconf.SOCKS_PORT}",
                 "http://ip-api.com/json/?fields=query,countryCode,city"],
                capture_output=True, text=True, timeout=timeout + 5)
            import json as _j
            j = _j.loads(r.stdout)
            return j.get("query"), j.get("countryCode"), j.get("city")
        except FileNotFoundError:
            raise CoreError("curl برای تست IP پیدا نشد")
        except Exception as e:
            raise CoreError(f"تست IP ناموفق بود: {e}")


def cleanup_stale():
    """کشتن پروسه‌های به‌جامانده از اجرای قبلی."""
    if paths.IS_WIN:
        subprocess.run(["taskkill", "/IM", "xray.exe", "/F"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "xray run -c .*nicevpn"], capture_output=True)
        subprocess.run(["pkill", "-f", "hev-socks5-tunnel"], capture_output=True)
