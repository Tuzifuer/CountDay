# -*- coding: utf-8 -*-
"""开发预览：把卡片画到一张合成背景上，导出 PNG 便于检查视觉效果。"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication

import config
import countdown
import theme
from card import CountCard


def sample_events() -> list[dict]:
    today = date.today()
    return [
        {"id": "a", "title": "春节", "date": (today + timedelta(days=76)).isoformat(),
         "type": "countdown", "created": (today - timedelta(days=120)).isoformat()},
        {"id": "b", "title": "项目交付", "date": (today + timedelta(days=3)).isoformat(),
         "type": "countdown", "created": (today - timedelta(days=30)).isoformat()},
        {"id": "c", "title": "入职纪念日", "date": (today - timedelta(days=365)).isoformat(),
         "type": "anniversary", "created": (today - timedelta(days=365)).isoformat()},
        {"id": "d", "title": "生日", "date": today.isoformat(),
         "type": "countdown", "created": (today - timedelta(days=10)).isoformat()},
    ]


def main() -> int:
    app = QApplication(sys.argv)
    events = sample_events()

    variants = [
        ("ink", events[0], {}, None),
        ("frost", events[1], {"show_progress": True}, None),
        ("ocean", events[2], {}, None),
        ("sakura", events[3], {"show_shadow": True}, None),
        ("glass", events[0], {"show_progress": True, "show_dots": True}, None),
    ]

    cards = []
    for preset, ev, over, _ in variants:
        style = theme.apply_preset(dict(config.DEFAULT_STYLE), preset)
        style.update(over)
        card = CountCard(style, dict(config.DEFAULT_BEHAVIOR))
        info = countdown.compute(ev, "natural", style)
        card.set_content(info, 3, 0)
        card.adjustSize()
        cards.append(card)

    pad = 40
    w = max(c.width() for c in cards) + pad * 2
    h = sum(c.height() for c in cards) + pad * (len(cards) + 1)

    canvas = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing, True)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0.0, QColor("#2C3E50"))
    grad.setColorAt(0.5, QColor("#4A5B6B"))
    grad.setColorAt(1.0, QColor("#1F2933"))
    p.fillRect(canvas.rect(), grad)
    y = pad
    for card in cards:
        pm = card.grab()
        p.drawPixmap(QPoint((w - pm.width()) // 2, y), pm)
        y += pm.height() + pad
    p.end()

    out = sys.argv[1] if len(sys.argv) > 1 else "preview.png"
    canvas.save(out)
    print("saved", out, canvas.width(), "x", canvas.height())
    return 0


if __name__ == "__main__":
    sys.exit(main())
