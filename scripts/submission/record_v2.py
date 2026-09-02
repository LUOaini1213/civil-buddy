"""强化版真机录屏（1920x1080，可见鼠标，九场景讲全功能）。

场景表（口播时长驱动，动作超时顺延）：
  s1 首屏+项目树 → s2 设置里填 Key（供应商切换）→ s3 输入「装箱」嵌入装柜台
  → s4 满载成箱 → s5 确认闸+预检 → s6 确认并拼柜 → s7 可视化(滚动)
  → s8 总览裁决 → s9 还原后：@召唤 / 斜杠指令 / 示例卡只预填不发送
"""
import json
import time
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(r"C:\Users\LW\civil-buddy")
SUB = ROOT / "output/submission"
TTS = SUB / "tts_v2"
VID_DIR = SUB / "rec_v2"
VID_DIR.mkdir(exist_ok=True)
for old in VID_DIR.glob("*.webm"):
    old.unlink()

def wav_dur(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()

SCENES = ["s1_home", "s2_llm", "s3_nl", "s4_teama", "s5_hitl",
          "s6_confirm", "s7_visual", "s8_verdict", "s9_more"]
DUR = {s: wav_dur(TTS / f"{s}.wav") for s in SCENES}

CURSOR_JS = """
(() => {
  const mk = () => {
    if (document.getElementById('cb-fake-cursor')) return;
    const st = document.createElement('style');
    st.textContent = '#cb-fake-cursor{position:fixed;z-index:2147483647;width:26px;height:26px;'
      + 'border-radius:50%;background:rgba(255,196,0,.85);border:3px solid rgba(20,20,20,.7);'
      + 'pointer-events:none;transform:translate(-50%,-50%);box-shadow:0 0 14px rgba(255,196,0,.55);'
      + 'transition:left .06s linear, top .06s linear}';
    document.head.appendChild(st);
    const c = document.createElement('div');
    c.id = 'cb-fake-cursor';
    c.style.left = '-60px'; c.style.top = '-60px';
    document.body.appendChild(c);
    window.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, {capture:true});
    window.addEventListener('mousedown', () => {
      c.style.background = 'rgba(255,90,90,.95)';
      setTimeout(() => { c.style.background = 'rgba(255,196,0,.85)'; }, 200);
    }, {capture:true});
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk);
  else mk();
})();
"""

marks: list[tuple[str, float]] = []
t0 = 0.0

def now() -> float:
    return time.time() - t0

def mark(seg: str) -> None:
    marks.append((seg, now()))
    print(f"  [{now():6.1f}s] {seg}")

def hold(seg: str, pad: float = 0.5) -> None:
    start = dict(marks)[seg]
    end = start + DUR[seg] + pad
    while now() < end:
        time.sleep(0.1)

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(VID_DIR),
        record_video_size={"width": 1920, "height": 1080},
        device_scale_factor=1,
    )
    ctx.add_init_script(CURSOR_JS)
    page = ctx.new_page()
    t0 = time.time()

    # s1 首屏 + 左栏项目树（鼠标沿左栏划过）
    page.goto("http://127.0.0.1:8765/")
    page.wait_for_selector("#cbEmpty", state="visible", timeout=20000)
    mark("s1_home")
    page.mouse.move(140, 200)
    time.sleep(1.2)
    page.mouse.move(140, 420)
    hold("s1_home")

    # s2 模型设置：设置 → 模型设置 → 切换供应商（DeepSeek→z.ai→回）→ 关闭
    mark("s2_llm")
    page.click("#cbMoreBtn")
    time.sleep(0.7)
    page.click("#cbLlmOpen")
    page.wait_for_selector("#cbLlm:not(.hidden)", timeout=8000)
    time.sleep(1.6)
    page.select_option("#cbLlmVendor", "zai")
    time.sleep(1.8)
    page.select_option("#cbLlmVendor", "deepseek")
    time.sleep(1.4)
    page.click("#cbLlmClose")
    hold("s2_llm")

    # s3 自然语言「装箱」→ 内嵌装柜台 → 放大
    mark("s3_nl")
    page.click("#input")
    page.locator("#input").press_sequentially("装箱", delay=420)
    time.sleep(0.7)
    page.press("#input", "Enter")
    page.wait_for_selector("#cbPackEmbed iframe", state="attached", timeout=20000)
    time.sleep(2.0)
    page.click('#cbPackEmbed button:has-text("放大")')
    hold("s3_nl")

    frame = page.frame_locator("#cbPackEmbed iframe")

    # s4 满载成箱（Team A）
    mark("s4_teama")
    frame.locator('button.primary-lg:has-text("开始第 1 步")').click()
    frame.locator('button:has-text("去第 2 步")').wait_for(state="visible", timeout=90000)
    hold("s4_teama")

    # s5 确认闸 + 一键勾选预检
    mark("s5_hitl")
    frame.locator('button:has-text("去第 2 步")').click()
    time.sleep(min(5.0, DUR["s5_hitl"] - 3.0))
    oneclick = frame.locator('button:has-text("演示一键勾选")')
    if oneclick.count() > 0:
        oneclick.first.click()
    hold("s5_hitl")

    # s6 人工确认 → Team B
    mark("s6_confirm")
    frame.locator('button:has-text("确认并拼柜 · resume")').click()
    frame.locator('button:has-text("看第 3 步")').wait_for(state="visible", timeout=120000)
    hold("s6_confirm")

    # s7 可视化 + 缓慢滚动看三视角
    mark("s7_visual")
    frame.locator('button.tab:has-text("可视化")').click()
    time.sleep(1.2)
    for _ in range(4):
        page.mouse.wheel(0, 260)
        time.sleep(0.7)
    hold("s7_visual", 0.8)

    # s8 总览裁决
    mark("s8_verdict")
    frame.locator('button:has-text("看第 3 步")').first.click()
    time.sleep(1.5)
    for _ in range(3):
        page.mouse.wheel(0, 240)
        time.sleep(0.8)
    hold("s8_verdict", 0.8)

    # s9 还原 → @召唤 → /指令 → 示例卡只预填
    mark("s9_more")
    page.click('#cbPackEmbed button:has-text("还原")')
    time.sleep(0.8)
    page.click("#input")
    page.locator("#input").press_sequentially("@", delay=200)
    try:
        page.wait_for_selector("#atMenu:not([hidden])", timeout=4000)
    except Exception:
        pass
    time.sleep(2.2)
    page.press("#input", "Escape")
    page.fill("#input", "")
    page.locator("#input").press_sequentially("/", delay=200)
    try:
        page.wait_for_selector("#cmdMenu:not([hidden])", timeout=4000)
    except Exception:
        pass
    time.sleep(2.2)
    page.press("#input", "Escape")
    page.fill("#input", "")
    # 「/」菜单点 /bid → 模板**预填**进输入框、不发送（红线的画面证据）。
    # 发送「装箱」后欢迎区已隐藏，示例卡不可用——实测确认，故用命令菜单演同一条红线。
    page.locator("#input").press_sequentially("/", delay=200)
    try:
        page.wait_for_selector("#cmdMenu:not([hidden])", timeout=4000)
        item = page.locator('#cmdMenu button:has-text("/bid")')
        if item.count() > 0:
            item.first.click()
            time.sleep(1.0)
            # 若只是下钻到二级（输入框仍是"/"），再点一项完成预填
            if page.input_value("#input").strip() == "/":
                sub = page.locator("#cmdMenu button")
                if sub.count() > 0:
                    sub.first.click()
    except Exception:
        pass
    hold("s9_more", 0.8)

    total = now()
    video = page.video
    ctx.close()
    vpath = video.path()
    browser.close()

print(f"录制完成 total={total:.1f}s → {vpath}")
(SUB / "rec_v2_schedule.json").write_text(
    json.dumps({"total": total, "marks": marks, "video": str(vpath)}, ensure_ascii=False, indent=1),
    encoding="utf-8",
)
# 片头 8.4 + 片尾 >=12.4，demo 必须 <= 98 左右才能守住 119
assert total <= 98.5, f"demo 段 {total:.1f}s，加片头片尾会破 2 分钟"
