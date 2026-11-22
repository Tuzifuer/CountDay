# -*- coding: utf-8 -*-
"""配置读写：%APPDATA%\\CountDay\\config.json"""
from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

APP_NAME = "CountDay"
APP_DISPLAY_NAME = "桌面倒计日"
APP_VERSION = "1.0.0"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


CONFIG_PATH = app_data_dir() / "config.json"

# ---------------------------------------------------------------- 默认样式

DEFAULT_STYLE = {
    "preset": "ink",
    "bg_color": "#151A22",
    "bg_opacity": 0.66,
    "fg_color": "#FFFFFF",
    "accent_color": "#F5C451",
    "radius": 18.0,
    "font_family": "Microsoft YaHei UI",
    "digit_family": "",
    "font_size": 15.0,      # 基准字号（px），其它字号按比例派生
    "digit_scale": 4.3,     # 大数字相对基准字号的倍率
    "align": "center",      # center / left / right
    "show_title": True,
    "show_date": True,
    "show_weekday": True,
    "show_progress": False,
    "show_dots": True,
    "show_shadow": True,
    "letter_spacing": 0.6,
}

DEFAULT_BEHAVIOR = {
    "mode": "bottom",        # bottom=桌面置底 / top=置顶 / normal=普通窗口
    "locked": False,
    "rotate": True,          # 多事件自动轮播
    "rotate_interval": 8,    # 秒
    "calc_mode": "natural",  # natural=自然日 / urgent=紧迫（满 24 小时才算一天）
    "autostart": False,
    "remind": True,          # 当天托盘提醒
}

DEFAULT_WINDOW = {"x": None, "y": None}


def _new_event(title: str, day: date, kind: str = "countdown") -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "date": day.isoformat(),
        "type": kind,
        "created": date.today().isoformat(),
    }


def default_events() -> list[dict]:
    today = date.today()
    return [
        _new_event("元旦", date(today.year + 1, 1, 1)),
        _new_event("项目交付", today + timedelta(days=45)),
        _new_event("入职纪念日", today - timedelta(days=365), "anniversary"),
    ]


def default_config() -> dict:
    return {
        "version": APP_VERSION,
        "events": default_events(),
        "style": copy.deepcopy(DEFAULT_STYLE),
        "behavior": copy.deepcopy(DEFAULT_BEHAVIOR),
        "window": copy.deepcopy(DEFAULT_WINDOW),
        "current_index": 0,
    }


# ---------------------------------------------------------------- 校验 / 合并

def _clean_event(raw: dict) -> dict | None:
    try:
        title = str(raw.get("title", "")).strip() or "未命名"
        d = date.fromisoformat(str(raw.get("date"))[:10])
    except Exception:
        return None
    kind = raw.get("type") if raw.get("type") in ("countdown", "anniversary") else "countdown"
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
        "title": title,
        "date": d.isoformat(),
        "type": kind,
        "created": str(raw.get("created") or date.today().isoformat())[:10],
    }


def _merge(default: dict, loaded: dict) -> dict:
    out = copy.deepcopy(default)
    for k, v in loaded.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    if not CONFIG_PATH.exists():
        cfg = default_config()
        save(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        # 配置损坏时备份并重建，避免软件无法启动
        try:
            CONFIG_PATH.replace(CONFIG_PATH.with_suffix(".bad.json"))
        except Exception:
            pass
        cfg = default_config()
        save(cfg)
        return cfg

    cfg = _merge(default_config(), raw if isinstance(raw, dict) else {})
    events = [e for e in (_clean_event(x) for x in cfg.get("events", []) if isinstance(x, dict)) if e]
    cfg["events"] = events or default_events()
    try:
        cfg["current_index"] = max(0, min(int(cfg.get("current_index", 0)), len(cfg["events"]) - 1))
    except Exception:
        cfg["current_index"] = 0
    return cfg


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
