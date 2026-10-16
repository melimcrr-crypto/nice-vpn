#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""هسته مدیریت Xray — مستقل از UI (لینوکس + ویندوز)

نسبت به نسخه 1.0.0:
- انتخاب خودکار پورت اگر 10808/10809 اشغال باشند
- اعتبارسنجی کانفیگ با «xray run -test» قبل از اجرا
- تأیید اتصال واقعی: بعد از بالا آمدن هسته، یک درخواست HTTP واقعی از داخل تونل
  زده می‌شود؛ تا وقتی ترافیک واقعی رد نشود «متصل» اعلام نمی‌شود.
- حالت TUN واقعی روی لینوکس: tun2socks + اسکریپت روت nicevpn-tun (pkexec)
- چک IP بدون curl (با urllib از داخل تونل)
"""
import collections
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from . import paths
from . import xrayconf

if not paths.IS_WIN:
    import shutil  # noqa: F401  (برای pkill در لینوکس)

ST_STOPPED = "stopped"
ST_CONNECTING = "connecting"
ST_CONNECTED = "connected"
ST_FAILED = "failed"

VERIFY_URLS = [
    "https://www.gstatic.com/generate_204",
    "https://cp.cloudflare.com/generate_204",
    "http://ip-api.com/json/?fields=query,countryCode,city",
]


def ensure_dirs():
    paths.ensure_dirs()


class CoreError(Exception):
    pass


def _port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def find_free_ports(preferred_socks=xrayconf.SOCKS_PORT, preferred_http=xrayconf.HTTP_PORT):
    """پورت SOCKS/HTTP — اگر پیش‌فرض اشغال بود، بازه جایگزین اسکن می‌شود."""
    if _port_free(preferred_socks) and _port_free(preferred_http):
        return preferred_socks, preferred_http
    base = 20000
    for i in range(0, 1000, 10):
        c1, c2 = base + i, base + i + 1
        if _port_free(c1) and _port_free(c2):
            return c1, c2
    raise CoreError("پورت آزاد برای پروکسی پیدا نشد")


def tcp_ping(address, port, timeout=4.0):
    """TCP ping (زمان اتصال) برحسب ms — None یعنی ناموفق."""
    t0 = time.time()
    try:
        s = socket.create_connection((address, port), timeout=timeout)
        s.close()
        return int((time.time() - t0) * 1000)
    except Exception:
        return None


def _proxy_opener(http_port):
    handler = urllib.request.ProxyHandler({
        "http": f"http://127.0.0.1:{http_port}",
        "https": f"http://127.0.0.1:{http_port}",
    })
    op = urllib.request.build_opener(handler)
    op.addheaders = [("User-Agent", "NiceVPN/1.1")]
    return op


def probe_connected(http_port, timeout=10):
    """تأیید ترافیک واقعی از داخل تونل. خروجی: (ok, info, elapsed_ms)"""
    t0 = time.time()
    last = ""
    for url in VERIFY_URLS:
        try:
            r = _proxy_opener(http_port).open(url, timeout=timeout)
            code = r.getcode()
            body = r.read(4096)
            if 200 <= code < 400:
                return True, body[:512].decode("utf-8", "replace"), int((time.time() - t0) * 1000)
            last = f"HTTP {code} از {url}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            continue
    return False, last, int((time.time() - t0) * 1000)


class VpnCore:
    """مدیریت چرخه حیات xray (+ تونل کامل روی لینوکس).

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
        self.tun_up = False
        self.socks_port = xrayconf.SOCKS_PORT
        self.http_port = xrayconf.HTTP_PORT
        self._state = ST_STOPPED
        self._logs = collections.deque(maxlen=60)
        self._log_thread = None
        self._monitor_thread = None
        self._stop_flag = threading.Event()

    # ---------------- state helpers ----------------
    @property
    def state(self):
        return self._state

    @staticmethod
    def _socks_alive(port=None):
        try:
            s = socket.create_connection(("127.0.0.1", port or xrayconf.SOCKS_PORT), timeout=1.5)
            s.close()
            return True
        except Exception:
            return False

    def _emit(self, state, msg):
        self._state = state
        self.on_state(state, msg)

    def _last_logs(self, n=4):
        return "\n".join(list(self._logs)[-n:]) or "(لاگی موجود نیست)"

    # ---------------- start / stop ----------------
    def start(self, node, tun_mode=False):
        if self._state in (ST_CONNECTING, ST_CONNECTED):
            raise CoreError("هسته همین حالا در حال اجراست — اول قطع کنید")
        ensure_dirs()
        if not os.path.isfile(paths.XRAY_BIN):
            raise CoreError(
                "باینری xray پیدا نشد!\n"
                "اگر از سورس اجرا می‌کنید اول این را اجرا کنید:\n"
                "    bash tools/fetch-binaries.sh\n"
                "یا بسته نصبی (RPM/ZIP) را نصب کنید — در بسته‌ها xray داخل خود برنامه است."
            )
        self.node = node
        self.tun_mode = bool(tun_mode) and not paths.IS_WIN
        self.tun_up = False
        self._stop_flag.clear()
        self._logs.clear()

        # پورت‌ها — اگر اشغال بودند جابجا می‌شوند
        try:
            self.socks_port, self.http_port = find_free_ports()
        except CoreError as e:
            self._emit(ST_FAILED, str(e))
            raise
        if (self.socks_port, self.http_port) != (xrayconf.SOCKS_PORT, xrayconf.HTTP_PORT):
            self.on_log(f"[ports] پورت پیش‌فرض اشغال بود → SOCKS {self.socks_port} / HTTP {self.http_port}")

        self._emit(ST_CONNECTING, f"در حال اتصال به {node.name} …")

        geo_ok = xrayconf.has_geo_files()
        cfg_path = xrayconf.write_xray_config(node, paths.CACHE_DIR, block_ads=geo_ok,
                                              direct_ir=geo_ok,
                                              socks_port=self.socks_port, http_port=self.http_port)
        env = dict(os.environ)
        if geo_ok:
            env["XRAY_LOCATION_ASSET"] = paths.DATA_DIR

        # اعتبارسنجی سریع کانفیگ — خطاها همین‌جا واضح اعلام می‌شوند
        try:
            t = subprocess.run([paths.XRAY_BIN, "run", "-test", "-c", cfg_path],
                               capture_output=True, text=True, timeout=25, env=env)
        except Exception as e:
            raise CoreError(f"اجرای تست xray ناموفق بود: {e}")
        if t.returncode != 0:
            out = (t.stdout or "") + (t.stderr or "")
            tail = "\n".join(out.strip().splitlines()[-6:])
            raise CoreError("کانفیگ Xray رد شد:\n" + tail)

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
                    self._logs.append(line)
                    self.on_log(line)
            # EOF یعنی پروسه بسته شده
            if not self._stop_flag.is_set() and self._state != ST_STOPPED:
                self._emit(ST_FAILED, "هسته xray ناگهانی بسته شد.\n" + self._last_logs(3))
        except Exception:
            pass

    def _monitor_start(self):
        deadline = time.time() + 10
        while time.time() < deadline and not self._stop_flag.is_set():
            if self.xray_proc and self.xray_proc.poll() is not None:
                return  # _pump_logs خودش FAILED را اعلام می‌کند
            if self._socks_alive(self.socks_port):
                break
            time.sleep(0.3)
        else:
            if not self._stop_flag.is_set() and self._state == ST_CONNECTING:
                self._emit(ST_FAILED, "پورت پروکسی بالا نیامد (تایم‌اوت).\n" + self._last_logs(3))
            return
        if self._stop_flag.is_set() or self._state != ST_CONNECTING:
            return

        # تونل کامل (لینوکس): موازی با تست ترافیک بالا می‌آید
        if self.tun_mode:
            threading.Thread(target=self._start_tun, daemon=True).start()

        # ---------- تأیید ترافیک واقعی ----------
        self.on_log("[verify] تست ترافیک واقعی از داخل تونل …")
        ok, info, ms = probe_connected(self.http_port, timeout=12)
        if self._stop_flag.is_set() or self._state == ST_STOPPED:
            return
        if ok:
            tun_note = " — تونل کامل فعال" if self.tun_up else ""
            self._emit(ST_CONNECTED, f"متصل ✔ ({ms} ms){tun_note}")
            threading.Thread(target=self._fetch_ip, daemon=True).start()
        else:
            self.on_log("[verify] خطا: " + info)
            self._emit(ST_FAILED,
                       "هسته بالا آمد ولی ترافیک رد شد — این سرور از شبکه‌ی شما جواب نمی‌دهد.\n"
                       "سرور دیگری انتخاب کنید یا از منو «اتصال خودکار به بهترین سرور» را بزنید.")

    def _fetch_ip(self):
        try:
            r = _proxy_opener(self.http_port).open(
                "http://ip-api.com/json/?fields=query,countryCode,city", timeout=12)
            import json as _j
            j = _j.loads(r.read(4096).decode("utf-8", "replace"))
            ip, cc, city = j.get("query"), j.get("countryCode"), j.get("city")
            if self._state == ST_CONNECTED and ip:
                tun_note = " — تونل کامل فعال" if self.tun_up else ""
                self.on_state(ST_CONNECTED,
                              f"متصل ✔ — IP: {ip} ({cc} — {city}){tun_note}")
        except Exception:
            pass

    # ---------------- TUN (فقط لینوکس) ----------------
    def _start_tun(self):
        helper = paths.find_tun_helper()
        if not os.path.isfile(paths.TUN_BIN) or not helper:
            self.on_log("[tun] تونل کامل نصب نیست — فعلاً فقط حالت پروکسی فعال است")
            return
        srv, _sport = self.node.real_addr
        cmd = ["pkexec", helper, paths.TUN_BIN, xrayconf.TUN_DEVICE,
               str(self.socks_port), srv]
        self.on_log("[tun] درخواست رمز مدیر برای تونل کامل …")
        try:
            self.tun_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             start_new_session=True)
        except OSError as e:
            self.on_log(f"[tun] اجرای تونل ناموفق بود: {e}")
            return
        threading.Thread(target=self._pump_tun_logs, daemon=True).start()
        # صبر کوتاه برای آماده شدن
        for _ in range(40):
            if self.tun_proc.poll() is not None:
                code = self.tun_proc.returncode
                if code in (126, 127):
                    self.on_log("[tun] رمز مدیر داده نشد — تونل کامل غیرفعال ماند")
                else:
                    self.on_log(f"[tun] تونل با کد {code} بسته شد (فقط پروکسی فعال است)")
                return
            if os.path.isdir(f"/sys/class/net/{xrayconf.TUN_DEVICE}"):
                self.tun_up = True
                self.on_log("[tun] تونل کامل (TUN) فعال شد — کل ترافیک سیستم از تونل رد می‌شود")
                return
            time.sleep(0.25)
        self.on_log("[tun] اینترفیس TUN آماده نشد (فقط پروکسی فعال است)")

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
            # pkexec اسکریپت روت را جدا اجرا می‌کند — trap داخل خودش روتینگ را برمی‌گرداند
            subprocess.run(["pkill", "-f", "nicevpn-tun"], capture_output=True)
            subprocess.run(["pkill", "-f", "tun2socks.*nicev0"], capture_output=True)
        self.xray_proc = None
        self.tun_proc = None
        self.tun_up = False
        self._state = ST_STOPPED
        self.on_state(ST_STOPPED, "قطع شد")

    # ---------------- ابزار تست ----------------
    def check_real_ip(self, timeout=15):
        """IP ظاهری از طریق تونل (بدون curl — با urllib)."""
        try:
            r = _proxy_opener(self.http_port).open(
                "http://ip-api.com/json/?fields=query,countryCode,city", timeout=timeout)
            import json as _j
            j = _j.loads(r.read(4096).decode("utf-8", "replace"))
            return j.get("query"), j.get("countryCode"), j.get("city")
        except Exception as e:
            raise CoreError(f"تست IP ناموفق بود: {e}")


def cleanup_stale():
    """کشتن پروسه‌های به‌جامانده از اجرای قبلی."""
    if paths.IS_WIN:
        subprocess.run(["taskkill", "/IM", "xray.exe", "/F"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "xray run -c .*nicevpn"], capture_output=True)
        subprocess.run(["pkill", "-f", "xray run -c .*xray-config.json"], capture_output=True)
        subprocess.run(["pkill", "-f", "nicevpn-tun"], capture_output=True)
        subprocess.run(["pkill", "-f", "tun2socks.*nicev0"], capture_output=True)
