"""Per-post horizon plans vs 易标 or pack-agent. Planning only — no gap implementation."""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.expert_roster import list_experts

YIBIAO_STEPS = ("parse", "outline", "qa", "kb", "write")
PACK_POSTS = frozenset({"pack-ship"})
FORBIDDEN_GOALS = ("可以投标", "可以开工", "中标率")


def lane_id(category: str) -> str:
    return f"lane-{category}"


def _step_status(exp, step: str) -> str:
    tags = set()
    # yibiao tags live on yibiao-map; roster exclusive + category imply kb/write
    if step == "kb":
        return "已有 · 分层 KB + search_kb/read_kb（demo/kb）"
    if step == "write":
        tools = ", ".join(exp.exclusive) or "write_deliverable"
        return f"已有 · 独有 {tools}；chat 不写盘"
    if step == "qa":
        return f"已有 · {exp.category}__scan_forbidden" + (
            " + 高风险确认句" if exp.risk == "high" else ""
        )
    if step == "parse":
        if exp.id == "bid-parse":
            return "已有 · bid-parse__extract / run_tender_pipeline（exact_text）"
        if any(x in " ".join(exp.exclusive) for x in ("extract", "takeoff", "parse", "record", "recon")):
            return f"部分 · 独有 {', '.join(exp.exclusive)} 可抄用户原文，无扫描 PDF"
        return "缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝"
    if step == "outline":
        if any(x in " ".join(exp.exclusive) for x in ("outline", "expand", "draft", "brief", "memo", "plan", "network", "week")):
            return f"已有 · {', '.join(exp.exclusive)} 提纲/说明"
        return "部分 · run 出内部提纲骨架，未对照易标目录扩写器"
    return "UNSPECIFIED"


def _pack_steps(exp) -> Dict[str, str]:
    if exp.id == "pack-ship":
        return {
            "list": "已有 · pack-ship__list",
            "plan": "已有 · pack-ship__plan 投影 solver",
            "export": "已有 · pack-ship__export",
            "can_fit": "已有 · 只抄 solver；断线字面 UNSPECIFIED",
            "mid50": "已有 · 只抄 solver；断线 UNSPECIFIED",
            "utilization": "已有 · 只抄 solver；断线 UNSPECIFIED",
            "xyz": "禁止编造 · 未接通不写坐标",
        }
    return {
        "list": "缺口 · 非装柜岗不暴露 pack-ship 工具表",
        "plan": "不适用",
        "export": "不适用",
        "can_fit": "不适用 · 不得手写 can_fit",
        "mid50": "不适用",
        "utilization": "不适用",
        "xyz": "禁止编造",
    }


def _next_knife(exp) -> str:
    if exp.id == "bid-parse":
        return "经营岗 turn 与 bid-parse 共用同一 extract 表；可选接通本机 MinerU，失败仍拒绝，不默认 OCR。"
    if exp.id == "bid-compliance":
        return "把 tender.review.v1 禁语/缺项接到本岗 exclusive gaps，仍不判定废标。"
    if exp.id == "bid-tech":
        return "技术标目录只按抽出评分点扩章，无评分点则待对照，不套上个项目。"
    if exp.id == "construction":
        return "scheme_draft 继续 11 章讨论提纲；确认句之后才写盘，不当法定专项。"
    if exp.id == "method-hazard":
        return "判定书只打三态+依据标题；不写可以开工。"
    if exp.id == "pack-ship":
        return "默认召唤本岗时把最近一次 packing_summary 当 solver 快照抄进 plan/export，仍禁止重算 xyz。"
    if exp.category == "finance":
        return "税务/资金日历只抄 IRAS 页述标题与 9%；税额 UNSPECIFIED。"
    if exp.category == "bim":
        return "碰撞/算量/LOD 只出表头与口径，不接 IFC 真抽量（另开一轮）。"
    return f"在 chat/run 上把 {exp.exclusive[0] if exp.exclusive else 'write'} 的用户栏位写全，缺数 [A001]/UNSPECIFIED。"


def build_post_plans() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for exp in list_experts():
        bench = "pack-agent" if exp.id in PACK_POSTS else "yibiao"
        rec: Dict[str, Any] = {
            "id": exp.id,
            "name": exp.name,
            "category": exp.category,
            "lane": lane_id(exp.category),
            "benchmark": bench,
            "risk": exp.risk,
            "exclusive": list(exp.exclusive),
            "next_knife": _next_knife(exp),
        }
        if bench == "yibiao":
            rec["steps"] = {s: _step_status(exp, s) for s in YIBIAO_STEPS}
        else:
            rec["steps"] = _pack_steps(exp)
        rows.append(rec)
    return rows


def coverage_pairs() -> List[tuple[str, str]]:
    return [(p["id"], p["lane"]) for p in build_post_plans()]


def horizon_order() -> List[str]:
    return [
        "1. 保持 66 岗同一套 chat/run，不回退成一召唤就写盘。",
        "2. bid-parse / bid-compliance / bid-tech 与经营岗矩阵、再审共用同一 handoff。",
        "3. pack-ship 把真实 packing_summary 抄进 list/plan/export，断线 UNSPECIFIED。",
        "4. construction / method-hazard 高风险确认句后出讨论提纲，不写法定专项。",
        "5. 其余岗按大类补独有工具栏位（造价/计划/试验/财务/监理…），缺数不编。",
        "6. 有宿主后再做 kb:// 分页；扫描 PDF 仅可选 CLI，失败拒绝。",
    ]


def render_markdown(plans: List[Dict[str, Any]] | None = None) -> str:
    plans = plans or build_post_plans()
    lines = [
        "# 66 岗对照易标 / pack-agent 的长程规划（2026-08-17）",
        "",
        "每岗一条。车道 = `lane-<大类>`（子代理分批，不是 16 份大类摘要冒充）。",
        "易标完成度 = parse → outline → qa → kb → write。pack-agent = 数字只抄 solver + list/plan/export + 断线 UNSPECIFIED。",
        "内部讨论草稿。不以可以投标、可以开工、中标率 +N% 为完成目标。本轮只规划，不实现缺口。",
        "",
        "## 长程总序",
        "",
    ]
    lines.extend(f"- {x}" for x in horizon_order())
    lines += ["", "## 覆盖", "", f"- 岗位数：{len(plans)}", ""]
    cur = ""
    for p in plans:
        if p["category"] != cur:
            cur = p["category"]
            lines += ["", f"## 大类 `{cur}` · 车道 `{p['lane']}`", ""]
        lines += [
            f"### {p['id']}",
            "",
            f"- 名称：{p['name']}",
            f"- 子代理/车道：`{p['lane']}`",
            f"- 对照：{p['benchmark']}",
            f"- 独有：{', '.join(p['exclusive'])}",
        ]
        for k, v in (p.get("steps") or {}).items():
            lines.append(f"- {k}：{v}")
        lines += [f"- 下一刀：{p['next_knife']}", ""]
    return "\n".join(lines)
