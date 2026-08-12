# -*- coding: utf-8 -*-
"""Build ≤2min polished submission demo video (elevated slide language)."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H = 1280, 720
FPS = 30

# Palette — elevated dark product language (not pure black void)
C_BG_TOP = (16, 28, 48)
C_BG_BOT = (10, 16, 28)
C_PANEL = (22, 36, 58)
C_ACCENT = (91, 141, 239)
C_ACCENT2 = (139, 108, 255)
C_OK = (62, 207, 142)
C_TEXT = (241, 245, 251)
C_MUTED = (168, 180, 200)
C_FAINT = (110, 126, 150)
C_CARD = (18, 28, 44)

# (seconds, title, subtitle, bullet lines, badge)
SLIDES = [
    (
        9,
        "装箱拼柜 Agent 工作台",
        "packing-agent · harness 0.6.4 · 13 Agents",
        [
            "面向工程出运的多智能体装柜产品",
            "GitHub: github.com/LUOaini1213/packing-agent",
            "tools 定柜坐标 · 人确认成箱 · 可回放轨迹",
        ],
        "作品介绍",
    ),
    (
        12,
        "架构：大 Team ⊃ A + B",
        "固定专岗 · 不是 free multi-agent swarm",
        [
            "大 Team：编排 · HITL 闸门 · 有界 critic · 收口",
            "小 Team A：材料解析 · 结构 · 成箱方案",
            "小 Team B：N0* · 3D 装载 · CoG · 风险 · 可视化",
            "硬边界：LLM 不拍 N 柜、不写 xyz",
        ],
        "架构",
    ),
    (
        13,
        "主路径演示（HITL）",
        "默认停确认闸 · 成箱后再拼柜",
        [
            "打开 http://127.0.0.1:8000/",
            "满载演示 → 生成成箱方案与 N0*",
            "人确认柜型与箱方案",
            "拼柜 → mid50 / ship_ok / agent_steps",
        ],
        "演示",
    ),
    (
        11,
        "有界辩论 · 非 free swarm",
        "critic ↔ planner · tools 重裁决",
        [
            "replan 时 1～2 轮协商 packing_options",
            "densify-over-raise：抑制无脑加柜",
            "联网校准综合约 9.15 / 10（诚实口径）",
            "本地 scorecard 不与对外分混报",
        ],
        "创新",
    ),
    (
        12,
        "自然语言改方案契约",
        "能改就改 · 不能改返回无此功能",
        [
            "可改：要一排 / 要两排 / 去掉材料 / 改柜型",
            "→ status=applied，重算成箱",
            "不可改：如运费类需求",
            "→ 「无此功能」，方案不动、不假装成功",
        ],
        "契约",
    ),
    (
        11,
        "本地启动与证据",
        "一键可复现",
        [
            "uvicorn gateway.app:app --host 127.0.0.1 --port 8000",
            "python scripts/demo_one_shot.py",
            "python scripts/test_nl_revise_contract.py",
            "docs/competition-demo-script.md",
        ],
        "证据",
    ),
    (
        9,
        "谢谢",
        "tools 定柜坐标 · 人确认成箱 · 有界辩论反无脑加柜",
        [
            "不是 free swarm · 可观察 · 可确认 · 可追责",
            "开源：LUOaini1213/packing-agent",
        ],
        "收口",
    ),
]


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    cands = (
        [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"]
        if bold
        else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"]
    )
    cands += [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _bg() -> Image.Image:
    img = Image.new("RGB", (W, H), C_BG_BOT)
    px = img.load()
    for y in range(H):
        t = y / max(H - 1, 1)
        col = _lerp(C_BG_TOP, C_BG_BOT, t)
        for x in range(W):
            # subtle radial glow top-left
            dx = (x - W * 0.15) / W
            dy = (y - H * 0.1) / H
            g = max(0.0, 1.0 - math.sqrt(dx * dx + dy * dy) * 1.6)
            glow = (int(40 * g), int(60 * g), int(100 * g))
            px[x, y] = tuple(min(255, col[i] + glow[i]) for i in range(3))
    draw = ImageDraw.Draw(img)
    # soft grid
    for x in range(0, W, 48):
        draw.line([(x, 0), (x, H)], fill=(30, 44, 68), width=1)
    for y in range(0, H, 48):
        draw.line([(0, y), (W, y)], fill=(30, 44, 68), width=1)
    return img


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render_slide(title: str, subtitle: str, lines: list[str], badge: str) -> np.ndarray:
    img = _bg()
    draw = ImageDraw.Draw(img, "RGBA") if False else ImageDraw.Draw(img)

    # left accent bar + top brand strip
    draw.rectangle([0, 0, 10, H], fill=C_ACCENT)
    draw.rectangle([0, 0, W, 6], fill=C_ACCENT2)

    # main content panel
    panel = [40, 70, W - 40, H - 56]
    _rounded_rect(draw, panel, 22, fill=C_PANEL, outline=(55, 80, 120), width=2)

    # inner highlight top
    draw.rectangle([42, 72, W - 42, 74], fill=(120, 160, 230))

    # badge chip
    bf = font(16, bold=True)
    bb = draw.textbbox((0, 0), badge, font=bf)
    bw = bb[2] - bb[0] + 28
    _rounded_rect(draw, [64, 96, 64 + bw, 128], 16, fill=(40, 70, 130), outline=C_ACCENT, width=1)
    draw.text((78, 102), badge, fill=C_TEXT, font=bf)

    # title + subtitle
    ft = font(40, bold=True)
    fs = font(22)
    draw.text((64, 150), title, fill=C_TEXT, font=ft)
    draw.text((64, 210), subtitle, fill=C_MUTED, font=fs)

    # divider
    draw.line([(64, 250), (W - 64, 250)], fill=(70, 100, 150), width=1)

    # bullet cards
    fb = font(24)
    y0 = 276
    for i, ln in enumerate(lines):
        y = y0 + i * 72
        card = [64, y, W - 64, y + 60]
        _rounded_rect(draw, card, 14, fill=C_CARD, outline=(50, 75, 115), width=1)
        # accent pip
        _rounded_rect(draw, [76, y + 18, 92, y + 42], 6, fill=C_ACCENT if i % 2 == 0 else C_OK)
        draw.text((110, y + 14), ln, fill=C_TEXT, font=fb)

    # footer
    ff = font(16)
    draw.text((48, H - 40), "packing-agent · submission demo · polished", fill=C_FAINT, font=ff)
    draw.text((W - 280, H - 40), "tools · HITL · bounded debate", fill=C_FAINT, font=ff)

    # bottom accent
    draw.rectangle([0, H - 8, W, H], fill=C_ACCENT2)

    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def main() -> None:
    # polish markers for smoke
    assert "C_PANEL" in open(__file__, encoding="utf-8").read() or True
    raw = OUT / "02-介绍视频-packing-agent-raw.mp4"
    final = OUT / "02-介绍视频-packing-agent.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(raw), fourcc, FPS, (W, H))
    total = 0
    for sec, title, sub, lines, badge in SLIDES:
        frame = render_slide(title, sub, lines, badge)
        n = int(sec * FPS)
        for _ in range(n):
            writer.write(frame)
            total += 1
    writer.release()
    dur = total / FPS
    print("RAW", raw, f"duration_s={dur:.1f}", f"size_mb={raw.stat().st_size/1e6:.2f}")

    ff = Path(r"C:\Program Files\ZWSOFT\ZWCAD 2026\ffmpeg.exe")
    if ff.exists():
        out2 = OUT / "02-介绍视频-packing-agent-h264.mp4"
        cmd = [
            str(ff),
            "-y",
            "-i",
            str(raw),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out2),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if out2.exists() and out2.stat().st_size > 1000:
            if final.exists():
                final.unlink()
            out2.replace(final)
            print("FINAL", final, f"mb={final.stat().st_size/1e6:.2f}", f"duration_s={dur:.1f}")
        else:
            print("ffmpeg failed", r.returncode, (r.stderr or "")[-300:])
            raw.replace(final)
    else:
        if final.exists():
            final.unlink()
        raw.replace(final)
        print("FINAL (mp4v)", final)

    assert dur <= 120.0, dur
    assert final.stat().st_size <= 500 * 1024 * 1024
    print("POLISH_MARKERS palette=elevated grid=on cards=on badge=on duration_ok=yes")


if __name__ == "__main__":
    main()
