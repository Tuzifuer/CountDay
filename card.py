# -*- coding: utf-8 -*-
"""桌面卡片：无边框透明窗口 + QPainter 自绘。"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF, QRectF, QSize, Qt,
                            QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QWidget

from countdown import Info

_SHADOW_CACHE: dict = {}


def _col(value, alpha: float = 1.0) -> QColor:
    c = QColor(value)
    if not c.isValid():
        c = QColor("#FFFFFF")
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def _make_shadow(w: int, h: int, radius: float, margin: float, offset: float = 5.0) -> QPixmap:
    scale = 6
    sw, sh = max(1, w // scale), max(1, h // scale)
    img = QImage(sw, sh, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 255))
    mx = margin / scale
    p.drawRoundedRect(QRectF(mx, mx + offset / scale, sw - 2 * mx, sh - 2 * mx),
                      radius / scale, radius / scale)
    p.end()
    big = img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return QPixmap.fromImage(big)


def _pick_family(preferred: str, fallbacks: list[str]) -> list[str]:
    fams = [preferred] if preferred else []
    fams += [f for f in fallbacks if f and f != preferred]
    return fams


class CountCard(QWidget):
    menuRequested = Signal(QPoint)
    editRequested = Signal()
    navigated = Signal(int)
    moved = Signal()
    restoreRequested = Signal()

    MARGIN = 18  # 给阴影留的边距

    def __init__(self, style: dict, behavior: dict):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self._style = dict(style)
        self._behavior = dict(behavior)
        self._info: Info | None = None
        self._dot_count = 0
        self._dot_index = 0
        self._hover = False
        self._fade = 1.0
        self._drag_from: QPoint | None = None
        self._layout_cache: dict | None = None
        self._fade_anim: QVariantAnimation | None = None

    # ------------------------------------------------------------ 数据

    def set_content(self, info: Info | None, dot_count: int = 0, dot_index: int = 0) -> None:
        self._info = info
        self._dot_count = dot_count
        self._dot_index = dot_index
        self._layout_cache = None
        self._apply_size()
        self.update()

    def apply_style(self, style: dict) -> None:
        self._style = dict(style)
        self._layout_cache = None
        self._apply_size()
        self.update()

    def apply_behavior(self, behavior: dict) -> None:
        self._behavior = dict(behavior)

    def current_info(self) -> Info | None:
        return self._info

    # ------------------------------------------------------------ 字体与布局

    def _fonts(self, st: dict) -> dict:
        fam = st.get("font_family") or "Microsoft YaHei UI"
        digit = st.get("digit_family") or fam
        base = float(st.get("font_size", 15.0))
        families = _pick_family(fam, ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"])
        digit_families = _pick_family(digit, families)
        ls = float(st.get("letter_spacing", 0.6))

        def mk(px: float, weight=QFont.Weight.Normal, fams=None, spacing: float = 0.0) -> QFont:
            f = QFont()
            f.setFamilies(fams or families)
            f.setPixelSize(max(6, int(round(px))))
            f.setWeight(weight)
            if spacing:
                f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
            return f

        return {
            "title": mk(base * 0.95, QFont.Weight.DemiBold, spacing=ls),
            "prefix": mk(base * 1.05, QFont.Weight.Normal),
            "digit": mk(base * float(st.get("digit_scale", 4.3)), QFont.Weight.Bold, digit_families),
            "unit": mk(base * 1.12, QFont.Weight.Medium),
            "foot": mk(base * 0.8, QFont.Weight.Normal, spacing=0.4),
        }

    def _layout(self) -> dict:
        if self._layout_cache is not None:
            return self._layout_cache

        st, info = self._style, self._info
        base = float(st.get("font_size", 15.0))
        f = self._fonts(st)
        fm = {k: QFontMetricsF(v) for k, v in f.items()}

        pad_h = max(12.0, base * 1.55)
        pad_v = max(9.0, base * 1.10)
        gap_title = base * 0.22
        gap_num = base * 0.34
        gap_foot = base * 0.10
        gap_bar = base * 0.62
        gap_dots = base * 0.52
        bar_h = max(3.0, base * 0.26)
        dot_d = max(3.0, base * 0.30)

        show_title = bool(st.get("show_title")) and bool(info)
        title = info.title if info else ""
        prefix = info.prefix if info else ""
        big = info.big if info else ""
        unit = info.unit if info else ""
        foot = info.foot if info else ""

        title_w = fm["title"].horizontalAdvance(title) if show_title else 0.0
        gap_p = base * 0.40 if prefix else 0.0
        gap_u = base * 0.26 if unit else 0.0
        prefix_w = fm["prefix"].horizontalAdvance(prefix) if prefix else 0.0
        digit_w = fm["digit"].horizontalAdvance(big) if big else 0.0
        unit_w = fm["unit"].horizontalAdvance(unit) if unit else 0.0
        num_w = prefix_w + gap_p + digit_w + gap_u + unit_w

        foot_w = fm["foot"].horizontalAdvance(foot) if foot else 0.0

        content_w = max(title_w, num_w, foot_w, base * 6.2)
        if st.get("show_progress") and info and info.progress is not None:
            content_w = max(content_w, base * 7.4)

        title_h = fm["title"].height() if show_title else 0.0
        num_h = fm["digit"].height() if big else 0.0
        foot_h = fm["foot"].height() if foot else 0.0

        has_bar = bool(st.get("show_progress")) and info is not None and info.progress is not None
        has_dots = bool(st.get("show_dots")) and self._dot_count > 1

        h = pad_v * 2 + num_h
        if show_title:
            h += title_h + gap_title
        if foot_h:
            h += gap_num + gap_foot + foot_h
        if has_bar:
            h += gap_bar + bar_h
        if has_dots:
            h += gap_dots + dot_d

        w = content_w + pad_h * 2
        size = QSize(int(round(w + self.MARGIN * 2)), int(round(h + self.MARGIN * 2)))

        self._layout_cache = {
            "size": size, "f": f, "fm": fm, "pad_h": pad_h, "pad_v": pad_v,
            "content_w": content_w, "title_h": title_h, "num_h": num_h, "foot_h": foot_h,
            "gap_title": gap_title, "gap_num": gap_num, "gap_foot": gap_foot,
            "gap_bar": gap_bar, "gap_dots": gap_dots, "bar_h": bar_h, "dot_d": dot_d,
            "has_bar": has_bar, "has_dots": has_dots,
            "show_title": show_title, "title": title, "prefix": prefix, "big": big,
            "unit": unit, "foot": foot, "gap_p": gap_p, "gap_u": gap_u,
            "num_w": num_w, "prefix_w": prefix_w, "digit_w": digit_w, "unit_w": unit_w,
        }
        return self._layout_cache

    def _apply_size(self) -> None:
        size = self._layout()["size"]
        if size != self.size():
            self.setFixedSize(size)
            self.clamp_to_screen()

    def clamp_to_screen(self) -> None:
        """尺寸变化后保证整块卡片仍落在某块屏幕内。"""
        scr = self.screen() or QGuiApplication.primaryScreen()
        if scr is None:
            return
        area = scr.availableGeometry()
        x = min(max(self.x(), area.left()), max(area.left(), area.right() - self.width() + 1))
        y = min(max(self.y(), area.top()), max(area.top(), area.bottom() - self.height() + 1))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def sizeHint(self) -> QSize:
        return self._layout()["size"]

    # ------------------------------------------------------------ 绘制

    def paintEvent(self, event) -> None:
        st, info = self._style, self._info
        L = self._layout()
        fade = self._fade
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing |
                         QPainter.SmoothPixmapTransform)

        m = self.MARGIN
        body = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        radius = float(st.get("radius", 18.0))
        bg = QColor(st.get("bg_color", "#151A22"))
        fg_hex = st.get("fg_color", "#FFFFFF")
        accent_hex = st.get("accent_color", "#F5C451")
        opacity = float(st.get("bg_opacity", 0.66))

        # 阴影
        if st.get("show_shadow") and opacity > 0.03:
            key = (int(body.width()), int(body.height()), int(radius))
            pm = _SHADOW_CACHE.get(key)
            if pm is None:
                pm = _make_shadow(*key, m)
                _SHADOW_CACHE[key] = pm
            p.setOpacity(0.34 * fade)
            p.drawPixmap(0, 0, pm)
            p.setOpacity(1.0)

        # 背景（带一点自上而下的玻璃渐变）
        if opacity > 0.003:
            path = QPainterPath()
            path.addRoundedRect(body, radius, radius)
            grad = QLinearGradient(body.topLeft(), body.bottomLeft())
            grad.setColorAt(0.0, _col(_mix(bg, QColor("#FFFFFF"), 0.10).name(), opacity * 0.95 * fade))
            grad.setColorAt(1.0, _col(_mix(bg, QColor("#000000"), 0.10).name(), opacity * fade))
            p.fillPath(path, QBrush(grad))

            light_bg = (bg.red() + bg.green() + bg.blue()) / 3 > 140
            border = _col("#000000", (0.10 if light_bg else 0.13) * fade * min(1.0, opacity * 1.6))
            if self._hover:
                border = _col(accent_hex, 0.45 * fade)
            p.setPen(QPen(border, 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        elif self._hover:
            path = QPainterPath()
            path.addRoundedRect(body, radius, radius)
            p.setPen(QPen(_col(accent_hex, 0.35), 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

        if not info:
            p.end()
            return

        fg = QColor(fg_hex) if QColor(fg_hex).isValid() else QColor("#FFFFFF")
        accent = QColor(accent_hex) if QColor(accent_hex).isValid() else QColor("#F5C451")
        muted = 0.72 if fg.lightness() > 128 else 0.68
        faint = 0.52 if fg.lightness() > 128 else 0.55

        left = body.left() + L["pad_h"]
        right = body.right() - L["pad_h"]
        align = st.get("align", "center")

        def row_x(row_w: float) -> float:
            if align == "left":
                return left
            if align == "right":
                return right - row_w
            return (left + right) / 2.0 - row_w / 2.0

        y = body.top() + L["pad_v"]

        # 标题
        if L["show_title"]:
            fm_t = L["fm"]["title"]
            x = row_x(fm_t.horizontalAdvance(L["title"]))
            p.setFont(L["f"]["title"])
            p.setPen(_col(fg.name(), muted * fade))
            p.drawText(QPointF(x, y + fm_t.ascent()), L["title"])
            y += L["title_h"] + L["gap_title"]

        # 大数字行
        fm_n, fm_p, fm_u = L["fm"]["digit"], L["fm"]["prefix"], L["fm"]["unit"]
        x = row_x(L["num_w"])
        baseline = y + fm_n.ascent()
        if L["prefix"]:
            p.setFont(L["f"]["prefix"])
            p.setPen(_col(fg.name(), 0.82 * fade))
            p.drawText(QPointF(x, baseline), L["prefix"])
            x += L["prefix_w"] + L["gap_p"]
        p.setFont(L["f"]["digit"])
        p.setPen(_col(accent.name(), fade))
        p.drawText(QPointF(x, baseline), L["big"])
        x += L["digit_w"]
        if L["unit"]:
            x += L["gap_u"]
            p.setFont(L["f"]["unit"])
            p.setPen(_col(fg.name(), 0.78 * fade))
            p.drawText(QPointF(x, baseline), L["unit"])
        y += L["num_h"]

        # 底部日期
        if L["foot"]:
            y += L["gap_num"] + L["gap_foot"]
            fm_f = L["fm"]["foot"]
            x = row_x(fm_f.horizontalAdvance(L["foot"]))
            p.setFont(L["f"]["foot"])
            p.setPen(_col(fg.name(), faint * fade))
            p.drawText(QPointF(x, y + fm_f.ascent()), L["foot"])
            y += L["foot_h"]

        # 进度条
        if L["has_bar"]:
            y += L["gap_bar"]
            bar = QRectF(left, y, L["content_w"], L["bar_h"])
            p.setPen(Qt.NoPen)
            p.setBrush(_col(fg.name(), 0.16 * fade))
            p.drawRoundedRect(bar, L["bar_h"] / 2, L["bar_h"] / 2)
            prog = max(0.0, min(1.0, info.progress or 0.0))
            if prog > 0.004:
                fill = QRectF(bar.left(), bar.top(), max(L["bar_h"], bar.width() * prog), bar.height())
                p.setBrush(_col(accent.name(), 0.85 * fade))
                p.drawRoundedRect(fill, L["bar_h"] / 2, L["bar_h"] / 2)
            y += L["bar_h"]

        # 页码点
        if L["has_dots"]:
            y += L["gap_dots"]
            d = L["dot_d"]
            n = self._dot_count
            gap = d * 0.95
            total = n * d + (n - 1) * gap
            dx = (left + right) / 2.0 - total / 2.0
            cy = y + d / 2.0
            p.setPen(Qt.NoPen)
            for i in range(n):
                active = (i == self._dot_index)
                p.setBrush(_col(accent.name() if active else fg.name(),
                                (0.9 if active else 0.25) * fade))
                r = d / 2.0 if active else d / 2.6
                p.drawEllipse(QPointF(dx + i * (d + gap) + d / 2.0, cy), r, r)

        p.end()

    # ------------------------------------------------------------ 交互

    def changeEvent(self, event) -> None:
        # 抗「显示桌面」：被最小化时立刻请求恢复
        if event.type() == QEvent.WindowStateChange and (self.windowState() & Qt.WindowMinimized):
            QTimer.singleShot(0, self.restoreRequested.emit)
        super().changeEvent(event)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self.menuRequested.emit(event.globalPosition().toPoint())
            return
        if event.button() == Qt.LeftButton and not self._behavior.get("locked"):
            self._drag_from = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_from is not None:
            self.move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._drag_from is not None:
            self._drag_from = None
            self.unsetCursor()
            self._snap_to_screens()
            self.moved.emit()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.editRequested.emit()

    def wheelEvent(self, event) -> None:
        self.navigated.emit(1 if event.angleDelta().y() < 0 else -1)

    def _snap_to_screens(self) -> None:
        """靠近屏幕边缘时吸附，并保证完整落在某块屏幕内。"""
        screen = self.screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        snap = 18
        x, y = self.x(), self.y()
        if abs(x - area.left()) < snap:
            x = area.left()
        if abs(area.right() - (x + self.width())) < snap:
            x = area.right() - self.width()
        if abs(y - area.top()) < snap:
            y = area.top()
        if abs(area.bottom() - (y + self.height())) < snap:
            y = area.bottom() - self.height()
        x = max(area.left(), min(x, area.right() - self.width()))
        y = max(area.top(), min(y, area.bottom() - self.height()))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    # ------------------------------------------------------------ 轮播淡入淡出

    def crossfade_to(self, info: Info, dot_count: int, dot_index: int) -> None:
        if self._info is None:
            self.set_content(info, dot_count, dot_index)
            return

        def start_fade_in():
            self._info = info
            self._dot_count = dot_count
            self._dot_index = dot_index
            self._layout_cache = None
            self._apply_size()
            self._animate(0.0, 1.0, 220)

        self._animate(1.0, 0.0, 160, on_done=start_fade_in)

    def _animate(self, a: float, b: float, ms: int, on_done=None) -> None:
        if self._fade_anim is not None:
            self._fade_anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(float(a))
        anim.setEndValue(float(b))
        anim.setDuration(ms)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def on_value(v):
            self._fade = float(v)
            self.update()

        anim.valueChanged.connect(on_value)
        if on_done:
            anim.finished.connect(on_done)
        self._fade_anim = anim
        anim.start()
