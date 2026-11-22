# -*- coding: utf-8 -*-
"""倒计日 / 纪念日的日期计算与文案生成。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@dataclass
class Info:
    title: str
    big: str                 # 大号字：数字或"今天"
    unit: str                # 大号字后面的单位："天"
    prefix: str              # 大号字前面的引导词："还有" / "已经" / "已过"
    foot: str                # 底部小字：日期 · 周几
    state: str               # future / today / past
    progress: float | None   # 0~1，可为 None
    date: date


def parse_date(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def _fmt_foot(d: date, show_date: bool, show_weekday: bool) -> str:
    parts = []
    if show_date:
        parts.append(d.strftime("%Y-%m-%d"))
    if show_weekday:
        parts.append(WEEKDAYS[d.weekday()])
    return "  ·  ".join(parts)


def _progress(created: date, target: date, today: date) -> float | None:
    total = (target - created).days
    if total <= 0:
        return None
    done = (today - created).days
    return max(0.0, min(1.0, done / total))


def compute(event: dict, calc_mode: str = "natural", style: dict | None = None,
            now: datetime | None = None) -> Info:
    style = style or {}
    show_date = style.get("show_date", True)
    show_weekday = style.get("show_weekday", True)

    now = now or datetime.now()
    today = now.date()
    target = parse_date(event["date"])
    kind = event.get("type", "countdown")
    created = parse_date(event.get("created") or today.isoformat())
    foot = _fmt_foot(target, show_date, show_weekday)

    if kind == "anniversary":
        days = (today - target).days
        if days == 0:
            return Info(event["title"], "今天", "", "", foot, "today", None, target)
        return Info(event["title"], str(days), "天", "已经", foot, "past",
                    _progress(target, today, today), target)

    # 倒计时
    if calc_mode == "urgent":
        if target == today:
            return Info(event["title"], "今天", "", "", foot, "today", None, target)
        remain = (datetime.combine(target, dtime(0, 0)) - now).total_seconds()
        if remain > 0:
            days = int(remain // 86400)
            return Info(event["title"], str(days), "天", "还有", foot,
                        "future" if days > 0 else "today",
                        _progress(created, target, today), target)
        days = max(1, (today - target).days)
        return Info(event["title"], str(days), "天", "已过", foot, "past", 1.0, target)

    days = (target - today).days
    if days > 0:
        return Info(event["title"], str(days), "天", "还有", foot, "future",
                    _progress(created, target, today), target)
    if days == 0:
        return Info(event["title"], "今天", "", "", foot, "today", None, target)
    return Info(event["title"], str(-days), "天", "已过", foot, "past", 1.0, target)


def sort_key(event: dict) -> tuple:
    """未来事件在前，按日期升序；已过事件在后。"""
    d = parse_date(event["date"])
    today = date.today()
    return (1 if d < today else 0, d)
