"""
统一 Run 产物落盘：output/runs/<run_id>/

体现 Agent「采取行动」：每次闭环生成可下载文件，而非仅聊天。
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from packing_assistant.config import TRACE_DIR

# 默认与 TRACE 同级：output/runs
RUNS_DIR = Path(TRACE_DIR).resolve().parent / "runs"


def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / str(run_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "views").mkdir(exist_ok=True)
    return d


def _write_json(path: Path, obj: Any) -> str:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def save_run_artifacts(
    state: Dict[str, Any],
    *,
    steps: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """
    将一次 pipeline 结果写入 output/runs/<run_id>/。
    返回相对/绝对路径字典，便于 API 返回。
    """
    rid = str(state.get("run_id") or state.get("session_id") or "run")
    d = run_dir(rid)
    paths: Dict[str, str] = {"run_dir": str(d), "run_id": rid}

    # 感知
    perception = state.get("perception") or state.get("materials_summary") or {}
    paths["perception"] = _write_json(d / "perception.json", perception)

    # 规划
    plan = state.get("plan") or {}
    booking = state.get("booking") or plan.get("booking") or {}
    planning = {
        "plan": plan,
        "booking": booking,
        "planning_reasons": plan.get("planning_reasons")
        or booking.get("planning_reasons")
        or [],
        "n0": plan.get("n0") or booking.get("n0"),
    }
    paths["plan"] = _write_json(d / "plan.json", planning)

    # 装载
    container_plan = state.get("container_plan") or {}
    paths["container_plan"] = _write_json(d / "container_plan.json", container_plan)

    # 评估 / 风险
    paths["evaluation"] = _write_json(d / "evaluation.json", state.get("evaluation") or {})
    risk = state.get("risk_report") or {}
    paths["risk"] = _write_json(d / "risk.json", risk)

    risk_md = _risk_md(state)
    (d / "risk.md").write_text(risk_md, encoding="utf-8")
    paths["risk_md"] = str(d / "risk.md")

    # 目标达成
    goal = {
        "goal": state.get("goal") or (state.get("orchestrator") or {}).get("goal"),
        "goal_status": state.get("goal_status") or {},
        "ship_ok": bool(
            container_plan.get("can_fit")
            and (risk.get("decision") not in ("REJECT",))
            and not risk.get("blockers")
        ),
    }
    # refine ship_ok from finalize logic if present
    if state.get("goal_status"):
        goal["goal_status"] = state["goal_status"]
    paths["goal"] = _write_json(d / "goal.json", goal)

    # finalize 文本
    final = state.get("final_response") or ""
    (d / "finalize.md").write_text(final if final else "# (no finalize)", encoding="utf-8")
    paths["finalize_md"] = str(d / "finalize.md")

    # boxes 摘要
    boxes = state.get("boxes") or []
    paths["boxes"] = _write_json(
        d / "boxes.json",
        {
            "count": len(boxes),
            "boxes": boxes[:200],
        },
    )

    # 图
    image = state.get("image_data") or {}
    views_dir = d / "views"
    copied = []
    for key in ("side", "top", "front"):
        p = (image.get(key) or {}).get("path")
        if p and Path(p).exists():
            dest = views_dir / Path(p).name
            try:
                shutil.copy2(p, dest)
                copied.append(str(dest))
            except Exception:
                pass
    for item in image.get("side_per_container") or []:
        p = item.get("path") if isinstance(item, dict) else None
        if p and Path(p).exists():
            try:
                dest = views_dir / Path(p).name
                shutil.copy2(p, dest)
                copied.append(str(dest))
            except Exception:
                pass
    ov = image.get("side_overview")
    if ov and Path(str(ov)).exists():
        try:
            dest = views_dir / Path(str(ov)).name
            shutil.copy2(ov, dest)
            copied.append(str(dest))
        except Exception:
            pass
    paths["views"] = _write_json(d / "views" / "index.json", {"files": copied})

    # agent steps / tool trajectory
    traj = steps or state.get("agent_steps") or []
    paths["trace"] = _write_json(d / "agent_trace.json", traj)
    # 流式 JSONL（若 pipeline 已写则保留；否则从 steps 合成一份）
    jsonl_path = d / "trace.jsonl"
    if not jsonl_path.exists() and traj:
        with jsonl_path.open("w", encoding="utf-8") as f:
            for i, st in enumerate(traj):
                f.write(
                    json.dumps(
                        {
                            "type": "agent_end",
                            "seq": i + 1,
                            "run_id": rid,
                            "node": st.get("node"),
                            "step": st,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
    if jsonl_path.exists():
        paths["trace_jsonl"] = str(jsonl_path)

    # 总览
    index = {
        "run_id": rid,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "n0": planning.get("n0"),
        "containers_used": container_plan.get("containers_used"),
        "can_fit": container_plan.get("can_fit"),
        "risk_decision": risk.get("decision"),
        "paths": paths,
        "agent_style": "multi_agent_workflow",
        "harness_version": (state.get("harness_meta") or {}).get("harness_version"),
        "note": "数值由 tools 计算；本目录为 Agent 闭环行动落盘结果",
    }
    paths["index"] = _write_json(d / "index.json", index)
    (d / "README.md").write_text(
        f"""# Run {rid}

- **目标**: `{goal.get('goal')}`
- **N0**: {planning.get('n0')} | **3D用柜**: {container_plan.get('containers_used')} | **can_fit**: {container_plan.get('can_fit')}
- **风险**: {risk.get('decision')} / {risk.get('level')}
- **出运**: {goal.get('ship_ok')}

## 文件

| 文件 | 含义 |
|------|------|
| perception.json | 感知：材料摘要 |
| plan.json | 规划：N0 与理由 |
| container_plan.json | 装载 layout |
| risk.md / risk.json | 风险 |
| finalize.md | 裁决文案 |
| agent_trace.json | 逐步 tool 轨迹 |
| trace.jsonl | 流式事件（可回放） |
| views/ | 三视图 |

感知→规划→工具→行动→目标：见 agent_trace.json / trace.jsonl 与 index.json。
""",
        encoding="utf-8",
    )
    paths["readme"] = str(d / "README.md")
    return paths


def _risk_md(state: Dict[str, Any]) -> str:
    risk = state.get("risk_report") or {}
    lines = [
        "# 风险合规",
        "",
        f"- **decision**: {risk.get('decision')}",
        f"- **level**: {risk.get('level')}",
        f"- **score**: {risk.get('compliance_score')}",
        f"- **passed**: {risk.get('passed')}",
        "",
        "## 阻断项",
        "",
    ]
    blockers = risk.get("blockers") or []
    if blockers:
        for b in blockers:
            lines.append(f"- {b}")
    else:
        lines.append("- （无）")
    lines.extend(["", "## 建议行动", ""])
    actions = risk.get("suggested_actions") or []
    if actions:
        for a in actions:
            lines.append(f"- {a}")
    else:
        lines.append("- （无额外建议）")
    lines.extend(["", "## 说明", "", risk.get("explanation") or "—", ""])
    risks = risk.get("risks") or state.get("risks") or []
    if risks:
        lines.extend(["## 风险列表", ""])
        for r in risks[:20]:
            lines.append(f"- {r}")
    return "\n".join(lines)
