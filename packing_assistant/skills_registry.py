"""Skills 契约注册：fail-loud，禁止静默缺失。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "docs" / "skills"

# skill_id → 模块入口约定
REQUIRED_SKILLS: Dict[str, Dict[str, str]] = {
    "material.parse": {
        "module": "packing_assistant.agents.material_parser",
        "doc": "material-parse.md",
        "rule": "不得编造尺寸重量",
    },
    "structure.calc": {
        "module": "packing_assistant.tools.structure_calc",
        "doc": "structure-calc.md",
        "rule": "半严格校核",
    },
    "bin3d.pack": {
        "module": "packing_assistant.tools.bin3d",
        "doc": "bin3d-pack.md",
        "rule": "LLM 禁止写 xyz",
    },
    "evaluate.plan": {
        "module": "packing_assistant.agents.evaluator",
        "doc": "evaluate-plan.md",
        "rule": "双利用率",
    },
    "risk.cog": {
        "module": "packing_assistant.tools.cog",
        "doc": "risk-cog.md",
        "rule": "CTU 60/50",
    },
    "hitl.confirm": {
        "module": "packing_assistant.hitl_gates",
        "doc": "hitl-confirm.md",
        "rule": "门禁确定性",
    },
    "replan.critic": {
        "module": "packing_assistant.agents.replan_critic",
        "doc": "replan-critic.md",
        "rule": "只改 packing_options",
    },
    "vgm.draft": {
        "module": "packing_assistant.tools.vgm_draft",
        "doc": "vgm-draft.md",
        "rule": "草稿须人签",
    },
}


def validate_skills(*, fail_loud: bool = True) -> Dict[str, Any]:
    """检查 skill 文档与模块可导入。"""
    import importlib

    missing_docs: List[str] = []
    missing_mods: List[str] = []
    ok: List[str] = []
    for sid, meta in REQUIRED_SKILLS.items():
        doc = SKILLS_DIR / meta["doc"]
        if not doc.exists():
            missing_docs.append(f"{sid}:{meta['doc']}")
        try:
            importlib.import_module(meta["module"])
            ok.append(sid)
        except Exception as e:
            missing_mods.append(f"{sid}:{meta['module']}:{e}")

    report = {
        "ok": ok,
        "missing_docs": missing_docs,
        "missing_modules": missing_mods,
        "pass": not missing_mods and not missing_docs,
    }
    if fail_loud and missing_mods:
        raise RuntimeError(f"skills missing modules: {missing_mods}")
    return report


def list_skills() -> List[Dict[str, str]]:
    return [
        {"id": k, **v, "doc_path": str(SKILLS_DIR / v["doc"])}
        for k, v in REQUIRED_SKILLS.items()
    ]
