# -*- coding: utf-8 -*-
"""开发预览：离屏渲染设置面板与事件对话框，导出 PNG 检查排版。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QTabWidget

import config
from dialogs import EventDialog, SettingsDialog


def main() -> int:
    app = QApplication(sys.argv)
    cfg = config.load()

    dlg = SettingsDialog(cfg)
    dlg.resize(600, 560)
    tabs = dlg.findChild(QTabWidget)
    names = ["settings_events.png", "settings_style.png", "settings_behavior.png"]
    for i, name in enumerate(names):
        tabs.setCurrentIndex(i)
        dlg.grab().save(name)
        print("saved", name)

    ev = EventDialog(None, cfg["events"][0])
    ev.adjustSize()
    ev.grab().save("event_dialog.png")
    print("saved event_dialog.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
