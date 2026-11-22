# -*- coding: utf-8 -*-
"""Windows 平台相关：桌面置底、置顶、开机自启。"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
SWP_NOZORDER = 0x0004

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "CountDay"

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    _LONG_PTR = ctypes.c_ssize_t
    if hasattr(user32, "GetWindowLongPtrW"):          # 64 位
        _get_long = user32.GetWindowLongPtrW
        _set_long = user32.SetWindowLongPtrW
    else:                                             # 32 位
        _get_long = user32.GetWindowLongW
        _set_long = user32.SetWindowLongW

    _get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_long.restype = _LONG_PTR
    _set_long.argtypes = [wintypes.HWND, ctypes.c_int, _LONG_PTR]
    _set_long.restype = _LONG_PTR

    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
else:
    user32 = None


# ------------------------------------------------------------ 窗口样式

def prepare_desktop_window(hwnd) -> None:
    """不抢焦点、不进 Alt+Tab、不进任务栏。"""
    if not IS_WINDOWS:
        return
    try:
        h = wintypes.HWND(int(hwnd))
        cur = _get_long(h, GWL_EXSTYLE)
        new = cur | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if new != cur:
            _set_long(h, GWL_EXSTYLE, new)
    except Exception:
        pass


def set_ex_style_flag(hwnd, flag: int, enabled: bool) -> None:
    if not IS_WINDOWS:
        return
    try:
        h = wintypes.HWND(int(hwnd))
        cur = _get_long(h, GWL_EXSTYLE)
        new = (cur | flag) if enabled else (cur & ~flag)
        if new != cur:
            _set_long(h, GWL_EXSTYLE, new)
    except Exception:
        pass


def _set_pos(hwnd, insert_after: int) -> None:
    if not IS_WINDOWS:
        return
    try:
        user32.SetWindowPos(wintypes.HWND(int(hwnd)), wintypes.HWND(insert_after),
                            0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)
    except Exception:
        pass


def push_bottom(hwnd) -> None:
    """压到所有窗口下面（桌面置底）。"""
    _set_pos(hwnd, HWND_BOTTOM)


def set_topmost(hwnd) -> None:
    _set_pos(hwnd, HWND_TOPMOST)


def set_normal_z(hwnd) -> None:
    _set_pos(hwnd, HWND_NOTOPMOST)


def set_foreground(hwnd) -> None:
    """右键菜单前临时抢前台，否则菜单弹不出来。"""
    if not IS_WINDOWS:
        return
    try:
        user32.SetForegroundWindow(wintypes.HWND(int(hwnd)))
    except Exception:
        pass


def get_foreground() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        user32.GetForegroundWindow.restype = wintypes.HWND
        return int(user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def force_foreground(hwnd) -> None:
    """可靠地抢到前台：必要时 AttachThreadInput 绕过前台锁定。"""
    if not IS_WINDOWS:
        return
    try:
        h = wintypes.HWND(int(hwnd))
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        fg = user32.GetForegroundWindow()
        if fg == h:
            return
        cur_tid = kernel32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = False
        if fg_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        user32.BringWindowToTop(h)
        user32.SetForegroundWindow(h)
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, False)
    except Exception:
        pass


# ------------------------------------------------------------ 开机自启

def startup_command() -> str:
    """返回写入注册表 Run 键的启动命令。"""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    launcher = pyw if pyw.exists() else exe
    script = Path(__file__).resolve().parent / "main.py"
    return f'"{launcher}" "{script}"'


def get_autostart() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            return bool(value)
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
