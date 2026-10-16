#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI اصلی Nice VPN — PySide6 (سازگار با KDE Plasma/Breeze و ویندوز، تم تیره، RTL فارسی)"""
import os
import subprocess
import sys

from PySide6.QtCore import Qt, QTimer, QSettings, QSize, QRectF, Signal, QObject
from PySide6.QtGui import (QAction, QColor, QFont, QFontDatabase, QIcon, QLinearGradient,
                           QPainter, QPainterPath, QPen, QBrush, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy,
    QSystemTrayIcon, QPlainTextEdit, QVBoxLayout, QWidget, QFileDialog, QLineEdit,
)

from . import nodes as nodes_mod
from . import core as core_mod
from . import paths
from . import sysproxy
from . import __version__
from .core import ST_STOPPED, ST_CONNECTING, ST_CONNECTED, ST_FAILED
from .xrayconf import SOCKS_PORT, HTTP_PORT

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ICONS = os.path.join(ASSETS, "icons")

STYLE = """
* { font-size: 14px; }
QMainWindow, QWidget#root { background: #0b1020; }
QLabel { color: #cbd5e1; }
#title { font-size: 20px; font-weight: 800; color: #f1f5f9; }
#subtitle { font-size: 12px; color: #64748b; }
#statusLabel { font-size: 13px; color: #94a3b8; }
QFrame#card {
    background: #101a2e;
    border: 1px solid #1e293b;
    border-radius: 16px;
}
QListWidget {
    background: transparent; border: none; outline: none;
}
QListWidget::item { margin: 4px 2px; }
QFrame#serverCard {
    background: #0f152c;
    border: 1px solid #1c2547;
    border-radius: 12px;
}
QFrame#serverCard:hover { border: 1px solid #7c6cf0; }
QFrame#serverCard[selected="true"] {
    background: #171a38;
    border: 1px solid #8b5cf6;
}
QPushButton#ghost {
    background: #16203a; color: #94a3b8;
    border: 1px solid #233250; border-radius: 10px;
    padding: 8px 14px; font-weight: 600;
}
QPushButton#ghost:hover { background: #1c2b47; color: #e2e8f0; }
QPushButton#ghost:pressed { background: #14203a; }
QPlainTextEdit#logs {
    background: #070c18; color: #a78bfa; border: 1px solid #16233c;
    border-radius: 12px; font-family: monospace; font-size: 11.5px;
}
QCheckBox { color: #94a3b8; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid #2b3b5c; background: #101a2e;
}
QCheckBox::indicator:checked { background: #7c3aed; border-color: #8b5cf6; }
QMenu { background: #101a2e; color: #cbd5e1; border: 1px solid #233250; border-radius: 10px; }
QMenu::item:selected { background: #7c3aed; }
QToolTip { background: #101a2e; color: #e2e8f0; border: 1px solid #233250; }
"""


def load_font(app):
    for f in ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"):
        p = os.path.join(ASSETS, "fonts", f)
        if os.path.isfile(p):
            QFontDatabase.addApplicationFont(p)
    reg = os.path.join(ASSETS, "fonts", "Vazirmatn-Regular.ttf")
    fams = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(reg)) if os.path.isfile(reg) else []
    if fams:
        app.setFont(QFont(fams[0], 10))
    elif QFontDatabase.hasFamily("Vazirmatn"):
        app.setFont(QFont("Vazirmatn", 10))


def app_icon():
    for name in ("logo-256.png", "logo-512.png", "logo.svg"):
        p = os.path.join(ICONS, name)
        if os.path.isfile(p):
            return QIcon(p)
    return QIcon()


class ConnectBtn(QWidget):
    """دکمه دایره‌ای بزرگ با حلقه متحرک"""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(190, 190)
        self._phase = "stopped"   # stopped / connecting / connected
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("کلیک برای اتصال/قطع")

    def _tick(self):
        if self._phase == "connecting":
            self._angle = (self._angle + 6) % 360
            self.update()

    def set_phase(self, phase):
        self._phase = phase
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # هاله
        glow = QRadialGradient(cx, cy, w / 2)
        if self._phase == "connected":
            glow.setColorAt(0.0, QColor(34, 197, 94, 90))
        elif self._phase == "connecting":
            glow.setColorAt(0.0, QColor(234, 179, 8, 70))
        else:
            glow.setColorAt(0.0, QColor(139, 92, 246, 60))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(0, 0, w, h))

        # بدنه دکمه
        g = QLinearGradient(0, 0, w, h)
        if self._phase == "connected":
            g.setColorAt(0, QColor("#15803d")); g.setColorAt(1, QColor("#22c55e"))
        elif self._phase == "connecting":
            g.setColorAt(0, QColor("#a16207")); g.setColorAt(1, QColor("#eab308"))
        else:
            g.setColorAt(0, QColor("#312e81")); g.setColorAt(1, QColor("#6d28d9"))
        p.setBrush(QBrush(g))
        pen = QPen(QColor("#8b5cf6") if self._phase != "connecting" else QColor("#facc15"), 3)
        p.setPen(pen)
        p.drawEllipse(QRectF(18, 18, w - 36, h - 36))

        # حلقه چرخان
        if self._phase == "connecting":
            arc_pen = QPen(QColor("#fde68a"), 5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(arc_pen)
            r = w / 2 - 10
            p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), -self._angle * 16, 100 * 16)

        # آیکون پاور
        p.setPen(Qt.NoPen)
        icon_col = QColor("#ecfdf5") if self._phase == "connected" else QColor("#ede9fe")
        path = QPainterPath()
        # خط پاور
        pp = QPainterPath()
        pp.moveTo(cx, cy - 26)
        pp.lineTo(cx, cy - 4)
        p.setPen(QPen(icon_col, 5, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(pp)
        # قوس
        arc = QPainterPath()
        arc.moveTo(cx - 20, cy - 18)
        arc.arcTo(QRectF(cx - 22, cy - 22, 44, 44), 130, -260)
        p.setBrush(Qt.NoBrush)
        p.drawPath(arc)


class ServerCard(QFrame):
    def __init__(self, node, ping_ms=None, parent=None):
        super().__init__(parent)
        self.node = node
        self.setObjectName("serverCard")
        self.setProperty("selected", "false")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        right = QVBoxLayout()
        name = QLabel(node.name)
        name.setStyleSheet("color:#f1f5f9; font-weight:700; font-size:14.5px; border:none; background:transparent;")
        meta = QLabel(f"{node.real_addr[0]}:{node.real_addr[1]}  •  {node.type_label}")
        meta.setStyleSheet("color:#64748b; font-size:11.5px; border:none; background:transparent;")
        right.addWidget(name)
        right.addWidget(meta)
        lay.addLayout(right, 1)

        self.ping_lbl = QLabel("…" if ping_ms is None else self._fmt(ping_ms))
        self.ping_lbl.setStyleSheet("color:#64748b; font-weight:700; border:none; background:transparent;")
        self.ping_lbl.setAlignment(Qt.AlignCenter)
        self.ping_lbl.setFixedWidth(70)
        lay.addWidget(self.ping_lbl)
        self.set_ping(ping_ms)

    @staticmethod
    def _fmt(ms):
        return "—" if ms is None else f"{ms} ms"

    def set_ping(self, ms):
        self.ping_lbl.setText(self._fmt(ms))
        if ms is None:
            col = "#64748b"
        elif ms < 150:
            col = "#34d399"
        elif ms < 400:
            col = "#fbbf24"
        else:
            col = "#f87171"
        self.ping_lbl.setStyleSheet(f"color:{col}; font-weight:800; border:none; background:transparent;")

    def set_selected(self, sel):
        self.setProperty("selected", "true" if sel else "false")
        # force re-style
        self.style().unpolish(self)
        self.style().polish(self)


class UiBridge(QObject):
    """پل بین‌نخی — ورکرهای پایتون (پینگ/سابسکریپشن/هسته) از طریق این سیگنال‌ها
    به رشته گرافیکی می‌روند (QueuedConnection خودکار).
    دلیل مهم: QTimer.singleShot از رشته‌ی غیر-Qt هرگز اجرا نمی‌شود؛ همین باگ باعث
    می‌شد پینگ، لاگ و حتی وضعیت «متصل» در نسخه‌های قبلی به رابط کاربری نرسد."""

    pingDone = Signal(list)          # نتایج تست پینگ همه سرورها
    stateChanged = Signal(str, str)  # (state, message) از هسته
    logLine = Signal(str)            # خط لاگ از هسته
    statusMsg = Signal(str)          # پیام وضعیت از ورکرها
    warnBox = Signal(str, str)       # (عنوان، متن) جعبه هشدار
    infoBox = Signal(str, str)       # (عنوان، متن) جعبه اطلاعات
    subNodes = Signal(list)          # نودهای دریافتی از سابسکریپشن


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nice VPN")
        self.resize(460, 720)
        self.setMinimumSize(QSize(420, 640))
        self.setLayoutDirection(Qt.RightToLeft)

        self.settings = QSettings("NiceVPN", "NiceVPN")
        self.core = core_mod.VpnCore(on_state=self._on_state, on_log=self._on_log)
        self.custom_nodes = []
        self._load_custom_nodes()
        self.all_nodes = nodes_mod.load_builtin_nodes() + self.custom_nodes
        self.selected_idx = int(self.settings.value("last_server", 0))
        if not (0 <= self.selected_idx < len(self.all_nodes)):
            self.selected_idx = 0
        self.auto_proxy = self.settings.value("auto_proxy", "1") == "1"
        self.want_tun = self.settings.value("tun_mode", "0") == "1"
        self._proxy_active = False  # برای جلوگیری از ست‌های تکراری پروکسی سیستم

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(10)

        # ---------- هدر ----------
        head = QHBoxLayout()
        logo_lbl = QLabel()
        logo_path = os.path.join(ICONS, "logo-128.png")
        if os.path.isfile(logo_path):
            logo_lbl.setPixmap(QPixmap(logo_path).scaled(
                52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        head.addWidget(logo_lbl)
        ht = QVBoxLayout()
        t1 = QLabel("Nice VPN"); t1.setObjectName("title")
        t2 = QLabel("با هسته Xray — بدون تبلیغات، بدون عضویت اجباری"); t2.setObjectName("subtitle")
        ht.addWidget(t1); ht.addWidget(t2)
        head.addLayout(ht, 1)
        v.addLayout(head)

        # ---------- دکمه اتصال ----------
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        self.btn = ConnectBtn()
        wrap.addWidget(self.btn)
        wrap.addStretch(1)
        v.addLayout(wrap)

        self.status = QLabel("آماده — یک سرور انتخاب کنید و دکمه را بزنید")
        self.status.setObjectName("statusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        v.addWidget(self.status)

        info = QLabel(f"SOCKS5: 127.0.0.1:{SOCKS_PORT}   •   HTTP: 127.0.0.1:{HTTP_PORT}")
        info.setObjectName("subtitle")
        info.setAlignment(Qt.AlignCenter)
        v.addWidget(info)
        self.info_ports = info

        # ---------- گزینه‌ها ----------
        opt = QHBoxLayout()
        self.chk_proxy = QCheckBox("پروکسی سیستم خودکار")
        self.chk_proxy.setChecked(self.auto_proxy)
        self.chk_proxy.toggled.connect(self._on_auto_proxy)
        opt.addWidget(self.chk_proxy)
        self.chk_tun = QCheckBox("تونل کامل سیستم (رمز مدیر)")
        self.chk_tun.setChecked(self.want_tun)
        self.chk_tun.setToolTip("کل ترافیک سیستم از تونل رد می‌شود (tun2socks + pkexec — روت‌ها خودکار برمی‌گردند)")
        self.chk_tun.toggled.connect(self._on_tun)
        # TUN فقط در لینوکس
        self.chk_tun.setVisible(not paths.IS_WIN)
        opt.addWidget(self.chk_tun)
        v.addLayout(opt)

        # ---------- لیست سرورها ----------
        v.addWidget(self._sep())
        cap = QLabel("سرورها")
        cap.setStyleSheet("color:#c4b5fd; font-weight:800; font-size:13px;")
        v.addWidget(cap)

        self.listw = QListWidget()
        v.addWidget(self.listw, 1)
        self._cards = []
        self._fill_servers()
        self.listw.currentRowChanged.connect(self._on_select)

        # ---------- دکمه‌ها ----------
        btns = QHBoxLayout()
        b_ping = QPushButton("تست پینگ"); b_ping.setObjectName("ghost")
        b_ping.clicked.connect(self.ping_all)
        btns.addWidget(b_ping)

        menu_btn = QPushButton("☰ منو"); menu_btn.setObjectName("ghost")
        m = QMenu(self)
        m.addAction("اتصال خودکار (بهترین سرور)", self.auto_connect)
        m.addSeparator()
        m.addAction("افزودن کانفیگ از کلیپ‌بورد (vless/vmess)", self._add_from_clip)
        m.addAction("افزودن از فایل…", self._add_from_file)
        m.addAction("سابسکریپشن (URL)…", self._add_sub)
        m.addSeparator()
        m.addAction("بررسی IP و لوکیشن فعلی", self._check_ip)
        m.addAction("کپی تنظیمات ترمینال", self._copy_env)
        m.addSeparator()
        m.addAction("تشخیص مشکلات", self._diag)
        m.addSeparator()
        m.addAction("حذف کانفیگ‌های دستی", self._clear_custom)
        m.addAction("درباره Nice VPN", self._about)
        menu_btn.setMenu(m)
        btns.addWidget(menu_btn)

        b_logs = QPushButton("لاگ‌ها"); b_logs.setObjectName("ghost")
        b_logs.setCheckable(True)
        b_logs.toggled.connect(lambda on: self.logs.setVisible(on))
        btns.addWidget(b_logs)
        v.addLayout(btns)

        self.logs = QPlainTextEdit(); self.logs.setObjectName("logs")
        self.logs.setReadOnly(True)
        self.logs.setFixedHeight(110)
        self.logs.setVisible(False)
        v.addWidget(self.logs)

        # ---------- tray ----------
        self.tray = QSystemTrayIcon(app_icon(), self)
        tm = QMenu()
        self.tray_toggle = tm.addAction("اتصال", self.toggle_connect)
        tm.addAction("نمایش / مخفی", self._toggle_visible)
        tm.addSeparator()
        tm.addAction("خروج", self._quit)
        self.tray.setContextMenu(tm)
        self.tray.activated.connect(self._tray_activated)
        self.tray.setToolTip("Nice VPN")
        self.tray.show()

        self.btn.clicked.connect(self.toggle_connect)

        # ---------- پل بین‌نخی (بدون این، پیام رشته‌های دیگر به UI نمی‌رسد) ----------
        self.bridge = UiBridge(self)
        self.bridge.pingDone.connect(self._apply_pings)
        self.bridge.stateChanged.connect(self._apply_state_ui)
        self.bridge.logLine.connect(self.logs.appendPlainText)
        self.bridge.statusMsg.connect(self.status.setText)
        self.bridge.warnBox.connect(self._show_warn)
        self.bridge.infoBox.connect(self._show_info)
        self.bridge.subNodes.connect(self._add_nodes)

        self._apply_state_ui("stopped", "آماده")
        self.ping_all(silent=True)

    # ---------------- helpers ----------------
    def _sep(self):
        s = QFrame(); s.setFrameShape(QFrame.HLine); s.setStyleSheet("color:#16233c;")
        return s

    def _fill_servers(self):
        self.listw.clear()
        self._cards = []
        for i, n in enumerate(self.all_nodes):
            it = QListWidgetItem()
            it.setSizeHint(QSize(0, 62))
            self.listw.addItem(it)
            card = ServerCard(n)
            card.set_selected(i == self.selected_idx)
            self.listw.setItemWidget(it, card)
            self._cards.append(card)
        if self.all_nodes:
            self.listw.setCurrentRow(self.selected_idx)

    def _on_select(self, row):
        if row < 0:
            return
        self.selected_idx = row
        self.settings.setValue("last_server", row)
        for i, c in enumerate(self._cards):
            c.set_selected(i == row)

    # ---------------- ping ----------------
    def ping_all(self, silent=False):
        def worker():
            import concurrent.futures as cf
            # پینگ به آدرسِ «واقعیِ» اتصال (از داخل outbound) — نه آدرس نمایشی لیست
            with cf.ThreadPoolExecutor(max_workers=8) as ex:
                results = list(ex.map(
                    lambda n: core_mod.tcp_ping(n.real_addr[0], n.real_addr[1], timeout=3),
                    self.all_nodes))
            self.bridge.pingDone.emit(results)
        import threading
        threading.Thread(target=worker, daemon=True).start()
        if not silent:
            self.status.setText("در حال تست پینگ …")

    def _apply_pings(self, results):
        for card, ms in zip(self._cards, results):
            card.set_ping(ms)
        if self.core.state == "stopped":
            self.status.setText("آماده — یک سرور انتخاب کنید و دکمه را بزنید")

    # ---------------- connect ----------------
    def toggle_connect(self):
        if self.core.state in (ST_STOPPED, ST_FAILED):
            node = self.all_nodes[self.selected_idx]
            self._proxy_active = False
            try:
                self.core.start(node, tun_mode=self.chk_tun.isChecked())
            except core_mod.CoreError as e:
                QMessageBox.critical(self, "خطا", str(e))
        else:
            self.core.stop()
            if self.chk_proxy.isChecked():
                ok, err = sysproxy.set_system_proxy(False)
                if not ok:
                    self._on_log(f"[proxy] {err}")
            self._proxy_active = False

    # ---------------- اتصال خودکار به بهترین سرور ----------------
    def auto_connect(self):
        if self.core.state in (ST_CONNECTING, ST_CONNECTED):
            self.status.setText("اول قطع کنید — اتصال فعلی باز است")
            return
        self.status.setText("اتصال خودکار — پینگ همه سرورها …")
        import threading
        import time as _t

        def worker():
            import concurrent.futures as cf
            nodes = self.all_nodes
            with cf.ThreadPoolExecutor(max_workers=8) as ex:
                pings = list(ex.map(
                    lambda n: core_mod.tcp_ping(n.real_addr[0], n.real_addr[1], timeout=3),
                    nodes))
            order = sorted(range(len(nodes)), key=lambda i: (pings[i] is None, pings[i] or 99999))
            for i in order:
                node = nodes[i]
                ping_s = "—" if pings[i] is None else f"{pings[i]} ms"
                self.bridge.statusMsg.emit(f"اتصال خودکار: {node.name} ({ping_s}) …")
                try:
                    self.core.start(node, tun_mode=False)  # در تلاش‌های خودکار فقط پروکسی
                except core_mod.CoreError as e:
                    self._on_log(f"[auto] {node.name}: {e}")
                    continue
                deadline = _t.time() + 35
                while _t.time() < deadline:
                    if self.core.state in (ST_CONNECTED, ST_FAILED, ST_STOPPED):
                        break
                    _t.sleep(0.5)
                if self.core.state == ST_CONNECTED:
                    self.bridge.statusMsg.emit("اتصال خودکار موفق بود ✔")
                    return
                try:
                    self.core.stop()
                except Exception:
                    pass
                _t.sleep(1.2)
            self.bridge.warnBox.emit(
                "اتصال خودکار",
                "هیچ سروری جواب نداد.\nاینترنت و فیلترشکن فعلی را بررسی کنید و دوباره امتحان کنید.")

        threading.Thread(target=worker, daemon=True).start()

    def _on_state(self, state, msg):
        self.bridge.stateChanged.emit(state, msg)

    def _apply_state_ui(self, state, msg):
        self.status.setText(msg)
        self.btn.set_phase(state if state in (ST_CONNECTING, ST_CONNECTED) else ST_STOPPED)
        if state == ST_CONNECTED:
            self.tray_toggle.setText("قطع اتصال")
            self.tray.setToolTip("Nice VPN — متصل")
            self.info_ports.setText(
                f"SOCKS5: 127.0.0.1:{self.core.socks_port}   •   HTTP: 127.0.0.1:{self.core.http_port}")
            if self.chk_proxy.isChecked() and not (self.chk_tun.isVisible() and self.chk_tun.isChecked()) \
                    and not self._proxy_active:
                self._proxy_active = True
                ok, err = sysproxy.set_system_proxy(True, http_port=self.core.http_port,
                                                    socks_port=self.core.socks_port)
                if not ok:
                    self._on_log(f"[proxy] {err}")
                else:
                    self._on_log("[proxy] پروکسی سیستم فعال شد")
        elif state == ST_STOPPED:
            self.tray_toggle.setText("اتصال")
            self.info_ports.setText(
                f"SOCKS5: 127.0.0.1:{SOCKS_PORT}   •   HTTP: 127.0.0.1:{HTTP_PORT}")
        elif state == ST_FAILED:
            self.tray_toggle.setText("اتصال")
            self.status.setStyleSheet("color:#f87171;")
            self.logs.setVisible(True)
            QTimer.singleShot(8000, lambda: self.status.setStyleSheet(""))
            QTimer.singleShot(8000, lambda: self.status.setText(
                "آماده — سرور دیگری را امتحان کنید یا از منو «اتصال خودکار» را بزنید"))

    def _show_warn(self, title, text):
        QMessageBox.warning(self, title, text)

    def _show_info(self, title, text):
        QMessageBox.information(self, title, text)

    def _on_log(self, line):
        self.bridge.logLine.emit(line)

    # ---------------- options ----------------
    def _on_auto_proxy(self, on):
        self.auto_proxy = on
        self.settings.setValue("auto_proxy", "1" if on else "0")
        if not on and self.core.state == "connected" and not (self.chk_tun.isVisible() and self.chk_tun.isChecked()):
            sysproxy.set_system_proxy(False)

    def _on_tun(self, on):
        self.want_tun = on
        self.settings.setValue("tun_mode", "1" if on else "0")
        if on and not paths.IS_WIN and not os.path.isfile(paths.TUN_BIN):
            QMessageBox.warning(self, "تونل کامل",
                "باینری tun2socks پیدا نشد.\n"
                "اگر از سورس اجرا می‌کنید:  bash tools/fetch-binaries.sh --with-tun\n"
                "در بسته نصبی (RPM) تونل داخل خود برنامه است.")

    # ---------------- menu actions ----------------
    def _add_nodes(self, new_nodes):
        if not new_nodes:
            QMessageBox.information(self, "خالی", "هیچ کانفیگ قابل استفاده‌ای پیدا نشد")
            return
        self.custom_nodes.extend(new_nodes)
        self._save_custom_nodes()
        self.all_nodes = nodes_mod.load_builtin_nodes() + self.custom_nodes
        self._fill_servers()
        self.status.setText(f"{len(new_nodes)} کانفیگ اضافه شد")

    def _add_from_clip(self):
        text = QApplication.clipboard().text()
        added = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(("vless://", "vmess://")):
                try:
                    added.append(nodes_mod.parse_link(line))
                except Exception:
                    pass
        self._add_nodes(added)

    def _add_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل کانفیگ", "", "همه فایل‌ها (*)")
        if not path:
            return
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e)); return
        added = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(("vless://", "vmess://")):
                try:
                    added.append(nodes_mod.parse_link(line))
                except Exception:
                    pass
        self._add_nodes(added)

    def _add_sub(self):
        url, ok = QInputDialog.getText(self, "سابسکریپشن", "آدرس URL سابسکریپشن:")
        if not ok or not url.strip():
            return
        self.status.setText("در حال دریافت سابسکریپشن …")
        import threading
        def worker():
            try:
                ns = nodes_mod.fetch_subscription(url.strip())
            except Exception as e:
                ns = []
                self.bridge.warnBox.emit("خطا", str(e))
            self.bridge.subNodes.emit(ns)
        threading.Thread(target=worker, daemon=True).start()

    def _check_ip(self):
        self.status.setText("در حال بررسی IP …")
        import threading
        def worker():
            try:
                ip, cc, city = self.core.check_real_ip()
                msg = f"IP ظاهری شما: {ip}\nکشور: {cc} — {city}"
            except Exception as e:
                msg = f"بررسی ناموفق (احتمالاً متصل نیستید): {e}"
            self.bridge.infoBox.emit("IP فعلی", msg)
            self.bridge.statusMsg.emit("آماده")
        threading.Thread(target=worker, daemon=True).start()

    def _clear_custom(self):
        self.custom_nodes = []
        self._save_custom_nodes()
        self.all_nodes = nodes_mod.load_builtin_nodes()
        self.selected_idx = 0
        self._fill_servers()

    def _save_custom_nodes(self):
        import json
        self.settings.setValue("custom_nodes", json.dumps([n.to_dict() for n in self.custom_nodes]))

    def _load_custom_nodes(self):
        import json
        raw = self.settings.value("custom_nodes", "")
        if raw:
            try:
                self.custom_nodes = [nodes_mod.Node.from_dict(d) for d in json.loads(raw)]
            except Exception:
                self.custom_nodes = []

    def _copy_env(self):
        QApplication.clipboard().setText(sysproxy.env_export_hint(
            http_port=getattr(self.core, "http_port", HTTP_PORT),
            socks_port=getattr(self.core, "socks_port", SOCKS_PORT)))
        self.status.setText("دستورات ترمینال کپی شد")

    # ---------------- عیب‌یابی ----------------
    def _diag(self):
        import platform
        lines = [f"Nice VPN {__version__}",
                 f"Python: {platform.python_version()} ({sys.executable})"]
        try:
            from PySide6 import __version__ as qv
            lines.append(f"PySide6: {qv}")
        except Exception as e:
            lines.append(f"PySide6: خطا! {e}")
        lines.append(f"xray: {paths.XRAY_BIN}")
        if os.path.isfile(paths.XRAY_BIN):
            try:
                r = subprocess.run([paths.XRAY_BIN, "version"], capture_output=True, text=True, timeout=10)
                lines.append("  " + (r.stdout or r.stderr).strip().splitlines()[0])
            except Exception as e:
                lines.append(f"  اجرا نشد: {e}")
        else:
            lines.append("  ⚠ پیدا نشد!")
        lines.append(f"tun2socks: {paths.TUN_BIN} " +
                     ("(موجود)" if os.path.isfile(paths.TUN_BIN) else "(پیدا نشد — فقط پروکسی)"))
        lines.append(f"اسکریپت تونل: {paths.find_tun_helper() or 'پیدا نشد'}")
        from .xrayconf import has_geo_files
        lines.append(f"فایل‌های geo (بلاک تبلیغ/ایران مستقیم): {'موجود' if has_geo_files() else 'نیستند'}")
        lines.append(f"پورت‌ها: SOCKS {getattr(self.core, 'socks_port', SOCKS_PORT)} / "
                     f"HTTP {getattr(self.core, 'http_port', HTTP_PORT)}")
        lines.append(f"محیط دسکتاپ: {sysproxy.desktop_env()}")
        lines.append(f"وضعیت هسته: {self.core.state}")
        QMessageBox.information(self, "تشخیص مشکلات", "\n".join(lines))

    def _about(self):
        QMessageBox.about(self, "درباره Nice VPN",
            f"<b>Nice VPN</b> نسخه {__version__}<br><br>"
            "کلاینت سبک و تمیز Xray/VLESS برای فدورا KDE و ویندوز.<br>"
            "بدون تبلیغات • بدون عضویت اجباری • بدون ریموت‌کانفیگ<br><br>"
            f"<a href='https://github.com/melimcrr-crypto/nice-vpn'>GitHub — melimcrr-crypto/nice-vpn</a>")

    # ---------------- tray / close ----------------
    def _toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_visible()

    def closeEvent(self, ev):
        # به‌جای خروج کامل، به tray برود (رفتار استاندارد اپ‌های VPN)
        ev.ignore()
        self.hide()
        self.tray.showMessage("Nice VPN", "برنامه به tray منتقل شد و اتصال باز است", app_icon(), 2000)

    def _quit(self):
        if self.core.state != "stopped":
            self.core.stop()
        if self.chk_proxy.isChecked():
            sysproxy.set_system_proxy(False)
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Nice VPN")
    app.setOrganizationName("NiceVPN")
    app.setApplicationDisplayName("Nice VPN")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLE)
    load_font(app)
    core_mod.cleanup_stale()
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
