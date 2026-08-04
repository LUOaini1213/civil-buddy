#!/usr/bin/env python3
"""比赛综合分卡（诚实校准版）。

- 六维跟踪 phase0 dimension_averages，禁止 gates 全绿就刷 10.0
- 仅 phase0_quick（n 小 / quick=true）时综合封顶，并标 partial
- 赢线：综合 ≥7.5 且 任务成功 ≥8.0 且硬门全过（与内部评分标准一致）
- 冲刺线 ≥9.5：要求 full baseline（非 quick 且 n≥20）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

OUT = ROOT / "output" / "competition"

# 赢线 / 冲刺线（0–10 分制）
WIN_OVERALL = 7.5
WIN_TASK = 8.0
STRETCH_OVERALL = 9.5
FULL_BASELINE_MIN_N = 20


def clamp(x: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, x))


def run_script(rel: str, args: List[str] | None = None, timeout: int = 600) -> Tuple[int, str]:
    cmd = [sys.executable, str(ROOT / rel)] + list(args or [])
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"},
    )
    return int(p.returncode), ((p.stdout or "") + (p.stderr or ""))


def _read_json(p: Path) -> Dict[str, Any]:
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_baseline(*, prefer_full: bool = True) -> Dict[str, Any]:
    """优先 full 归档（含 t30/t80），否则 latest / quick。"""
    phase0 = ROOT / "output" / "phase0"
    candidates = []
    if prefer_full:
        candidates.append(phase0 / "baseline_full_latest.json")
    candidates.extend(
        [
            phase0 / "baseline_latest.json",
            phase0 / "baseline_quick_latest.json",
        ]
    )
    best: Dict[str, Any] = {}
    best_rank = -1
    for p in candidates:
        bl = _read_json(p)
        if not bl:
            continue
        n = int(bl.get("n") or 0)
        quick = bool(bl.get("quick"))
        if "quick" not in bl and n and n <= 12:
            quick = True
        # 排序：full 大 n 优先
        rank = (0 if quick else 1000) + n
        if rank > best_rank:
            best_rank = rank
            best = bl
            best["_source_path"] = str(p)
    return best


def dim_means(bl: Dict[str, Any]) -> Dict[str, float]:
    d = (
        bl.get("dimension_averages")
        or bl.get("dim_means")
        or bl.get("dimension_means")
        or {}
    )
    return {str(k): float(v) for k, v in d.items()} if isinstance(d, dict) else {}


def baseline_meta(bl: Dict[str, Any]) -> Dict[str, Any]:
    n = int(bl.get("n") or 0)
    quick = bool(bl.get("quick"))
    # 兼容未写 quick 字段的旧产物：n≤12 视为 quick
    if "quick" not in bl and n and n <= 12:
        quick = True
    is_full = (not quick) and n >= FULL_BASELINE_MIN_N
    return {
        "n": n,
        "quick": quick,
        "is_full": is_full,
        "partial": not is_full,
        "pass_rate": float(bl.get("pass_rate") or 0),
        "avg_score": float(bl.get("avg_score") or 0),
        "source": bl.get("_source_path") or "",
    }


def _dim10(dm: Dict[str, float], key: str, default: float = 0.75) -> float:
    """phase0 0–1 维 → 0–10。缺省用 default（故意偏低，避免虚高）。"""
    v = dm.get(key)
    if v is None:
        return clamp(default * 10.0)
    return clamp(float(v) * 10.0)


def score_task(bl: Dict[str, Any], adv_ok: bool, meta: Dict[str, Any]) -> float:
    """任务成功：主锚 phase0.task_success，对抗仅小幅加分。"""
    dm = dim_means(bl)
    if bl and "task_success" in dm:
        s = _dim10(dm, "task_success")
    elif bl:
        # 无维均值时用 pass/avg 保守合成
        pr = meta["pass_rate"]
        avg = meta["avg_score"]
        s = clamp(3.5 + 3.0 * pr + 2.0 * min(1.0, avg))
    else:
        s = 7.0 if adv_ok else 6.0
    if adv_ok:
        s = clamp(s + 0.25)
    # full 大样本 + 高通过率：小幅加成（冲刺可信）
    if meta.get("is_full"):
        pr = meta.get("pass_rate") or 0
        if pr >= 0.90:
            s = clamp(s + 0.25)
        if pr >= 0.95:
            s = clamp(s + 0.2)
        if (meta.get("n") or 0) >= 25:
            s = clamp(s + 0.15)
    # quick 集不许冲到 9.5+
    if meta.get("partial"):
        s = min(s, 8.8)
    return clamp(s)


def score_long(hitl_ok: bool, bl: Dict[str, Any], meta: Dict[str, Any]) -> float:
    dm = dim_means(bl)
    s = _dim10(dm, "long_horizon", default=0.80)
    if hitl_ok:
        s = clamp(s + 0.25)  # 有 resume 门：小加成，不再 +1.5 刷满
    else:
        s = min(s, 7.5)
    if meta.get("partial"):
        s = min(s, 8.6)
    return clamp(s)


def score_tools(
    booking_ok: bool,
    mid50_ok: bool,
    bl: Dict[str, Any],
    meta: Dict[str, Any],
    *,
    llm_shadow_ok: bool = False,
) -> float:
    dm = dim_means(bl)
    s = _dim10(dm, "tool_quality", default=0.82)
    bonus = 0.0
    if booking_ok:
        bonus += 0.2
    if mid50_ok:
        bonus += 0.2
    if llm_shadow_ok:
        bonus += 0.25  # 影子 KPI 门禁通过
    s = clamp(s + bonus)
    if meta.get("partial"):
        s = min(s, 9.2)
    return clamp(s)


def score_multi(bl: Dict[str, Any], hitl_ok: bool, meta: Dict[str, Any]) -> float:
    dm = dim_means(bl)
    s = _dim10(dm, "multi_agent", default=0.82)
    if hitl_ok:
        s = clamp(s + 0.2)
    if meta.get("partial"):
        s = min(s, 9.0)
    return clamp(s)


def score_eff(bl: Dict[str, Any], phase0_wall: float, meta: Dict[str, Any]) -> float:
    dm = dim_means(bl)
    s = _dim10(dm, "efficiency", default=0.78)
    if phase0_wall and phase0_wall < 120:
        s = clamp(s + 0.25)
    elif phase0_wall and phase0_wall < 300:
        s = clamp(s + 0.1)
    try:
        ms = float(bl.get("ms_total") or 0)
        n = float(meta.get("n") or 1)
        per = ms / max(n, 1)
        if per <= 5000:
            s = clamp(s + 0.15)
        elif per <= 15000:
            s = clamp(s + 0.05)
    except Exception:
        pass
    if meta.get("partial"):
        s = min(s, 8.8)
    return clamp(s)


def score_explain(
    verdict_ok: bool, kb_ok: bool, bl: Dict[str, Any], meta: Dict[str, Any]
) -> float:
    dm = dim_means(bl)
    s = _dim10(dm, "explainability", default=0.80)
    if verdict_ok:
        s = clamp(s + 0.3)
    if kb_ok:
        s = clamp(s + 0.25)
    if meta.get("partial"):
        s = min(s, 9.0)
    return clamp(s)


def apply_overall_caps(overall: float, meta: Dict[str, Any], hard_ok: bool) -> float:
    """仅 quick/小 n 时硬封顶；无硬门则再压。"""
    o = overall
    if meta.get("partial"):
        o = min(o, 8.85)  # 禁止 quick 刷 9.5+
    if not hard_ok:
        o = min(o, 7.2)
    if not meta.get("is_full"):
        o = min(o, 9.2)  # full 以外永不 10
    return clamp(o)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Competition scorecard (calibrated)")
    ap.add_argument(
        "--full",
        action="store_true",
        help="跑 full phase0（含 t30/t80）再计分；亦可 SCORECARD_FULL=1",
    )
    ap.add_argument(
        "--use-archived-full",
        action="store_true",
        help="不重跑 full，仅使用 baseline_full_latest.json（若存在）",
    )
    ap.add_argument(
        "--skip-phase0",
        action="store_true",
        help="跳过 phase0 子进程，只读已有 baseline",
    )
    args = ap.parse_args()
    want_full = bool(args.full or os.environ.get("SCORECARD_FULL", "").strip() in ("1", "true", "yes"))
    # 已有 full 归档且未强制 --full → 默认跳过 phase0 重跑（省 ~11min）
    full_path = ROOT / "output" / "phase0" / "baseline_full_latest.json"
    full_cached = _read_json(full_path)
    has_full_archive = bool(
        full_cached
        and not bool(full_cached.get("quick"))
        and int(full_cached.get("n") or 0) >= FULL_BASELINE_MIN_N
    )
    if has_full_archive and not want_full and not args.skip_phase0:
        args.skip_phase0 = True
        print(
            f"INFO auto --skip-phase0: found full archive n={full_cached.get('n')} "
            f"(pass --full to re-run)"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    checks: Dict[str, Any] = {}

    def gate(
        name: str, rel: str, args_l: List[str] | None = None, timeout: int = 600
    ) -> bool:
        print(f">> {name}")
        try:
            rc, out = run_script(rel, args_l, timeout=timeout)
        except subprocess.TimeoutExpired:
            checks[name] = {"ok": False, "exit": -1, "err": "timeout"}
            print(f"FAIL {name} timeout")
            return False
        ok = rc == 0
        checks[name] = {"ok": ok, "exit": rc, "tail": out[-1500:]}
        print(f"{'PASS' if ok else 'FAIL'} {name} exit={rc}")
        return ok

    mid50_ok = gate("mid50", "scripts/test_mid50_cog.py", timeout=180)
    adv_ok = gate("adversarial", "scripts/test_adversarial_competition.py", timeout=600)
    hitl_ok = gate("hitl", "scripts/test_hitl_resume_competition.py", timeout=400)
    booking_ok = gate("booking", "scripts/test_booking_volume_metrics.py", timeout=180)
    kb_ok = gate("kb_search", "scripts/test_search_knowledge.py", timeout=120)
    gate("kb_bindings", "scripts/test_kb_bindings.py", timeout=60)
    llm_shadow_ok = gate(
        "llm_shadow_kpi", "scripts/test_llm_shadow_kpi.py", timeout=600
    )

    phase0_wall = 0.0
    phase0_ok = True
    phase0_full_ok = False
    if not args.skip_phase0:
        if want_full and not args.use_archived_full:
            t0 = time.time()
            # full 含 t30/t80，可能 30–90+ 分钟
            phase0_full_ok = gate(
                "phase0_full",
                "scripts/run_phase0_baseline.py",
                [],
                timeout=7200,
            )
            phase0_wall = time.time() - t0
            phase0_ok = phase0_full_ok
        else:
            t0 = time.time()
            phase0_ok = gate(
                "phase0_quick",
                "scripts/run_phase0_baseline.py",
                ["--quick"],
                timeout=900,
            )
            phase0_wall = time.time() - t0
            # 若已有 full 归档且要求冲刺：标记 full 可用
            full_bl = _read_json(ROOT / "output" / "phase0" / "baseline_full_latest.json")
            if full_bl and not bool(full_bl.get("quick")) and int(full_bl.get("n") or 0) >= FULL_BASELINE_MIN_N:
                phase0_full_ok = True
                checks["phase0_full_archived"] = {
                    "ok": True,
                    "n": full_bl.get("n"),
                    "pass_rate": full_bl.get("pass_rate"),
                }
                print(
                    f"INFO using archived full baseline n={full_bl.get('n')} "
                    f"pass_rate={full_bl.get('pass_rate')}"
                )
    else:
        checks["phase0_skipped"] = {"ok": True}
        full_bl = _read_json(ROOT / "output" / "phase0" / "baseline_full_latest.json")
        if full_bl and int(full_bl.get("n") or 0) >= FULL_BASELINE_MIN_N:
            phase0_full_ok = True

    verdict_ok = False
    try:
        from packing_assistant.demo_presets import materials_steel_light
        from packing_assistant.harness import public_response, run_agent_pipeline

        st = run_agent_pipeline(
            "scorecard",
            materials=materials_steel_light(),
            enable_auto_confirm=True,
            session_id="scorecard-verdict",
            save_artifacts=False,
        )
        pub = public_response(st)
        verdict_ok = bool((pub.get("verdict") or {}).get("level"))
    except Exception as e:
        checks["verdict_sample"] = {"ok": False, "err": str(e)}
    checks["verdict_sample"] = {"ok": verdict_ok}
    print(f"{'PASS' if verdict_ok else 'FAIL'} verdict_sample")

    bl = load_baseline(prefer_full=True)
    meta = baseline_meta(bl)
    dims = {
        "任务成功": score_task(bl, adv_ok, meta),
        "长程完成": score_long(hitl_ok, bl, meta),
        "工具质量": score_tools(
            booking_ok, mid50_ok, bl, meta, llm_shadow_ok=llm_shadow_ok
        ),
        "多Agent": score_multi(bl, hitl_ok, meta),
        "效率": score_eff(bl, phase0_wall, meta),
        "解释性": score_explain(verdict_ok, kb_ok, bl, meta),
    }
    raw_overall = sum(dims.values()) / max(len(dims), 1)

    hard = {
        "mid50": mid50_ok,
        "adversarial": adv_ok,
        "hitl": hitl_ok,
        "booking": booking_ok,
        "llm_shadow_kpi": llm_shadow_ok,
        "kb": kb_ok,
        "phase0": phase0_ok,
        "verdict": verdict_ok,
    }
    hard_ok = all(hard.values())
    overall = apply_overall_caps(raw_overall, meta, hard_ok)

    pr = meta["pass_rate"]
    avg = meta["avg_score"]
    task = float(dims["任务成功"])
    win_line = hard_ok and overall >= WIN_OVERALL and task >= WIN_TASK
    # 冲刺：full + 综合≥9.5 + 任务≥8.5（大样本下 task 维常 ~0.85）
    stretch = (
        hard_ok
        and meta.get("is_full")
        and overall >= STRETCH_OVERALL
        and task >= 8.5
        and llm_shadow_ok
    )

    from packing_assistant.config import HARNESS_VERSION

    honesty = []
    if meta.get("partial"):
        honesty.append(
            f"PARTIAL baseline: quick={meta.get('quick')} n={meta.get('n')} "
            f"(full needs non-quick n≥{FULL_BASELINE_MIN_N}); overall capped"
        )
    else:
        honesty.append(
            f"FULL baseline archived: n={meta.get('n')} pass_rate={pr:.3f} "
            f"source={meta.get('source') or 'baseline'}"
        )
    honesty.append(
        "Local auto score is calibrated against phase0 dims — not a free 10.0 for green gates."
    )
    honesty.append(
        "Known limits: TMS/ERP stub only; VGM/POR drafts need human signoff; "
        "llm_toolcall is shadow KPI gate (policy_fallback ok without API key)."
    )
    honesty.append(
        "CN–SG corridor: knowledge_base/07_domain_knowledge/cn_sg_corridor.md "
        "(summary, not legal text)."
    )

    lines = [
        "# Competition Scorecard (calibrated)",
        "",
        f"- harness: **{HARNESS_VERSION}** · agents: **13** (big Team ⊃ A/B roster)",
        f"- phase0 pass_rate: {pr:.3f} avg_score: {avg:.3f} n={meta.get('n')} "
        f"quick={meta.get('quick')} full={meta.get('is_full')} "
        f"src={meta.get('source') or '-'}",
        f"- phase0 wall_s: {phase0_wall:.1f} full_archived={phase0_full_ok}",
        f"- hard gates: {hard}",
        f"- raw_overall (pre-cap): {raw_overall:.2f} → overall: {overall:.2f}",
        "",
        "## Honesty",
        "",
    ]
    for h in honesty:
        lines.append(f"- {h}")
    lines += [
        "",
        "## Dimensions",
        "",
        "| 维度 | 分数 |",
        "|------|------|",
    ]
    for k, v in dims.items():
        flag = "OK" if v >= 9.0 else ("WIN" if v >= WIN_TASK or k != "任务成功" else "GAP")
        if k == "任务成功":
            flag = "OK" if v >= WIN_TASK else "GAP"
        lines.append(f"| {k} | {v:.2f} {flag} |")
    lines += [
        "",
        f"**综合**: {overall:.2f}",
        f"- **赢线** (≥{WIN_OVERALL} + 任务≥{WIN_TASK} + hard): "
        f"{'PASS' if win_line else 'FAIL'}",
        f"- **冲刺** (≥{STRETCH_OVERALL} + full n≥{FULL_BASELINE_MIN_N} + 任务≥8.5 + llm_shadow): "
        f"{'PASS' if stretch else 'FAIL (need full phase0 / higher dims)'}",
        "",
        "## Checks",
        "",
    ]
    for k, v in checks.items():
        ok = v.get("ok") if isinstance(v, dict) else v
        lines.append(f"- {k}: {'PASS' if ok else 'FAIL'} {v if isinstance(v, dict) else ''}")

    report = "\n".join(lines)
    (OUT / "SCORECARD.md").write_text(report, encoding="utf-8")
    payload = {
        "harness": HARNESS_VERSION,
        "agents_roster": 13,
        "dims": dims,
        "overall": overall,
        "raw_overall": raw_overall,
        "hard": hard,
        "hard_ok": hard_ok,
        "win_line": win_line,
        "stretch_pass": stretch,
        "llm_shadow_ok": llm_shadow_ok,
        "phase0_full_ok": phase0_full_ok,
        "baseline": {
            "pass_rate": pr,
            "avg": avg,
            "n": meta.get("n"),
            "quick": meta.get("quick"),
            "is_full": meta.get("is_full"),
            "partial": meta.get("partial"),
            "source": meta.get("source"),
            "dimension_averages": dim_means(bl),
        },
        "honesty": honesty,
        "thresholds": {
            "win_overall": WIN_OVERALL,
            "win_task": WIN_TASK,
            "stretch_overall": STRETCH_OVERALL,
            "full_min_n": FULL_BASELINE_MIN_N,
        },
    }
    (OUT / "scorecard_latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(report)
    # CI：赢线 + 硬门；冲刺另计
    if not win_line:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
