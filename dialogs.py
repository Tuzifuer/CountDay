# -*- coding: utf-8 -*-
"""事件编辑对话框 + 设置面板。"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDateEdit,
                               QDialog, QDialogButtonBox, QDoubleSpinBox, QFontComboBox,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSlider,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

import theme

QSS = """
QDialog { background: #F6F7F9; }
QLabel { color: #2B3038; }
QGroupBox { font-weight: 600; color: #2B3038; border: 1px solid #DEE2E8;
            border-radius: 8px; margin-top: 12px; padding: 10px 12px 12px 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QDateEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF; border: 1px solid #D6DBE2; border-radius: 6px;
    padding: 5px 8px; min-height: 20px; }
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #3B82F6; }
QPushButton { background: #FFFFFF; border: 1px solid #D6DBE2; border-radius: 6px;
              padding: 6px 14px; min-height: 20px; }
QPushButton:hover { background: #EEF2F7; }
QPushButton:default { background: #2563EB; color: #FFFFFF; border-color: #2563EB; }
QPushButton:default:hover { background: #1D4ED8; }
QListWidget { background: #FFFFFF; border: 1px solid #D6DBE2; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 6px 8px; border-radius: 5px; }
QListWidget::item:selected { background: #DCE9FF; color: #12325F; }
QTabWidget::pane { border: 1px solid #DEE2E8; border-radius: 8px; background: #FFFFFF; }
QTabBar::tab { padding: 7px 18px; margin-right: 2px; border: 1px solid #DEE2E8;
               border-bottom: none; border-top-left-radius: 7px; border-top-right-radius: 7px;
               background: #EDF0F4; color: #4B5563; }
QTabBar::tab:selected { background: #FFFFFF; color: #1F2937; font-weight: 600; }
QCheckBox { color: #2B3038; }
"""


# ---------------------------------------------------------------- 事件编辑

class EventDialog(QDialog):
    def __init__(self, parent=None, event: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("编辑事件" if event else "新建事件")
        self.setStyleSheet(QSS)
        self.setMinimumWidth(360)
        self._event = dict(event) if event else None

        self.title_edit = QLineEdit(self._event["title"] if self._event else "")
        self.title_edit.setPlaceholderText("例如：春节 / 项目上线 / 生日")

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        d = date.fromisoformat(self._event["date"]) if self._event else date.today() + timedelta(days=30)
        self.date_edit.setDate(QDate(d.year, d.month, d.day))

        self.type_combo = QComboBox()
        self.type_combo.addItem("倒计日（还有 N 天）", "countdown")
        self.type_combo.addItem("纪念日（已经 N 天）", "anniversary")
        if self._event and self._event.get("type") == "anniversary":
            self.type_combo.setCurrentIndex(1)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("事件名称", self.title_edit)
        form.addRow("目标日期", self.date_edit)
        form.addRow("类型", self.type_combo)

        hint = QLabel("提示：拖动卡片可移动位置；右键卡片有完整菜单。")
        hint.setStyleSheet("color:#6B7280; font-size:12px;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        lay.setSpacing(12)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(buttons)

    def _on_ok(self) -> None:
        if not self.title_edit.text().strip():
            self.title_edit.setFocus()
            self.title_edit.setPlaceholderText("请填写事件名称")
            return
        self.accept()

    def result_event(self) -> dict:
        qd = self.date_edit.date()
        ev = dict(self._event) if self._event else {
            "id": uuid.uuid4().hex[:12],
            "created": date.today().isoformat(),
        }
        ev["title"] = self.title_edit.text().strip()
        ev["date"] = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
        ev["type"] = self.type_combo.currentData()
        return ev


# ---------------------------------------------------------------- 颜色小按钮

class ColorButton(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(84, 26)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self) -> None:
        self.setText(self._color.upper())
        c = QColor(self._color)
        fg = "#111111" if c.lightness() > 140 else "#FFFFFF"
        self.setStyleSheet(
            f"QPushButton {{ background:{self._color}; color:{fg}; border:1px solid #D6DBE2;"
            f" border-radius:6px; font-size:11px; padding:0; }}")

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "选择颜色")
        if c.isValid():
            self._color = c.name()
            self._refresh()

    def color(self) -> str:
        return self._color


# ---------------------------------------------------------------- 设置面板

class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("桌面倒计日 · 设置")
        self.setStyleSheet(QSS)
        self.setMinimumSize(560, 520)
        self._cfg = cfg
        self.events = [dict(e) for e in cfg["events"]]
        st, bh = cfg["style"], cfg["behavior"]

        tabs = QTabWidget()
        tabs.addTab(self._tab_events(), "事件")
        tabs.addTab(self._tab_style(st), "外观")
        tabs.addTab(self._tab_behavior(bh), "行为")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存并应用")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 12)
        lay.addWidget(tabs)
        lay.addWidget(buttons)

    # -------------------------------------------------- 事件页

    def _tab_events(self) -> QWidget:
        page = QWidget()
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._reload_list()

        btn_new = QPushButton("新建")
        btn_edit = QPushButton("编辑")
        btn_del = QPushButton("删除")
        btn_up = QPushButton("上移")
        btn_down = QPushButton("下移")
        btn_new.clicked.connect(self._new_event)
        btn_edit.clicked.connect(self._edit_event)
        btn_del.clicked.connect(self._del_event)
        btn_up.clicked.connect(lambda: self._move_event(-1))
        btn_down.clicked.connect(lambda: self._move_event(1))
        self.list.itemDoubleClicked.connect(lambda *_: self._edit_event())

        col = QVBoxLayout()
        for b in (btn_new, btn_edit, btn_del, btn_up, btn_down):
            col.addWidget(b)
        col.addStretch(1)

        row = QHBoxLayout()
        row.addWidget(self.list, 1)
        row.addLayout(col)

        tip = QLabel("多个事件时会按「行为」页的间隔自动轮播；右键卡片可快速切换/编辑。")
        tip.setStyleSheet("color:#6B7280; font-size:12px;")
        tip.setWordWrap(True)

        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addLayout(row)
        lay.addWidget(tip)
        return page

    def _reload_list(self, select: int | None = None) -> None:
        cur = self.list.currentRow() if select is None else select
        self.list.clear()
        for e in self.events:
            kind = "纪念日" if e.get("type") == "anniversary" else "倒计日"
            item = QListWidgetItem(f"{e['title']}    {e['date']}    {kind}")
            self.list.addItem(item)
        if self.events:
            self.list.setCurrentRow(max(0, min(cur, len(self.events) - 1)))

    def _new_event(self) -> None:
        dlg = EventDialog(self)
        if dlg.exec():
            self.events.append(dlg.result_event())
            self._reload_list(len(self.events) - 1)

    def _edit_event(self) -> None:
        i = self.list.currentRow()
        if not (0 <= i < len(self.events)):
            return
        dlg = EventDialog(self, self.events[i])
        if dlg.exec():
            self.events[i] = dlg.result_event()
            self._reload_list(i)

    def _del_event(self) -> None:
        i = self.list.currentRow()
        if 0 <= i < len(self.events):
            self.events.pop(i)
            self._reload_list(max(0, i - 1))

    def _move_event(self, step: int) -> None:
        i = self.list.currentRow()
        j = i + step
        if 0 <= i < len(self.events) and 0 <= j < len(self.events):
            self.events[i], self.events[j] = self.events[j], self.events[i]
            self._reload_list(j)

    # -------------------------------------------------- 外观页

    def _tab_style(self, st: dict) -> QWidget:
        page = QWidget()
        self.preset_combo = QComboBox()
        for p in theme.PRESETS:
            self.preset_combo.addItem(p["name"], p["id"])
        idx = max(0, self.preset_combo.findData(st.get("preset", "ink")))
        self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.currentIndexChanged.connect(self._on_preset)

        self.btn_bg = ColorButton(st.get("bg_color", "#151A22"))
        self.btn_fg = ColorButton(st.get("fg_color", "#FFFFFF"))
        self.btn_accent = ColorButton(st.get("accent_color", "#F5C451"))

        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(int(round(float(st.get("bg_opacity", 0.66)) * 100)))
        self.lbl_opacity = QLabel("背景不透明度")

        def _on_opacity(v: int) -> None:
            self.lbl_opacity.setText(f"背景不透明度 {v}%")

        self.opacity.valueChanged.connect(_on_opacity)
        _on_opacity(self.opacity.value())

        self.radius = QSlider(Qt.Horizontal)
        self.radius.setRange(0, 36)
        self.radius.setValue(int(float(st.get("radius", 18))))

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(st.get("font_family", "Microsoft YaHei UI")))

        self.digit_combo = QComboBox()
        self.digit_combo.addItem("跟随正文字体", "")
        for fam in QFontDatabase.families():
            self.digit_combo.addItem(fam, fam)
        di = self.digit_combo.findData(st.get("digit_family", ""))
        self.digit_combo.setCurrentIndex(max(0, di))

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(9.0, 30.0)
        self.size_spin.setSingleStep(0.5)
        self.size_spin.setValue(float(st.get("font_size", 15.0)))
        self.size_spin.setSuffix(" px")
        self.size_spin.setMinimumWidth(96)

        self.digit_scale = QDoubleSpinBox()
        self.digit_scale.setRange(2.0, 8.0)
        self.digit_scale.setSingleStep(0.1)
        self.digit_scale.setValue(float(st.get("digit_scale", 4.3)))
        self.digit_scale.setSuffix(" 倍")
        self.digit_scale.setMinimumWidth(96)

        self.align_combo = QComboBox()
        for label, val in (("居中", "center"), ("靠左", "left"), ("靠右", "right")):
            self.align_combo.addItem(label, val)
        self.align_combo.setCurrentIndex(max(0, self.align_combo.findData(st.get("align", "center"))))
        self.align_combo.setMinimumWidth(96)

        self.cb_title = QCheckBox("显示事件名")
        self.cb_title.setChecked(bool(st.get("show_title", True)))
        self.cb_date = QCheckBox("显示日期")
        self.cb_date.setChecked(bool(st.get("show_date", True)))
        self.cb_week = QCheckBox("显示星期")
        self.cb_week.setChecked(bool(st.get("show_weekday", True)))
        self.cb_prog = QCheckBox("显示进度条")
        self.cb_prog.setChecked(bool(st.get("show_progress", False)))
        self.cb_dots = QCheckBox("显示轮播页码点")
        self.cb_dots.setChecked(bool(st.get("show_dots", True)))
        self.cb_shadow = QCheckBox("显示投影")
        self.cb_shadow.setChecked(bool(st.get("show_shadow", True)))

        gb_color = QGroupBox("配色")
        g1 = QGridLayout(gb_color)
        g1.addWidget(QLabel("主题预设"), 0, 0)
        g1.addWidget(self.preset_combo, 0, 1, 1, 3)
        g1.addWidget(QLabel("背景色"), 1, 0)
        g1.addWidget(self.btn_bg, 1, 1)
        g1.addWidget(QLabel("文字色"), 1, 2)
        g1.addWidget(self.btn_fg, 1, 3)
        g1.addWidget(QLabel("强调色"), 2, 0)
        g1.addWidget(self.btn_accent, 2, 1)
        g1.addWidget(self.lbl_opacity, 2, 2)
        g1.addWidget(self.opacity, 2, 3)
        g1.setColumnStretch(3, 1)
        g1.setColumnStretch(1, 0)

        gb_font = QGroupBox("字体与排版")
        g2 = QFormLayout(gb_font)
        g2.addRow("正文字体", self.font_combo)
        g2.addRow("数字字体", self.digit_combo)
        gb_size = QHBoxLayout()
        gb_size.addWidget(self.size_spin)
        gb_size.addSpacing(10)
        gb_size.addWidget(QLabel("数字放大"))
        gb_size.addWidget(self.digit_scale)
        gb_size.addStretch(1)
        g2.addRow("基准字号", gb_size)
        gb_size2 = QHBoxLayout()
        gb_size2.addWidget(self.align_combo)
        gb_size2.addSpacing(10)
        gb_size2.addWidget(QLabel("圆角"))
        gb_size2.addWidget(self.radius, 1)
        g2.addRow("对齐 / 圆角", gb_size2)

        gb_items = QGroupBox("显示内容")
        g3 = QGridLayout(gb_items)
        for i, cb in enumerate((self.cb_title, self.cb_date, self.cb_week,
                                self.cb_prog, self.cb_dots, self.cb_shadow)):
            g3.addWidget(cb, i // 3, i % 3)

        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        lay.addWidget(gb_color)
        lay.addWidget(gb_font)
        lay.addWidget(gb_items)
        lay.addStretch(1)
        return page

    def _on_preset(self) -> None:
        p = theme.get(self.preset_combo.currentData())
        for btn, key in ((self.btn_bg, "bg_color"), (self.btn_fg, "fg_color"),
                         (self.btn_accent, "accent_color")):
            btn._color = p[key]
            btn._refresh()
        self.opacity.setValue(int(round(p["bg_opacity"] * 100)))

    # -------------------------------------------------- 行为页

    def _tab_behavior(self, bh: dict) -> QWidget:
        page = QWidget()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("桌面置底（贴在最底层，不挡其他窗口）", "bottom")
        self.mode_combo.addItem("窗口置顶（始终显示在最前）", "top")
        self.mode_combo.addItem("普通窗口（可被遮挡）", "normal")
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(bh.get("mode", "bottom"))))

        self.cb_locked = QCheckBox("锁定位置（防止误拖动）")
        self.cb_locked.setChecked(bool(bh.get("locked", False)))

        self.cb_rotate = QCheckBox("多事件自动轮播")
        self.cb_rotate.setChecked(bool(bh.get("rotate", True)))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(3, 120)
        self.spin_interval.setValue(int(bh.get("rotate_interval", 8)))
        self.spin_interval.setSuffix(" 秒")
        self.spin_interval.setMinimumWidth(96)

        self.calc_combo = QComboBox()
        self.calc_combo.addItem("自然日（按日期差，明天就是 1 天）", "natural")
        self.calc_combo.addItem("紧迫（满 24 小时才算 1 天）", "urgent")
        self.calc_combo.setCurrentIndex(max(0, self.calc_combo.findData(bh.get("calc_mode", "natural"))))

        self.cb_autostart = QCheckBox("开机自动启动")
        self.cb_autostart.setChecked(bool(bh.get("autostart", False)))
        self.cb_remind = QCheckBox("当天在托盘提醒我")
        self.cb_remind.setChecked(bool(bh.get("remind", True)))

        gb_win = QGroupBox("窗口层级")
        f1 = QFormLayout(gb_win)
        f1.addRow("显示模式", self.mode_combo)
        f1.addRow("", self.cb_locked)

        gb_rot = QGroupBox("轮播与计算")
        f2 = QFormLayout(gb_rot)
        row = QHBoxLayout()
        row.addWidget(self.cb_rotate)
        row.addWidget(self.spin_interval)
        row.addStretch(1)
        f2.addRow("轮播", row)
        f2.addRow("计算方式", self.calc_combo)

        gb_misc = QGroupBox("系统")
        f3 = QVBoxLayout(gb_misc)
        f3.addWidget(self.cb_autostart)
        f3.addWidget(self.cb_remind)
        btn_reset = QPushButton("重置卡片位置")
        btn_reset.setMaximumWidth(160)
        btn_reset.clicked.connect(self._reset_pos)
        row_reset = QHBoxLayout()
        row_reset.addWidget(btn_reset)
        row_reset.addStretch(1)
        f3.addLayout(row_reset)

        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        lay.addWidget(gb_win)
        lay.addWidget(gb_rot)
        lay.addWidget(gb_misc)
        lay.addStretch(1)
        return page

    def _reset_pos(self) -> None:
        self._reset_pos_flag = True

    _reset_pos_flag = False

    # -------------------------------------------------- 结果

    def result_data(self) -> dict:
        st = {
            "preset": self.preset_combo.currentData(),
            "bg_color": self.btn_bg.color(),
            "fg_color": self.btn_fg.color(),
            "accent_color": self.btn_accent.color(),
            "bg_opacity": round(self.opacity.value() / 100.0, 3),
            "radius": float(self.radius.value()),
            "font_family": self.font_combo.currentFont().family(),
            "digit_family": self.digit_combo.currentData() or "",
            "font_size": float(self.size_spin.value()),
            "digit_scale": float(self.digit_scale.value()),
            "align": self.align_combo.currentData(),
            "show_title": self.cb_title.isChecked(),
            "show_date": self.cb_date.isChecked(),
            "show_weekday": self.cb_week.isChecked(),
            "show_progress": self.cb_prog.isChecked(),
            "show_dots": self.cb_dots.isChecked(),
            "show_shadow": self.cb_shadow.isChecked(),
            "letter_spacing": float(self._cfg["style"].get("letter_spacing", 0.6)),
        }
        bh = {
            "mode": self.mode_combo.currentData(),
            "locked": self.cb_locked.isChecked(),
            "rotate": self.cb_rotate.isChecked(),
            "rotate_interval": int(self.spin_interval.value()),
            "calc_mode": self.calc_combo.currentData(),
            "autostart": self.cb_autostart.isChecked(),
            "remind": self.cb_remind.isChecked(),
        }
        return {"events": self.events, "style": st, "behavior": bh,
                "reset_position": self._reset_pos_flag}
