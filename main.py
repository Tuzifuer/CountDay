# -*- coding: utf-8 -*-
"""桌面倒计日 · 主程序。

功能：桌面置底卡片、倒计日/纪念日、多事件轮播、开机自启、托盘菜单。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QDialog, QMenu, QMessageBox, QSystemTrayIcon)

import config
import countdown
import theme
import win_utils
from card import CountCard
from dialogs import EventDialog, SettingsDialog

IPC_KEY = "CountDay.single.instance.v1"


# ---------------------------------------------------------------- 图标

def build_icon(accent: str = "#F5C451") -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        body = QRectF(size * 0.08, size * 0.14, size * 0.84, size * 0.80)
        radius = size * 0.20
        path = QPainterPath()
        path.addRoundedRect(body, radius, radius)
        p.save()
        p.setClipPath(path)
        p.fillRect(QRectF(0, 0, size, size), QColor("#1B212B"))
        p.fillRect(QRectF(body.left(), body.top(), body.width(), body.height() * 0.30),
                   QColor(accent))
        p.restore()
        # 两个日历环
        pen = p.pen()
        pen.setColor(QColor("#1B212B"))
        pen.setWidthF(max(1.0, size * 0.07))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        x1, x2 = body.left() + body.width() * 0.28, body.left() + body.width() * 0.72
        p.drawLine(int(x1), int(size * 0.07), int(x1), int(size * 0.20))
        p.drawLine(int(x2), int(size * 0.07), int(x2), int(size * 0.20))
        # 中间小圆点
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(size * 0.42, size * 0.55, size * 0.16, size * 0.16))
        p.end()
        icon.addPixmap(pm)
    return icon


# ---------------------------------------------------------------- 控制器

class Controller:
    def __init__(self, app: QApplication):
        self.app = app
        self.cfg = config.load()
        self.icon = build_icon(self.cfg["style"].get("accent_color", "#F5C451"))
        app.setWindowIcon(self.icon)

        self.index = int(self.cfg.get("current_index", 0))
        self.card = CountCard(self.cfg["style"], self.cfg["behavior"])
        self.card.menuRequested.connect(self.show_menu)
        self.card.editRequested.connect(self.edit_current)
        self.card.navigated.connect(self.step)
        self.card.moved.connect(self.save_position)
        self.card.restoreRequested.connect(self._unminimize)

        self._last_date = date.today()
        self._reminded: set[tuple[str, date]] = set()
        self._last_signature = None

        self._build_tray()
        self._restore_position()
        win_utils.prepare_desktop_window(int(self.card.winId()))  # 先建原生窗口再显示，避免闪一下
        self.card.show()
        QTimer.singleShot(0, self._post_show)

        self.tick_timer = QTimer(self.app)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self._on_tick)
        self.tick_timer.start()

        self.rotate_timer = QTimer(self.app)
        self.rotate_timer.timeout.connect(lambda: self.step(1, user=False))
        self._restart_rotate()

        self.zorder_timer = QTimer(self.app)
        self.zorder_timer.setInterval(1500)
        self.zorder_timer.timeout.connect(self._keep_bottom)
        self.zorder_timer.start()

        self.refresh()
        QTimer.singleShot(4000, lambda: self._maybe_remind(date.today()))

    # -------------------------------------------------- 初始化

    def _post_show(self) -> None:
        win_utils.prepare_desktop_window(int(self.card.winId()))
        self.apply_mode()

    def _place_default(self) -> None:
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.card.move(area.right() - self.card.width() - 39, area.top() + 56)

    def _restore_position(self) -> None:
        x = self.cfg["window"].get("x")
        y = self.cfg["window"].get("y")
        if x is None or y is None:
            self._place_default()
        else:
            self.card.move(int(x), int(y))
        self._ensure_visible()

    def _ensure_visible(self) -> None:
        center = self.card.pos() + QPoint(self.card.width() // 2, self.card.height() // 2)
        if QGuiApplication.screenAt(center) is None:
            area = QGuiApplication.primaryScreen().availableGeometry()
            self.card.move(area.right() - self.card.width() - 40, area.top() + 56)
        self.card.clamp_to_screen()

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.icon, self.app)
        self.tray.setToolTip(config.APP_DISPLAY_NAME)
        menu = QMenu()
        self.act_toggle = menu.addAction("隐藏卡片")
        self.act_toggle.triggered.connect(self.toggle_visible)
        menu.addSeparator()
        menu.addAction("新建事件…").triggered.connect(self.new_event)
        menu.addAction("下一个事件").triggered.connect(lambda: self.step(1))
        menu.addAction("设置…").triggered.connect(self.open_settings)
        menu.addSeparator()
        self.act_tray_autostart = menu.addAction("开机自启")
        self.act_tray_autostart.setCheckable(True)
        self.act_tray_autostart.setChecked(win_utils.get_autostart())
        self.act_tray_autostart.toggled.connect(self.set_autostart)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.toggle_visible()

    # -------------------------------------------------- 显示模式

    def apply_mode(self) -> None:
        hwnd = int(self.card.winId())
        mode = self.cfg["behavior"].get("mode", "bottom")
        win_utils.prepare_desktop_window(hwnd)
        if mode == "top":
            win_utils.set_topmost(hwnd)
        elif mode == "normal":
            win_utils.set_normal_z(hwnd)
        else:
            win_utils.push_bottom(hwnd)

    def _keep_bottom(self) -> None:
        if self.cfg["behavior"].get("mode") == "bottom" and self.card.isVisible():
            win_utils.push_bottom(int(self.card.winId()))

    def _unminimize(self) -> None:
        self.card.setWindowState(Qt.WindowNoState)
        self.card.show()
        self.apply_mode()

    def toggle_visible(self) -> None:
        if self.card.isVisible():
            self.card.hide()
            self.act_toggle.setText("显示卡片")
        else:
            self.card.show()
            self._post_show()
            self.act_toggle.setText("隐藏卡片")

    # -------------------------------------------------- 内容刷新

    def _current_event(self) -> dict:
        events = self.cfg["events"]
        self.index = max(0, min(self.index, len(events) - 1))
        return events[self.index]

    def _signature(self, info: countdown.Info) -> tuple:
        prog = None if info.progress is None else round(info.progress, 3)
        return (info.title, info.big, info.prefix, info.unit, info.foot, info.state, prog)

    def refresh(self, crossfade: bool = False) -> None:
        info = countdown.compute(self._current_event(), self.cfg["behavior"].get("calc_mode", "natural"),
                                 self.cfg["style"])
        n = len(self.cfg["events"])
        dot_count = n if n > 1 else 0
        self._last_signature = self._signature(info)
        if crossfade and dot_count:
            self.card.crossfade_to(info, dot_count, self.index)
        else:
            self.card.set_content(info, dot_count, self.index)
        if self.cfg["window"].get("x") is None:
            self._place_default()      # 首次启动：按真实尺寸贴右上角
        self._ensure_visible()
        self.tray.setToolTip(f"{info.title} · {info.prefix}{info.big}{info.unit}")

    def step(self, delta: int, user: bool = True) -> None:
        n = len(self.cfg["events"])
        if n <= 1:
            return
        self.index = (self.index + delta) % n
        self.cfg["current_index"] = self.index
        if user:
            self._restart_rotate()
        self.refresh(crossfade=True)
        config.save(self.cfg)

    def _on_tick(self) -> None:
        today = date.today()
        if today != self._last_date:
            self._last_date = today
            self.refresh()
            self._maybe_remind(today)
        else:
            # 紧迫模式下小时数会变，文本变化时静默更新
            info = countdown.compute(self._current_event(),
                                     self.cfg["behavior"].get("calc_mode", "natural"), self.cfg["style"])
            if self._signature(info) != self._last_signature:
                self._last_signature = self._signature(info)
                self.card.set_content(info, len(self.cfg["events"]) if len(self.cfg["events"]) > 1 else 0,
                                      self.index)

    def _maybe_remind(self, today: date) -> None:
        if not self.cfg["behavior"].get("remind", True):
            return
        for ev in self.cfg["events"]:
            if countdown.parse_date(ev["date"]) != today:
                continue
            key = (ev["id"], today)
            if key in self._reminded:
                continue
            self._reminded.add(key)
            kind = "纪念日" if ev.get("type") == "anniversary" else "倒计时"
            self.tray.showMessage(f"今天就是「{ev['title']}」",
                                  f"{ev['date']} · {kind}到期日，记得安排一下～",
                                  QSystemTrayIcon.Information, 6000)

    def _restart_rotate(self) -> None:
        self.rotate_timer.stop()
        bh = self.cfg["behavior"]
        if bh.get("rotate", True) and len(self.cfg["events"]) > 1:
            self.rotate_timer.start(max(3, int(bh.get("rotate_interval", 8))) * 1000)

    # -------------------------------------------------- 菜单与对话框

    def _build_menu(self) -> QMenu:
        info = self.card.current_info()
        menu = QMenu(self.card)
        header = menu.addAction(f"{info.title if info else ''}  {info.prefix if info else ''}"
                                f"{info.big if info else ''}{info.unit if info else ''}")
        header.setEnabled(False)
        menu.addSeparator()
        menu.addAction("编辑此事件…").triggered.connect(self.edit_current)
        menu.addAction("新建事件…").triggered.connect(self.new_event)
        if len(self.cfg["events"]) > 1:
            menu.addAction("下一个事件").triggered.connect(lambda: self.step(1))
            menu.addAction("上一个事件").triggered.connect(lambda: self.step(-1))
        menu.addSeparator()
        act_lock = menu.addAction("锁定位置")
        act_lock.setCheckable(True)
        act_lock.setChecked(bool(self.cfg["behavior"].get("locked")))
        act_lock.toggled.connect(self.set_locked)
        act_auto = menu.addAction("开机自启")
        act_auto.setCheckable(True)
        act_auto.setChecked(win_utils.get_autostart())
        act_auto.toggled.connect(self.set_autostart)
        menu.addSeparator()
        menu.addAction("设置…").triggered.connect(self.open_settings)
        menu.addAction("隐藏卡片").triggered.connect(self.toggle_visible)
        menu.addAction("退出").triggered.connect(self.quit)
        return menu

    def show_menu(self, pos: QPoint) -> None:
        """弹出卡片右键菜单。

        Qt 的弹出菜单要求本进程处于前台才能正常显示/接收输入，而卡片本身带
        WS_EX_NOACTIVATE（点它不抢焦点）。所以这里临时放开该标志、抢一次前台，
        菜单关闭后立刻还原标志并把焦点还给原来的窗口。
        """
        hwnd = int(self.card.winId())
        prev = win_utils.get_foreground()
        win_utils.set_ex_style_flag(hwnd, win_utils.WS_EX_NOACTIVATE, False)
        win_utils.force_foreground(hwnd)
        try:
            self._build_menu().exec(pos)
        finally:
            win_utils.set_ex_style_flag(hwnd, win_utils.WS_EX_NOACTIVATE, True)
            self._keep_bottom()
            if prev and prev != hwnd:
                win_utils.force_foreground(prev)

    def set_locked(self, locked: bool) -> None:
        self.cfg["behavior"]["locked"] = bool(locked)
        self.card.apply_behavior(self.cfg["behavior"])
        config.save(self.cfg)

    def set_autostart(self, enabled: bool) -> None:
        ok = win_utils.set_autostart(bool(enabled))
        self.cfg["behavior"]["autostart"] = bool(enabled) and ok
        if hasattr(self, "act_tray_autostart"):
            self.act_tray_autostart.blockSignals(True)
            self.act_tray_autostart.setChecked(self.cfg["behavior"]["autostart"])
            self.act_tray_autostart.blockSignals(False)
        config.save(self.cfg)
        if not ok:
            self._message(QMessageBox.Warning, "设置失败", "写入开机自启注册表失败，请检查系统权限。")

    # -------------------------------------------------- 对话框辅助

    def _run_dialog(self, dlg: QDialog) -> int:
        """卡片不抢焦点，对话框必须自己抢到前面来，否则会被别的窗口盖住。"""
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        dlg.setWindowIcon(self.icon)
        dlg.adjustSize()
        screen = self.card.screen() or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        dlg.move(geo.center().x() - dlg.width() // 2, geo.center().y() - dlg.height() // 2)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        win_utils.force_foreground(int(dlg.winId()))
        return dlg.exec()

    def _message(self, icon, title: str, text: str) -> None:
        box = QMessageBox(icon, title, text, QMessageBox.Ok)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        box.setWindowIcon(self.icon)
        win_utils.force_foreground(int(box.winId()))
        box.exec()

    def edit_current(self) -> None:
        ev = self._current_event()
        dlg = EventDialog(None, ev)
        if self._run_dialog(dlg) == QDialog.Accepted:
            self.cfg["events"][self.index] = dlg.result_event()
            config.save(self.cfg)
            self.refresh()

    def new_event(self) -> None:
        dlg = EventDialog(None)
        if self._run_dialog(dlg) == QDialog.Accepted:
            self.cfg["events"].append(dlg.result_event())
            self.index = len(self.cfg["events"]) - 1
            self.cfg["current_index"] = self.index
            config.save(self.cfg)
            self._restart_rotate()
            self.refresh(crossfade=True)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.cfg, None)
        if self._run_dialog(dlg) != QDialog.Accepted:
            return
        res = dlg.result_data()
        if not res["events"]:
            self._message(QMessageBox.Information, "提示", "至少保留一个事件，已取消本次修改。")
            return
        self.cfg["events"] = res["events"]
        self.cfg["style"] = res["style"]
        self.cfg["behavior"] = res["behavior"]
        self.index = min(self.index, len(self.cfg["events"]) - 1)
        config.save(self.cfg)
        self.card.apply_style(self.cfg["style"])
        self.card.apply_behavior(self.cfg["behavior"])
        self.icon = build_icon(self.cfg["style"].get("accent_color", "#F5C451"))
        self.app.setWindowIcon(self.icon)
        self.tray.setIcon(self.icon)
        if res.get("reset_position"):
            self.cfg["window"] = {"x": None, "y": None}
            config.save(self.cfg)
            self._restore_position()
        self.apply_mode()
        self._restart_rotate()
        self.refresh()
        if self.cfg["behavior"].get("autostart") != win_utils.get_autostart():
            self.set_autostart(self.cfg["behavior"].get("autostart", False))

    def save_position(self) -> None:
        self._ensure_visible()
        self.cfg["window"] = {"x": self.card.x(), "y": self.card.y()}
        config.save(self.cfg)

    # -------------------------------------------------- 退出

    def quit(self) -> None:
        try:
            self.cfg["window"] = {"x": self.card.x(), "y": self.card.y()}
            config.save(self.cfg)
        except Exception:
            pass
        self.tray.hide()
        self.app.quit()

    def handle_ipc(self) -> None:
        sock = self.server.nextPendingConnection()
        if sock is None:
            return
        sock.readyRead.connect(lambda: self._read_ipc(sock))
        sock.disconnected.connect(sock.deleteLater)

    def _read_ipc(self, sock: QLocalSocket) -> None:
        cmd = bytes(sock.readAll()).decode("utf-8", "ignore").strip()
        if cmd == "settings":
            self.open_settings()
        else:
            if not self.card.isVisible():
                self.toggle_visible()
            self._post_show()


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("CountDay")
    app.setQuitOnLastWindowClosed(False)

    if "--reset" in sys.argv:
        config.save(config.default_config())

    # 单实例
    probe = QLocalSocket()
    probe.connectToServer(IPC_KEY)
    if probe.waitForConnected(250):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        return 0

    controller = Controller(app)
    if "--demo-menu" in sys.argv:      # 开发调试：自动弹出右键菜单
        QTimer.singleShot(900, lambda: controller.show_menu(
            controller.card.pos() + QPoint(30, 30)))
    server = QLocalServer()
    QLocalServer.removeServer(IPC_KEY)
    if server.listen(IPC_KEY):
        controller.server = server
        server.newConnection.connect(controller.handle_ipc)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
