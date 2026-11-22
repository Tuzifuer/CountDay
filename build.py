# -*- coding: utf-8 -*-
"""打包脚本：生成图标 -> PyInstaller 编译 exe。

用法：
    python build.py            # 单文件 exe（dist/CountDay.exe）
    python build.py --onedir   # 目录版（启动更快，dist/CountDay/CountDay.exe）
    python build.py --icon     # 只重新生成图标
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
ACCENT = (245, 196, 81)
DARK = (27, 33, 43)
LIGHT = (255, 255, 255)


def make_icon() -> Path:
    from PIL import Image, ImageDraw

    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    body = (int(s * 0.09), int(s * 0.15), int(s * 0.91), int(s * 0.93))
    r = int(s * 0.19)

    # 顶栏（强调色）
    d.rounded_rectangle(body, radius=r, fill=ACCENT + (255,))
    # 主体（深色），只留出顶部一条
    page = (body[0], int(s * 0.34), body[2], body[3])
    d.rounded_rectangle(page, radius=r, fill=DARK + (255,))
    d.rectangle((body[0], page[1], body[2], page[1] + r), fill=DARK + (255,))

    # 顶部两个挂环
    ring_w = int(s * 0.055)
    for cx in (body[0] + int(s * 0.22), body[2] - int(s * 0.22)):
        d.rounded_rectangle((cx - ring_w, int(s * 0.06), cx + ring_w, int(s * 0.235)),
                            radius=ring_w, fill=DARK + (255,))

    # 中间圆点
    dot = int(s * 0.075)
    cy = int(s * 0.615)
    d.ellipse((s // 2 - dot, cy - dot, s // 2 + dot, cy + dot), fill=LIGHT + (255,))

    ASSETS.mkdir(parents=True, exist_ok=True)
    ico = ASSETS / "icon.ico"
    img.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                         (128, 128), (256, 256)])
    img.resize((128, 128), Image.LANCZOS).save(ASSETS / "icon_preview.png")
    print(f"icon -> {ico}")
    return ico


def build(onedir: bool) -> int:
    ico = make_icon()
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--name", "CountDay",
           "--icon", str(ico),
           "--distpath", str(ROOT / "dist"),
           "--workpath", str(ROOT / "build"),
           "--specpath", str(ROOT / "build"),
           "--onefile" if not onedir else "--onedir",
           str(ROOT / "main.py")]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    if "--icon" in sys.argv:
        make_icon()
        sys.exit(0)
    sys.exit(build("--onedir" in sys.argv))
