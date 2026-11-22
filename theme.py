# -*- coding: utf-8 -*-
"""外观预设。"""

PRESETS: list[dict] = [
    {"id": "ink", "name": "曜石黑", "bg_color": "#151A22", "fg_color": "#FFFFFF",
     "accent_color": "#F5C451", "bg_opacity": 0.66},
    {"id": "frost", "name": "霜白", "bg_color": "#FFFFFF", "fg_color": "#1B2430",
     "accent_color": "#E4572E", "bg_opacity": 0.82},
    {"id": "ocean", "name": "深海蓝", "bg_color": "#0E2A47", "fg_color": "#EAF4FF",
     "accent_color": "#4FC3F7", "bg_opacity": 0.70},
    {"id": "mint", "name": "薄荷绿", "bg_color": "#10241F", "fg_color": "#E8FFF6",
     "accent_color": "#4ADE80", "bg_opacity": 0.66},
    {"id": "sakura", "name": "樱粉", "bg_color": "#2A1620", "fg_color": "#FFEFF5",
     "accent_color": "#FF7BA9", "bg_opacity": 0.68},
    {"id": "paper", "name": "纸感浅灰", "bg_color": "#F2F0EC", "fg_color": "#2A2A28",
     "accent_color": "#C2410C", "bg_opacity": 0.88},
    {"id": "glass", "name": "极简透明", "bg_color": "#000000", "fg_color": "#FFFFFF",
     "accent_color": "#FFFFFF", "bg_opacity": 0.0},
]


def get(preset_id: str) -> dict:
    for p in PRESETS:
        if p["id"] == preset_id:
            return p
    return PRESETS[0]


def apply_preset(style: dict, preset_id: str) -> dict:
    p = get(preset_id)
    out = dict(style)
    out["preset"] = p["id"]
    for k in ("bg_color", "fg_color", "accent_color", "bg_opacity"):
        out[k] = p[k]
    return out
