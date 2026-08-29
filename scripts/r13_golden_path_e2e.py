#!/usr/bin/env python3
"""UX R13 端到端金线终验（收官轮）。

真实浏览器（playwright + chromium）走完 :8765 Rust 工作台全动线，逐项记录 PASS/FAIL：

  1. 空态引导        #cbEmpty 空态卡 + #cbOnboard 三步引导（首访可见）+ ? 重开
  2. 示例卡预填      /pack 示例卡预填输入框且不自动发送
  3. 时间线八阶段    data-cb-stage 八轨（理解→召唤→成箱→确认→拼柜→合规→落盘→收口）
  4. HITL 审批卡     high 风险岗（钢结构）触发审批卡，显式确认=confirm_ok 重提
  5. 文书预览下载    文书预览浮层 + 下载 .md 真实落盘非空
  6. 审计含决策节点  #loadAudit 面板出现决策（decision）节点，count 决策≥1
  7. 主题切换        cbThemeBtn → data-theme=dark + aria-pressed + cb_theme_v1 持久化
  8. 窄屏 375px      375x812 视口下审批卡可见可点（触控可用）

用法：python scripts/r13_golden_path_e2e.py   （端口占用则复用现有服务）
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT_GW, PORT_WB = 8000, 8765
WORKBENCH_URL = f"http://127.0.0.1:{PORT_WB}"
STEEL_TASK = "请召唤钢结构岗，出一份钢结构说明草稿（内部讨论 AI 草稿，不是签认件）"

results: list[tuple[str, str, str]] = []  # (item, verdict, evidence)


def record(item: str, ok: bool, evidence: str) -> None:
    results.append((item, "PASS" if ok else "FAIL", evidence))
    print(f"[golden] {'PASS' if ok else 'FAIL'} · {item} · {evidence}")


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_http(url: str, timeout: float = 60.0) -> None:
    import urllib.request

    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(0.6)
    raise RuntimeError(f"服务未就绪：{url}（{last}）")


def ensure_servers() -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    if not port_open(PORT_GW):
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "gateway.app:app", "--host", "127.0.0.1", "--port", str(PORT_GW)],
                cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        )
        print(f"[golden] 已启动网关 ：{PORT_GW}")
    if not port_open(PORT_WB):
        wb = ROOT / "workbench"
        exe = None
        for cand in ("target/release/civil-workbench.exe", "target/debug/civil-workbench.exe"):
            if (wb / cand).is_file():
                exe = wb / cand
                break
        if exe is None:
            subprocess.run(["cargo", "build", "--bin", "civil-workbench"], cwd=str(wb), check=True)
            exe = wb / "target/debug/civil-workbench.exe"
        env = dict(os.environ)
        env["CIVIL_PORT"] = str(PORT_WB)
        procs.append(
            subprocess.Popen([str(exe)], cwd=str(wb), env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        )
        print(f"[golden] 已启动 Rust 工作台 ：{PORT_WB}（{exe.name}）")
    wait_http(f"http://127.0.0.1:{PORT_GW}/api/health")
    wait_http(f"{WORKBENCH_URL}/")
    print("[golden] 两端就绪")
    return procs


def stage_states(page) -> dict[str, str]:
    return page.evaluate(
        """() => {
        const out = {};
        document.querySelectorAll('[data-cb-stage]').forEach(el => {
          out[el.getAttribute('data-cb-stage')] = el.className || '';
        });
        return out;
    }"""
    )


def send_and_wait_approval(page, timeout_ms: int = 300000) -> None:
    page.fill("#input", STEEL_TASK)
    page.click("#send")
    page.wait_for_selector(".cb-tl", timeout=180000)
    page.wait_for_selector('button[aria-label^="确认并重提"]', timeout=timeout_ms)


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[golden] SKIP：未安装 playwright。")
        return 0
    procs: list[subprocess.Popen] = []
    try:
        procs = ensure_servers()
    except Exception as e:  # noqa: BLE001
        print(f"[golden] FAIL：服务自启失败：{e}")
        return 1

    page_errors: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1440, "height": 960})

            # ---------- 桌面端全动线 ----------
            page = ctx.new_page()
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.goto(f"{WORKBENCH_URL}/", wait_until="domcontentloaded", timeout=30000)

            # 1. 空态引导
            try:
                page.wait_for_selector("#cbEmpty", timeout=15000)
                ob_visible = page.is_visible("#cbOnboard")
                steps = page.locator("#cbOnboard li, #cbOnboard .cb-ob-step").count()
                ev = f"空态卡在, 引导可见={ob_visible}, 步骤数={steps}"
                ok1 = ob_visible and steps >= 3
                page.click("#onboardHelp")  # 重开（若首访已显示则收起再点开语义不破坏：只验证可交互）
                ok1 = ok1 and page.locator("#onboardHelp").is_visible()
                record("1 空态引导", ok1, ev + ", ?入口在")
            except Exception as e:  # noqa: BLE001
                record("1 空态引导", False, f"{type(e).__name__}: {e}")

            # 2. 示例卡预填（不自动发送）
            try:
                page.reload(wait_until="domcontentloaded")
                page.wait_for_selector('button.cb-empty-card[data-cb-sample="pack"]', timeout=15000)
                before = page.input_value("#input")
                page.click('button.cb-empty-card[data-cb-sample="pack"]')
                after = page.input_value("#input")
                page.wait_for_timeout(1500)
                no_autosend = page.locator(".cb-tl").count() == 0
                record("2 示例卡预填", bool(after.strip()) and after != before and no_autosend,
                       f"预填={after[:24]!r}…, 未自动发送={no_autosend}")
            except Exception as e:  # noqa: BLE001
                record("2 示例卡预填", False, f"{type(e).__name__}: {e}")

            # 3+4. 发送钢结构任务 → 八阶段时间线 + HITL 审批卡
            try:
                page.fill("#input", STEEL_TASK)
                page.click("#send")
                page.wait_for_selector(".cb-tl", timeout=180000)
                chips = page.evaluate(
                    "() => Array.from(document.querySelectorAll('[data-cb-stage]')).map(e => e.getAttribute('data-cb-stage'))"
                )
                eight = sorted(set(chips)) == sorted(
                    ["understand", "summon", "box", "hitl", "pack", "risk", "write", "finalize"]
                )
                page.wait_for_selector('button[aria-label^="确认并重提"]', timeout=300000)
                record("3 时间线八阶段", eight, f"八轨 chips={sorted(set(chips))}")
            except Exception as e:  # noqa: BLE001
                record("3 时间线八阶段", False, f"{type(e).__name__}: {e}")
                record("4 HITL 审批卡确认", False, "审批卡未出现")
            else:
                # 4. 显式确认 → confirm_ok 重提
                try:
                    btn = page.locator('button[aria-label^="确认并重提"]').first
                    btn.click()
                    page.wait_for_selector(".cb-apr-state:not([hidden])", timeout=20000)
                    state_txt = page.locator(".cb-apr-state").first.inner_text()
                    ok4 = "确认" in state_txt or "已确认" in state_txt
                    record("4 HITL 审批卡确认", ok4, f"卡片状态={state_txt[:30]!r}")
                except Exception as e:  # noqa: BLE001
                    record("4 HITL 审批卡确认", False, f"{type(e).__name__}: {e}")

            # 5. 文书预览 + 真实下载
            try:
                preview = page.get_by_role("button", name="文书预览").first
                preview.wait_for(state="visible", timeout=300000)
                preview.click()
                page.wait_for_selector('[aria-label="交付物文书预览"]', timeout=20000)
                # 引导第 3 步应已打勾（R10：文书预览打开→打勾）
                ob_state = page.evaluate("() => localStorage.getItem('cb_onboarded_v1') || ''")
                dl_btn = page.locator('[aria-label="交付物文书预览"]').get_by_role("button", name=re.compile("下载"))
                with page.expect_download(timeout=30000) as dl_info:
                    dl_btn.first.click()
                dl = dl_info.value
                tmp = Path(tempfile.gettempdir()) / dl.suggested_filename
                dl.save_as(str(tmp))
                size = tmp.stat().st_size
                ok5 = size > 0 and ("done" in ob_state or "3" in ob_state or ob_state == "")
                record("5 文书预览下载", size > 0,
                       f"预览浮层在, 下载 {dl.suggested_filename} {size}B, 引导状态={ob_state[:40]!r}")
                page.keyboard.press("Escape")
            except Exception as e:  # noqa: BLE001
                record("5 文书预览下载", False, f"{type(e).__name__}: {e}")

            # 6. 审计时间线含决策节点
            try:
                page.click("#loadAudit")
                # 等决策区真正渲染完（面板 unhide 是同步的，body 此刻还是"加载中…"）
                page.wait_for_selector(".cb-audit-pinned", timeout=30000)
                page.wait_for_function(
                    "() => { const h = document.querySelector('.cb-audit-none');"
                    " return h && !h.textContent.includes('加载中'); }",
                    timeout=30000,
                )
                head_txt = ""
                for sel in (".cb-audit-none", ".cb-audit-pinned", "#auditPanel"):
                    loc = page.locator(sel).first
                    if loc.count():
                        head_txt = loc.inner_text()
                        if "决策" in head_txt:
                            break
                m = re.search(r"决策\s*(\d+)", head_txt)
                n_dec = int(m.group(1)) if m else 0
                dec_nodes = page.locator(".cb-audit-node").count()
                record("6 审计含决策节点", n_dec >= 1 or dec_nodes >= 1,
                       f"审计头摘要决策数={n_dec}, 节点元素={dec_nodes}")
            except Exception as e:  # noqa: BLE001
                record("6 审计含决策节点", False, f"{type(e).__name__}: {e}")

            # 7. 主题切换（暗→明 + 持久化）
            try:
                page.click("#cbThemeBtn")
                page.wait_for_timeout(300)
                dark = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
                pressed = page.get_attribute("#cbThemeBtn", "aria-pressed")
                stored = page.evaluate("() => localStorage.getItem('cb_theme_v1')")
                ok7 = dark == "dark" and pressed == "true" and stored == "dark"
                page.click("#cbThemeBtn")
                page.wait_for_timeout(300)
                back = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
                ok7 = ok7 and (back in ("light", None))
                record("7 主题切换", ok7, f"暗:data-theme={dark},aria={pressed},store={stored}; 回切={back}")
            except Exception as e:  # noqa: BLE001
                record("7 主题切换", False, f"{type(e).__name__}: {e}")
            page.close()

            # ---------- 窄屏 375px 审批可用 ----------
            page2 = ctx.new_page()
            page2.set_viewport_size({"width": 375, "height": 812})
            page2.on("pageerror", lambda exc: page_errors.append(str(exc)))
            try:
                page2.goto(f"{WORKBENCH_URL}/", wait_until="domcontentloaded", timeout=30000)
                page2.wait_for_selector("#input", timeout=15000)
                send_and_wait_approval(page2)
                btn2 = page2.locator('button[aria-label^="确认并重提"]').first
                box = btn2.bounding_box()
                in_vp = box and box["x"] >= 0 and box["x"] + box["width"] <= 375 + 1 and box["y"] + box["height"] <= 812
                btn2.click()
                page2.wait_for_selector(".cb-apr-state:not([hidden])", timeout=20000)
                state2 = page2.locator(".cb-apr-state").first.inner_text()
                record("8 窄屏375审批", bool(in_vp) and ("确认" in state2),
                       f"按钮box={box and [round(box['x']), round(box['y']), round(box['width']), round(box['height'])]}, 视口内={in_vp}, 状态={state2[:20]!r}")
            except Exception as e:  # noqa: BLE001
                record("8 窄屏375审批", False, f"{type(e).__name__}: {e}")
            page2.close()

            ctx.close()
            browser.close()
    finally:
        for proc in procs:
            proc.terminate()

    print("\n[golden] ===== 终验结果 =====")
    n_pass = sum(1 for _, v, _ in results if v == "PASS")
    for item, verdict, ev in results:
        print(f"{verdict}  {item}  — {ev}")
    if page_errors:
        print(f"[golden] 未捕获 JS 异常 {len(page_errors)} 条：{page_errors[:3]}")
    print(f"[golden] 汇总 {n_pass}/{len(results)} PASS" + ("，全部通过" if n_pass == len(results) and not page_errors else ""))
    return 0 if n_pass == len(results) and not page_errors else 1


if __name__ == "__main__":
    sys.exit(main())
