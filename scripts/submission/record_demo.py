"""真机演示录屏：exe 的 Civil Buddy → 自然语言「装箱」→ 内嵌装柜台 → 三步剧本全程。

控件链路（手动验证过）：
  开始第 1 步 · 满载演示 → [Team A 计算] → 去第 2 步 出现（停 HITL）
  → 演示一键勾选（非标预检 11 项）→ 确认并拼柜 · resume → [Team B]
  → 看第 3 步 出现 → 可视化 tab → 看第 3 步 · 总览裁决

时间轴机制：每个场景开场打点（mark），场景至少持续该段口播时长 + 缓冲；
动作等待超过口播就顺延——音轨按打点摆放，画音必对齐。
"""
import json
import time
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(r"C:\Users\LW\civil-buddy")
SUB = ROOT / "output/submission"
TTS = SUB / "tts_demo"
VID_DIR = SUB / "rec"
VID_DIR.mkdir(exist_ok=True)
for old in VID_DIR.glob("*.webm"):
    old.unlink()

def wav_dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()

SEGS = ["s0_intro", "s1_nl", "s2_teama", "s3_hitl", "s4_confirm", "s5_visual", "s6_verdict"]
DUR = {s: wav_dur(TTS / f"{s}.wav") for s in SEGS}

marks: list[tuple[str, float]] = []
t0 = 0.0

def now() -> float:
    return time.time() - t0

def mark(seg: str) -> None:
    marks.append((seg, now()))
    print(f"  [{now():6.1f}s] {seg}")

def hold(seg: str, pad: float = 1.0) -> None:
    start = dict(marks)[seg]
    end = start + DUR[seg] + pad
    while now() < end:
        time.sleep(0.1)

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir=str(VID_DIR),
        record_video_size={"width": 1280, "height": 720},
    )
    page = ctx.new_page()
    t0 = time.time()

    # S0 首屏
    page.goto("http://127.0.0.1:8765/")
    page.wait_for_selector("#cbEmpty", state="visible", timeout=20000)
    mark("s0_intro")
    hold("s0_intro", 1.2)

    # S1 自然语言输入「装箱」→ 内嵌装柜台 → 放大
    mark("s1_nl")
    page.click("#input")
    page.locator("#input").press_sequentially("装箱", delay=450)
    time.sleep(0.8)
    page.press("#input", "Enter")
    page.wait_for_selector("#cbPackEmbed iframe", state="attached", timeout=20000)
    time.sleep(2.2)  # 让评委看清嵌入面板出现
    page.click('#cbPackEmbed button:has-text("放大")')
    hold("s1_nl", 1.0)

    frame = page.frame_locator("#cbPackEmbed iframe")

    # S2 满载成箱（Team A，口播盖住计算期）；完成标志 = 「去第 2 步」出现
    mark("s2_teama")
    frame.locator('button.primary-lg:has-text("开始第 1 步")').click()
    frame.locator('button:has-text("去第 2 步")').wait_for(state="visible", timeout=90000)
    hold("s2_teama", 0.8)

    # S3 停在确认闸：滚到 HITL 区，末尾把非标预检一键勾上（演示辅助）
    mark("s3_hitl")
    frame.locator('button:has-text("去第 2 步")').click()
    time.sleep(min(6.0, DUR["s3_hitl"] - 3.0))
    oneclick = frame.locator('button:has-text("演示一键勾选")')
    if oneclick.count() > 0:
        oneclick.first.click()
    hold("s3_hitl", 0.8)

    # S4 人工确认 → Team B 拼柜；完成标志 = 「看第 3 步」出现
    mark("s4_confirm")
    frame.locator('button:has-text("确认并拼柜 · resume")').click()
    frame.locator('button:has-text("看第 3 步")').wait_for(state="visible", timeout=120000)
    hold("s4_confirm", 0.6)

    # S5 可视化（3D / 多视图）
    mark("s5_visual")
    frame.locator('button.tab:has-text("可视化")').click()
    time.sleep(1.0)
    frame.locator("body").hover()
    hold("s5_visual", 0.8)

    # S6 总览裁决（走产品自己的「看第 3 步」）
    mark("s6_verdict")
    frame.locator('button:has-text("看第 3 步")').first.click()
    hold("s6_verdict", 2.0)

    total = now()
    video = page.video
    ctx.close()
    vpath = video.path()
    browser.close()

print(f"录制完成 total={total:.1f}s → {vpath}")
(SUB / "rec_schedule.json").write_text(
    json.dumps({"total": total, "marks": marks, "video": str(vpath)}, ensure_ascii=False, indent=1),
    encoding="utf-8",
)
assert total <= 117.0, f"超时 {total:.1f}s，需要精简"
