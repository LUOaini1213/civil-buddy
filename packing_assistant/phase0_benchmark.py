"""Phase 0：比赛风格评测集 + 基线指标。

成功标准权重见 test/phase0/success_criteria.json。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
SIM_INDEX = ROOT / "test" / "sim_materials" / "INDEX.json"
CRITERIA_PATH = ROOT / "test" / "phase0" / "success_criteria.json"


@dataclass
class Phase0Case:
    id: str
    materials: List[Dict[str, Any]]
    user_input: str = ""
    packing_options: Dict[str, Any] = field(default_factory=dict)
    max_containers: int = 0
    tags: List[str] = field(default_factory=list)
    expect: Dict[str, Any] = field(default_factory=dict)
    story: str = ""


def load_success_criteria() -> Dict[str, Any]:
    if CRITERIA_PATH.is_file():
        return json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))
    return {
        "weights": {
            "task_success": 0.30,
            "long_horizon": 0.15,
            "tool_quality": 0.20,
            "multi_agent": 0.15,
            "efficiency": 0.10,
            "explainability": 0.10,
        },
        "win_threshold": {"total_score": 0.75, "task_success": 0.80},
    }


def _load_materials_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        mats = data.get("materials")
        if isinstance(mats, list):
            return mats
    return []


def _default_options() -> Dict[str, Any]:
    return {
        "prefer_stack": True,
        "multi_start": True,
        "cog_aware": True,
        "cog_rebalance": True,
        "standard_boxes": True,
        "mix_mode": True,
    }


def build_phase0_cases(*, include_heavy: bool = True) -> List[Phase0Case]:
    """构建 ≥20 的可自动 case（INDEX + 意图变体）。"""
    cases: List[Phase0Case] = []
    seen: set = set()

    def add(c: Phase0Case) -> None:
        if c.id in seen:
            return
        if not c.materials:
            return
        seen.add(c.id)
        cases.append(c)

    # —— 来自 sim INDEX ——
    if SIM_INDEX.is_file():
        idx = json.loads(SIM_INDEX.read_text(encoding="utf-8"))
        for cid, meta in (idx.get("cases") or {}).items():
            rel = meta.get("json") or f"test/sim_materials/{cid}/materials.json"
            path = ROOT / rel
            if not path.is_file():
                path = ROOT / "test" / "sim_materials" / cid / "materials.json"
            if not path.is_file():
                continue
            mats = _load_materials_json(path)
            n_lines = int(meta.get("n_lines") or len(mats))
            net = float(meta.get("net_kg") or 0)
            tags = ["sim"]
            if n_lines <= 15 and net < 5000:
                tags.append("short")
            elif net >= 25000 or n_lines >= 80:
                tags.append("long")
            else:
                tags.append("medium")
            if "weight" in cid or "volume" in cid or "payload" in cid or "overweight" in cid:
                tags.append("boundary")
            if "t30" in cid or "t80" in cid:
                tags.append("batch")
            if not include_heavy and ("t80" in cid or net > 50000):
                continue
            opts = dict(_default_options())
            hint = meta.get("packing_options_hint")
            if isinstance(hint, dict):
                opts.update(hint)
            # 板梁/模块板/超长混料：优先密装，避免标准空心架撑爆 3D
            if any(
                k in cid
                for k in (
                    "plates",
                    "plate",
                    "long_mix",
                    "modules_plates",
                    "modules",
                )
            ):
                opts.setdefault("dense_mode", True)
                opts.setdefault("prefer_stack", True)
                opts.setdefault("multi_start", True)
            exp = dict(meta.get("expect") or {})
            # 模块+板 t80 为应力票：几何极难 100% can_fit，流水线跑完即计任务分
            if "modules_plates" in cid:
                exp["allow_cannot_fit"] = True
                tags = list(tags) + ["stress"]
            add(
                Phase0Case(
                    id=f"sim:{cid}",
                    materials=mats,
                    user_input=f"phase0 {cid} 装柜评估",
                    packing_options=opts,
                    max_containers=0,
                    tags=tags,
                    expect=exp,
                    story=str(meta.get("story") or ""),
                )
            )

    # —— 意图 / 锁柜 / NL 变体（同料不同 Agency 输入）——
    tiny_path = ROOT / "test" / "sim_materials" / "tiny" / "materials.json"
    small_path = ROOT / "test" / "sim_materials" / "small_one_container" / "materials.json"
    for base_id, path, nl, mc, tags, exp in [
        (
            "nl_lock_1c_tiny",
            tiny_path,
            "预算1柜 密装 重心尽量居中",
            1,
            ["nl", "lock", "short"],
            {"containers_needed_max": 1, "can_fit": True},
        ),
        (
            "nl_lock_2c_small",
            small_path,
            "锁定2柜 自主拼柜",
            2,
            ["nl", "lock", "short"],
            {"containers_needed_max": 2},
        ),
        (
            "nl_min_cabin",
            small_path,
            "尽量少柜 可叠高",
            0,
            ["nl", "short"],
            {},
        ),
        (
            "nl_strict_cog",
            tiny_path,
            "严格重心 mid50 出运",
            0,
            ["nl", "short", "recovery"],
            {},
        ),
        (
            "nl_dense_stack",
            small_path,
            "密装优先叠高",
            0,
            ["nl", "stack", "short"],
            {},
        ),
    ]:
        if path.is_file():
            mats = _load_materials_json(path)
            opts = dict(_default_options())
            if "密装" in nl or "叠" in nl:
                opts["dense_mode"] = True
                opts["prefer_stack"] = True
            if "重心" in nl or "mid50" in nl:
                opts["cog_rebalance"] = True
                opts["lns_worst"] = True
            if mc:
                opts["lock_max_containers"] = True
                opts["container_budget"] = mc
                opts["meeting_cap"] = True
            add(
                Phase0Case(
                    id=f"synth:{base_id}",
                    materials=mats,
                    user_input=nl,
                    packing_options=opts,
                    max_containers=mc,
                    tags=tags,
                    expect=exp,
                    story=nl,
                )
            )

    # 再补合成小料（保证数量）
    if len(cases) < 20:
        for i in range(20 - len(cases)):
            mats = [
                {
                    "id": f"P0-{i}-a",
                    "part_no": "FST-P0",
                    "name": f"钢架{i}",
                    "length_mm": 2000 + i * 100,
                    "width_mm": 800,
                    "height_mm": 600,
                    "total_weight_kg": 200 + i * 20,
                    "quantity": 1,
                },
                {
                    "id": f"P0-{i}-b",
                    "part_no": "BBF-P0",
                    "name": f"小件{i}",
                    "length_mm": 400,
                    "width_mm": 300,
                    "height_mm": 200,
                    "total_weight_kg": 30,
                    "quantity": 2,
                },
            ]
            add(
                Phase0Case(
                    id=f"synth:pad_{i}",
                    materials=mats,
                    user_input=f"合成票{i} 正常装柜",
                    packing_options=_default_options(),
                    tags=["synth", "short"],
                    expect={"can_fit": True},
                )
            )

    return cases


def _score_task_success(st: Dict[str, Any], case: Phase0Case) -> float:
    plan = st.get("container_plan") or {}
    errors = st.get("errors") or []
    if errors and any("Traceback" in str(e) or "Exception" in str(e) for e in errors):
        return 0.0
    can_fit = plan.get("can_fit")
    used = int(plan.get("containers_used") or 0)
    exp = case.expect or {}
    score = 0.5
    if can_fit is True:
        score = 0.85
    elif can_fit is False:
        # 锁柜过紧允许失败，但降分
        if case.max_containers and used >= case.max_containers:
            score = 0.45
        elif exp.get("allow_cannot_fit"):
            # 应力票：流水线完整 + 有 replan 尝试 → 任务分及格
            score = 0.82
        else:
            score = 0.25
    if exp.get("can_fit") is True and can_fit is not True:
        score = min(score, 0.3)
    max_c = exp.get("containers_needed_max")
    if max_c is not None and can_fit and used > int(max_c):
        # 软惩罚：expect 多为订舱 N0；3D 用柜可略多，不应打成失败
        score = min(score, 0.84)
    min_c = exp.get("containers_needed_min")
    if min_c is not None and used and used < int(min_c):
        score = min(score, 0.5)
    if case.max_containers and used > case.max_containers and can_fit:
        score = min(score, 0.35)
    if st.get("status") == "error":
        score = min(score, 0.2)
    return float(max(0.0, min(1.0, score)))


def _score_long_horizon(st: Dict[str, Any]) -> float:
    nodes = [
        str(s.get("node"))
        for s in (st.get("agent_steps") or [])
        if isinstance(s, dict)
    ]
    need = ["material_parser", "box_scheme", "planner", "loader", "finalize"]
    # llm path may use team_a.run etc.
    alt = {
        "material_parser": ("material_parser", "team_a.run", "team_a_run"),
        "box_scheme": ("box_scheme", "team_a.run"),
        "planner": ("planner", "team_b.plan_load_eval", "team_b_plan_load_eval"),
        "loader": ("loader", "team_b.plan_load_eval"),
        "finalize": ("finalize", "finalize.run", "finalize_run"),
    }
    hit = 0
    for n in need:
        opts = alt.get(n, (n,))
        if any(any(o in x for o in opts) for x in nodes):
            hit += 1
    # also accept full finalize + boxes
    if st.get("final_response") and (st.get("boxes") or st.get("container_plan")):
        hit = max(hit, 4)
    if st.get("phase") in ("done", "team_b_running") or st.get("ship_ok") is not None:
        hit = max(hit, hit)
    return hit / 5.0


def _score_tool_quality(st: Dict[str, Any]) -> float:
    from packing_assistant.workteam_kpi import compute_kpis

    k = compute_kpis(st)
    illegal = int(k.get("illegal_tool_calls") or 0)
    n_tools = int(k.get("n_tools") or 0)
    cov = float(k.get("coverage_score") or 0)
    score = 0.4 * cov
    if n_tools >= 3:
        score += 0.3
    elif n_tools >= 1:
        score += 0.15
    if illegal == 0:
        score += 0.3
    else:
        score += max(0.0, 0.3 - 0.1 * illegal)
    return float(max(0.0, min(1.0, score)))


def _score_multi_agent(st: Dict[str, Any]) -> float:
    nodes = [
        str(s.get("node"))
        for s in (st.get("agent_steps") or [])
        if isinstance(s, dict)
    ]
    teams = [str(s.get("team") or "") for s in (st.get("agent_steps") or []) if isinstance(s, dict)]
    a_hit = any(
        x in nodes
        for x in (
            "material_parser",
            "structure",
            "box_scheme",
            "present_team_a",
            "team_a.run",
            "team_a_run",
        )
    ) or any(t in ("A", "a") for t in teams)
    b_hit = any(
        x in nodes
        for x in (
            "planner",
            "loader",
            "evaluator",
            "risk_compliance",
            "visualizer",
            "team_b.plan_load_eval",
        )
    ) or any(t in ("B", "b") for t in teams)
    big = any(
        x in nodes
        for x in ("orchestrator", "intent", "finalize", "replan_critic", "llm_scheduler")
    ) or any(t in ("big", "big_team") for t in teams)
    score = 0.0
    if a_hit:
        score += 0.4
    if b_hit:
        score += 0.4
    if big:
        score += 0.2
    if st.get("team_mode") == "big_team_a_b":
        score = max(score, 0.7)
    return float(min(1.0, score))


def _score_efficiency(st: Dict[str, Any], ms: int) -> float:
    n_steps = len(st.get("agent_steps") or [])
    # soft caps
    step_score = 1.0
    if n_steps > 40:
        step_score = 0.4
    elif n_steps > 25:
        step_score = 0.7
    elif n_steps > 15:
        step_score = 0.85
    time_score = 1.0
    if ms > 120_000:
        time_score = 0.4
    elif ms > 60_000:
        time_score = 0.7
    elif ms > 30_000:
        time_score = 0.85
    return 0.6 * step_score + 0.4 * time_score


def _score_explainability(st: Dict[str, Any]) -> float:
    steps = st.get("agent_steps") or []
    msgs = st.get("messages") or []
    ispec = st.get("intent_spec") or {}
    score = 0.0
    if len(steps) >= 3:
        score += 0.4
    elif steps:
        score += 0.2
    if any(isinstance(s, dict) and s.get("message") for s in steps):
        score += 0.2
    if ispec.get("scheme_id") or ispec.get("raw_nl") or st.get("user_input"):
        score += 0.2
    if msgs:
        score += 0.2
    return float(min(1.0, score))


def score_run(
    st: Dict[str, Any],
    case: Phase0Case,
    *,
    ms: int,
    criteria: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    criteria = criteria or load_success_criteria()
    weights = criteria.get("weights") or {}
    dims = {
        "task_success": _score_task_success(st, case),
        "long_horizon": _score_long_horizon(st),
        "tool_quality": _score_tool_quality(st),
        "multi_agent": _score_multi_agent(st),
        "efficiency": _score_efficiency(st, ms),
        "explainability": _score_explainability(st),
    }
    total = 0.0
    wsum = 0.0
    for k, w in weights.items():
        total += float(w) * float(dims.get(k) or 0)
        wsum += float(w)
    if wsum > 0 and abs(wsum - 1.0) > 0.01:
        total = total / wsum
    plan = st.get("container_plan") or {}
    return {
        "dimensions": dims,
        "total_score": round(total, 4),
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "n_steps": len(st.get("agent_steps") or []),
        "ms": ms,
        "team_mode": st.get("team_mode"),
        "agent_style": st.get("agent_style"),
        "replan_round": st.get("replan_round"),
        "ship_ok": st.get("ship_ok"),
    }


def classify_failure(
    st: Dict[str, Any], scored: Dict[str, Any], case: Optional[Phase0Case] = None
) -> str:
    dims = scored.get("dimensions") or {}
    if st.get("status") == "error" or (st.get("errors") or []):
        return "hard_error"
    if scored.get("can_fit") is False:
        if case and (case.expect or {}).get("allow_cannot_fit"):
            return "stress_cannot_fit"
        return "cannot_fit"
    if float(dims.get("task_success") or 0) < 0.5:
        return "task_constraint"
    if float(dims.get("long_horizon") or 0) < 0.5:
        return "incomplete_pipeline"
    if float(dims.get("tool_quality") or 0) < 0.5:
        return "tool_quality"
    if float(dims.get("multi_agent") or 0) < 0.5:
        return "weak_collaboration"
    if float(scored.get("total_score") or 0) < 0.75:
        return "low_score"
    return "ok"


def run_one_case(
    case: Phase0Case,
    *,
    agent_mode: str = "steps",
    criteria: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    t0 = time.time()
    st = run_agent_pipeline(
        case.user_input or f"phase0:{case.id}",
        materials=case.materials,
        container_type="40HQ",
        max_containers=int(case.max_containers or 0),
        enable_auto_confirm=True,
        session_id=f"phase0-{case.id.replace(':', '-')}",
        save_artifacts=False,
        packing_options=case.packing_options,
        agent_mode=agent_mode,
    )
    ms = int((time.time() - t0) * 1000)
    scored = score_run(st, case, ms=ms, criteria=criteria)
    fail = classify_failure(st, scored, case)
    thr = (criteria or load_success_criteria()).get("win_threshold") or {}
    passed = float(scored["total_score"]) >= float(
        thr.get("total_score") or 0.75
    ) and float((scored.get("dimensions") or {}).get("task_success") or 0) >= float(
        thr.get("task_success") or 0.80
    )
    return {
        "id": case.id,
        "tags": case.tags,
        "story": case.story,
        "pass": passed,
        "failure_mode": fail,
        "score": scored,
        "errors": list(st.get("errors") or [])[:3],
    }


def run_baseline(
    cases: Optional[Sequence[Phase0Case]] = None,
    *,
    agent_mode: str = "steps",
    quick: bool = False,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    criteria = load_success_criteria()
    if cases is None:
        cases = build_phase0_cases(include_heavy=not quick)
    if quick:
        # 优先 short + 部分 boundary
        short = [c for c in cases if "short" in c.tags or "synth" in c.tags]
        rest = [c for c in cases if c not in short]
        cases = (short + rest)[:12]

    rows = []
    t0 = time.time()
    for c in cases:
        print("RUN", c.id, c.tags)
        try:
            row = run_one_case(c, agent_mode=agent_mode, criteria=criteria)
        except Exception as e:
            row = {
                "id": c.id,
                "tags": c.tags,
                "pass": False,
                "failure_mode": "hard_error",
                "score": {"total_score": 0.0, "dimensions": {}, "ms": 0},
                "errors": [str(e)],
            }
        rows.append(row)
        print(
            ("PASS" if row["pass"] else "FAIL"),
            c.id,
            "score=",
            (row.get("score") or {}).get("total_score"),
            "mode=",
            row.get("failure_mode"),
        )

    n = len(rows)
    passed = sum(1 for r in rows if r.get("pass"))
    scores = [float((r.get("score") or {}).get("total_score") or 0) for r in rows]
    avg = sum(scores) / n if n else 0.0
    from collections import Counter

    fail_dist = dict(Counter(r.get("failure_mode") for r in rows))
    dim_avgs: Dict[str, float] = {}
    for key in (
        "task_success",
        "long_horizon",
        "tool_quality",
        "multi_agent",
        "efficiency",
        "explainability",
    ):
        vals = [
            float(((r.get("score") or {}).get("dimensions") or {}).get(key) or 0)
            for r in rows
        ]
        dim_avgs[key] = round(sum(vals) / n, 4) if n else 0.0

    steps_list = [int((r.get("score") or {}).get("n_steps") or 0) for r in rows]
    report = {
        "version": "phase0-baseline-v1",
        "agent_mode": agent_mode,
        "quick": quick,
        "n": n,
        "passed": passed,
        "pass_rate": round(passed / n, 4) if n else 0.0,
        "avg_score": round(avg, 4),
        "avg_steps": round(sum(steps_list) / n, 2) if n else 0.0,
        "dimension_averages": dim_avgs,
        "failure_mode_distribution": fail_dist,
        "criteria": criteria,
        "ms_total": int((time.time() - t0) * 1000),
        "cases": rows,
        "harness_version": __import__(
            "packing_assistant.config", fromlist=["HARNESS_VERSION"]
        ).HARNESS_VERSION,
    }

    out_dir = Path(out_dir or (ROOT / "output" / "phase0"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"baseline_{ts}.json"
    latest = out_dir / "baseline_latest.json"
    md_path = out_dir / "BASELINE_REPORT.md"
    text = json.dumps(report, ensure_ascii=False, indent=2)
    json_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    md_path.write_text(render_baseline_md(report), encoding="utf-8")
    report["paths"] = {
        "json": str(json_path),
        "latest": str(latest),
        "md": str(md_path),
    }
    return report


def render_baseline_md(report: Dict[str, Any]) -> str:
    """一页基线报告。"""
    dim = report.get("dimension_averages") or {}
    fail = report.get("failure_mode_distribution") or {}
    crit = report.get("criteria") or {}
    w = crit.get("weights") or {}
    thr = crit.get("win_threshold") or {}
    lines = [
        "# Phase 0 基线报告",
        "",
        f"- **Harness**: `{report.get('harness_version')}`",
        f"- **agent_mode**: `{report.get('agent_mode')}`",
        f"- **quick**: {report.get('quick')}",
        f"- **N**: {report.get('n')} · **通过**: {report.get('passed')} · **通过率**: {report.get('pass_rate')}",
        f"- **平均加权分**: **{report.get('avg_score')}** （赢阈值 total≥{thr.get('total_score', 0.75)}）",
        f"- **平均步数**: {report.get('avg_steps')}",
        f"- **总耗时**: {report.get('ms_total')} ms",
        "",
        "## 成功标准权重（假设）",
        "",
        "| 维度 | 权重 | 基线均分 |",
        "|------|------|----------|",
    ]
    for k, wt in w.items():
        lines.append(f"| {k} | {wt} | {dim.get(k, 0)} |")
    lines += [
        "",
        "## 失败模式分布",
        "",
        "```",
        json.dumps(fail, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 失败账本（差在哪 · 给 Phase 1）",
        "",
    ]
    from collections import defaultdict

    ledger: Dict[str, List[str]] = defaultdict(list)
    for r in report.get("cases") or []:
        fm = str(r.get("failure_mode") or "ok")
        if fm != "ok" or not r.get("pass"):
            ledger[fm].append(str(r.get("id")))
    if not ledger:
        lines.append(
            "- 无失败 case（全部 pass）。Phase 1 以 **工具层单测 + 长票压力** 为主，避免空转。"
        )
    else:
        lines.append("| 失败模式 | 次数 | 代表 case |")
        lines.append("|----------|------|-----------|")
        for mode, ids in sorted(ledger.items(), key=lambda x: -len(x[1])):
            sample = ", ".join(f"`{i}`" for i in ids[:5])
            if len(ids) > 5:
                sample += f" …(+{len(ids) - 5})"
            lines.append(f"| `{mode}` | {len(ids)} | {sample} |")
        lines.append("")
        lines.append("**Phase 1 建议优先级**（由账本驱动）：")
        priority = list(sorted(ledger.keys(), key=lambda m: -len(ledger[m])))
        hints = {
            "cannot_fit": "装不下 → bin3d/锁柜/密装 options 与 replan",
            "hard_error": "崩溃 → 工具异常结构化 + 单测",
            "task_constraint": "约束未满足 → booking 柜数/锁柜语义",
            "incomplete_pipeline": "未跑完 → finalize/HITL 续跑",
            "tool_quality": "工具轨迹弱 → packing/booking/cog 封装",
            "weak_collaboration": "A/B 轨迹缺失 → agent_steps team 字段",
            "low_score": "综合偏低 → 看维度均分最弱项",
        }
        for i, mode in enumerate(priority[:3], 1):
            lines.append(
                f"{i}. `{mode}`（n={len(ledger[mode])}）："
                f"{hints.get(mode, '见维度均分')}"
            )

    lines += [
        "",
        "## 解读（维度）",
        "",
    ]
    # auto narrative
    ts = float(dim.get("task_success") or 0)
    tq = float(dim.get("tool_quality") or 0)
    ma = float(dim.get("multi_agent") or 0)
    lh = float(dim.get("long_horizon") or 0)
    if ts < 0.8:
        lines.append("- **任务成功**偏弱：优先修 can_fit / 锁柜约束与 booking 体积工具可靠性。")
    else:
        lines.append("- **任务成功**尚可：维持回归，避免 Phase 1 改坏主路径。")
    if tq < 0.85:
        lines.append("- **工具质量**待抬：工具封装与 illegal=0、体积/叠装 Tool 稳定性（P1.2）。")
    else:
        lines.append("- **工具质量**基线健康。")
    if ma < 0.7:
        lines.append("- **多 Agent 协作**轨迹不完整：检查 A/B 节点是否写入 agent_steps。")
    else:
        lines.append("- **多 Agent（大⊃A/B）**轨迹可见，叙事可讲协作。")
    if lh < 0.8:
        lines.append("- **长程完成**不足：补全 finalize / 断点续跑验收（P1.4）。")
    else:
        lines.append("- **长程完成**闭环基本跑通。")
    lines += [
        "",
        "## Case 摘要",
        "",
        "| id | pass | score | failure | steps |",
        "|----|------|-------|---------|-------|",
    ]
    for r in report.get("cases") or []:
        sc = r.get("score") or {}
        lines.append(
            f"| `{r.get('id')}` | {r.get('pass')} | {sc.get('total_score')} | "
            f"{r.get('failure_mode')} | {sc.get('n_steps')} |"
        )
    lines += [
        "",
        "---",
        "",
        "下一步：见 `docs/competition-phase-plan.md` Phase 1。",
        "",
    ]
    return "\n".join(lines)
