"""片头/片尾卡（1920x1080，配色沿用 build_demo_video 的深海军蓝 + 蓝紫渐变强调）。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(r"C:\Users\LW\civil-buddy\output\submission")
W, H = 1920, 1080
BG_TOP, BG_BOT = (10, 16, 30), (16, 26, 46)
ACCENT, ACCENT2 = (91, 141, 239), (139, 108, 255)
TEXT, MUTED, FAINT = (241, 245, 251), (168, 180, 200), (110, 126, 150)
CARD = (18, 28, 44)
OK = (62, 207, 142)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(path, size)


def base() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        px_row = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = px_row
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 96):
        d.line([(gx, 0), (gx, H)], fill=(22, 32, 52), width=1)
    for gy in range(0, H, 96):
        d.line([(0, gy), (W, gy)], fill=(22, 32, 52), width=1)
    # 顶/底渐变条
    for x in range(W):
        t = x / W
        c = tuple(int(ACCENT[i] + (ACCENT2[i] - ACCENT[i]) * t) for i in range(3))
        d.line([(x, 0), (x, 10)], fill=c)
        d.line([(x, H - 10), (x, H)], fill=c)
    return img


def center(d: ImageDraw.ImageDraw, y: int, text: str, f: ImageFont.FreeTypeFont, fill) -> None:
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


# ---------- 片头 ----------
img = base()
d = ImageDraw.Draw(img)
badge = "第一届「海之子」杯 AI 智能体挑战计划"
bf = font(34)
bw = d.textlength(badge, font=bf)
bx = (W - bw) / 2
d.rounded_rectangle([bx - 28, 240, bx + bw + 28, 308], radius=34, outline=ACCENT, width=2)
d.text((bx, 254), badge, font=bf, fill=MUTED)
center(d, 380, "Civil Buddy", font(150, bold=True), TEXT)
center(d, 585, "土木版 Codex · 66 岗智能体工作台", font(58, bold=True), TEXT)
center(d, 690, "自然语言召唤专家 · 工具算数字 · 人做决定", font(40), MUTED)
center(d, 860, "github.com/LUOaini1213/civil-buddy", font(32), FAINT)
img.save(OUT / "card_title.png")

# ---------- 片尾 ----------
img = base()
d = ImageDraw.Draw(img)
center(d, 130, "全部可复跑", font(56, bold=True), TEXT)
chips = [
    ("128 组", "自动装箱评测（16×8 扇出）"),
    ("12 / 12", "phase0 基线全过 · 无需 Key"),
    ("8.85 / 10", "本地校准综合分"),
]
cw, ch, gap = 520, 240, 60
x0 = (W - cw * 3 - gap * 2) / 2
for i, (num, label) in enumerate(chips):
    x = x0 + i * (cw + gap)
    d.rounded_rectangle([x, 250, x + cw, 250 + ch], radius=22, fill=CARD, outline=(40, 56, 84), width=2)
    nf = font(76, bold=True)
    nw = d.textlength(num, font=nf)
    d.text((x + (cw - nw) / 2, 296), num, font=nf, fill=OK if i < 2 else ACCENT)
    lf = font(30)
    lw = d.textlength(label, font=lf)
    d.text((x + (cw - lw) / 2, 410), label, font=lf, fill=MUTED)
center(d, 600, "工具算数字 · 人做决定", font(72, bold=True), TEXT)
center(d, 740, "产出均为 AI 草稿 · 高风险须持证人员签认", font(38), MUTED)
center(d, 850, "开源 MIT · github.com/LUOaini1213/civil-buddy · 免安装试用包见 Releases", font(34), FAINT)
img.save(OUT / "card_end.png")
print("OK 两张卡已生成（1920x1080）")
