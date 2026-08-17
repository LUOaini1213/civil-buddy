"""Default-surface turn: understand first, write only on run/both.

Chat replies copy official titles already in-repo. No tender pipeline, no files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from packing_assistant.understand import understand

_REPO = Path(__file__).resolve().parents[1]
GST_LINE = "IRAS 页述：The current GST rate in Singapore is 9%（Current GST rates）。不是筹划意见，税额待持证办税人员按当期文件算。"
HAZARD_LINE = (
    "临边/洞口是否危大、要不要专家论证，须由持证人员按专项目录与现场条件判定。"
    "本产品只做内部讨论，不判定可以开工，不出法定专项方案。"
)
DRAFT_LINE = "内部讨论 AI 草稿。系统不判定可投标，不成稿则不写盘。"


def explain(text: str) -> str:
    t = text or ""
    bits = [DRAFT_LINE]
    if "GST" in t.upper() or "税率" in t or "发票" in t:
        bits.append(GST_LINE)
    if any(k in t for k in ("危大", "临边", "专家论证", "专项")):
        bits.append(HAZARD_LINE)
    if len(bits) == 1:
        bits.append("这是提问。未要求成稿，所以不进响应矩阵、不写投标应答或专项稿。要解析招标或写提纲请明说。")
    return "\n".join(bits)


def run_turn(
    text: str,
    *,
    p0_confirmed: bool = False,
    project_name: str = "幕墙项目投标应答（草稿）",
    force_intent: Optional[str] = None,
) -> Dict[str, Any]:
    intent = force_intent if force_intent in {"chat", "run", "both"} else understand(text)
    out: Dict[str, Any] = {
        "ok": True,
        "schema": "civil.turn.v1",
        "intent": intent,
        "wrote": False,
        "reply": "",
        "matrix": None,
        "submit_blocked": True,
        "submit_block_reason": "未成稿或仍是 AI 草稿，不可递交。",
    }
    if intent == "chat":
        out["reply"] = explain(text)
        return out

    from packing_assistant.tools.tender_parse import run_tender_pipeline

    pipe = run_tender_pipeline(
        text,
        source="default-turn",
        project_name=project_name,
        p0_confirmed=p0_confirmed,
    )
    reply = explain(text) if intent == "both" else "已按招标节选进矩阵。仍是 AI 草稿，submit_blocked=true，不可递交。"
    out.update(
        {
            "wrote": True,
            "reply": reply,
            "ok": bool(pipe.get("ok")),
            "matrix": pipe.get("matrix"),
            "handoff": pipe.get("handoff"),
            "review": pipe.get("review"),
            "submit_blocked": True,
            "submit_block_reason": pipe.get("submit_block_reason"),
            "tech_outline": pipe.get("tech_outline"),
            "bidbook_markdown": pipe.get("bidbook_markdown"),
            "export_markdown": pipe.get("export_markdown"),
            "extract_table_markdown": pipe.get("extract_table_markdown"),
            "matrix_csv": pipe.get("matrix_csv"),
            "p0_reject_scan": pipe.get("p0_reject_scan"),
            "run_id": pipe.get("run_id"),
            "product_mainline": "C_tender_delivery",
        }
    )
    return out
