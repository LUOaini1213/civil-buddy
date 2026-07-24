"""
LangGraph 节点实现（Harness 版）。

- 计算节点：白名单工具 + Schema 校验
- LLM 节点：解析意图 / 汇总解释（无 Key 时走规则回退）
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from packing_assistant.config import (
    OUTPUT_DIR,
    VALIDATION_MODE,
    assert_tool_allowed,
    normalize_container_type,
)
from packing_assistant.schemas import (
    validate_container_plan,
    validate_materials,
    validate_packing_result,
)
from packing_assistant.state import PackingState
from packing_assistant.tools import (
    check_risks,
    draw_layout,
    run_consolidation,
    run_packing,
)


# ---------------------------------------------------------------------------
# LLM 辅助（可选）
# ---------------------------------------------------------------------------

def _get_llm():
    """懒加载 ChatOpenAI；未配置 API Key 时返回 None。"""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI

        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": 0.2,
            "api_key": api_key,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    except Exception:
        return None


def _llm_invoke(system: str, user: str) -> Optional[str]:
    llm = _get_llm()
    if llm is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return str(resp.content)
    except Exception as e:
        return f"[LLM 调用失败: {e}]"


def _raise_or_warn(warnings: List[str], context: str) -> List[str]:
    if not warnings:
        return []
    tagged = [f"{context}: {w}" for w in warnings]
    if VALIDATION_MODE == "strict":
        raise ValueError("; ".join(tagged))
    return tagged


# ---------------------------------------------------------------------------
# 1. parse_input
# ---------------------------------------------------------------------------

def parse_input(state: PackingState) -> Dict[str, Any]:
    """解析用户输入，提取标准化材料清单。"""
    raw = (state.get("raw_input") or "").strip()
    existing = state.get("materials") or []
    warnings: List[str] = []

    instruction = state.get("user_instruction") or raw
    if existing and _looks_like_adjustment(instruction) and _materials_have_metrics(existing):
        materials, w = validate_materials(existing)
        warnings.extend(_raise_or_warn(w, "parse_input"))
        return {
            "materials": materials,
            "user_instruction": instruction,
            "validation_warnings": warnings,
            "messages": [
                {
                    "role": "system",
                    "content": "保留已有材料清单，识别为调整指令。",
                }
            ],
        }

    # 已注入且有效的材料（评测 / API）
    if existing and _materials_have_metrics(existing) and not _looks_like_material_input(raw):
        materials, w = validate_materials(existing)
        warnings.extend(_raise_or_warn(w, "parse_input"))
        return {
            "materials": materials,
            "container_type": normalize_container_type(state.get("container_type")),
            "validation_warnings": warnings,
            "messages": [
                {
                    "role": "assistant",
                    "content": f"使用预置材料 {len(materials)} 条。",
                }
            ],
        }

    materials = _rule_parse_materials(raw)

    if raw and _looks_like_material_input(raw):
        llm_text = _llm_invoke(
            system=(
                "你是钢结构装箱助手。从用户输入提取材料清单，只输出 JSON 数组，"
                "每项字段：名称, 规格, 数量, 单重_kg, 外尺寸_mm{长,宽,高}, 备注。"
                "无法确定的数字填 0。不要输出其它文字。"
            ),
            user=raw or json.dumps(existing, ensure_ascii=False),
        )
        if llm_text and not llm_text.startswith("[LLM"):
            parsed = _extract_json_array(llm_text)
            if parsed:
                materials = parsed

    if not materials and existing:
        materials = existing

    if not materials or not _materials_have_metrics(materials):
        materials = _demo_materials()
        warnings.append("parse_input: 未解析到有效材料，已回退演示默认清单")

    materials, w = validate_materials(materials)
    warnings.extend(_raise_or_warn(w, "parse_input"))

    return {
        "materials": materials,
        "container_type": normalize_container_type(state.get("container_type")),
        "validation_warnings": warnings,
        "messages": [
            {
                "role": "assistant",
                "content": f"已解析材料 {len(materials)} 条。",
            }
        ],
    }


def _demo_materials() -> List[Dict[str, Any]]:
    return [
        {
            "名称": "H型钢柱",
            "规格": "H400×200",
            "数量": 4,
            "单重_kg": 85,
            "外尺寸_mm": {"长": 3800, "宽": 400, "高": 200},
            "备注": "项目钢结构件",
        },
        {
            "名称": "钢梁",
            "规格": "H350×175",
            "数量": 6,
            "单重_kg": 55,
            "外尺寸_mm": {"长": 4200, "宽": 350, "高": 175},
            "备注": "",
        },
        {
            "名称": "连接板组件",
            "规格": "套件",
            "数量": 20,
            "单重_kg": 12,
            "外尺寸_mm": {"长": 800, "宽": 600, "高": 400},
            "备注": "木箱装",
        },
    ]


def _looks_like_adjustment(text: str) -> bool:
    keywords = ["重新算", "去掉", "删除", "换成", "改成", "重算", "调整", "不要"]
    return any(k in (text or "") for k in keywords)


def _looks_like_material_input(text: str) -> bool:
    t = (text or "").strip()
    if t.startswith("["):
        return True
    if re.search(r"\d+\s*(件|个|根|套|kg)", t, re.I):
        return True
    if re.search(r"\d+[x×]\d+", t):
        return True
    return False


def _materials_have_metrics(materials: List[Dict[str, Any]]) -> bool:
    for mat in materials:
        if float(mat.get("单重_kg") or 0) > 0:
            return True
        dims = mat.get("外尺寸_mm") or {}
        if float(dims.get("长") or 0) > 0:
            return True
    return False


def _rule_parse_materials(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    materials: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(
            r"(.+?)\s+(\d+)\s*(?:件|个|根|套)?\s*([\d.]+)?\s*kg?"
            r"(?:\s+([\d.]+)[x×]([\d.]+)[x×]([\d.]+))?",
            line,
            re.I,
        )
        if m:
            name = m.group(1).strip()
            qty = int(m.group(2))
            weight = float(m.group(3) or 0)
            L, W, H = m.group(4), m.group(5), m.group(6)
            materials.append(
                {
                    "名称": name,
                    "规格": name,
                    "数量": qty,
                    "单重_kg": weight,
                    "外尺寸_mm": {
                        "长": float(L or 0),
                        "宽": float(W or 0),
                        "高": float(H or 0),
                    },
                    "备注": "",
                }
            )
        else:
            materials.append(
                {
                    "名称": line,
                    "规格": line,
                    "数量": 1,
                    "单重_kg": 0,
                    "外尺寸_mm": {"长": 0, "宽": 0, "高": 0},
                    "备注": "待补全尺寸重量",
                }
            )
    return materials


def _extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "materials" in data:
            return data["materials"]
    except json.JSONDecodeError:
        start, end = text.find("["), text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


# ---------------------------------------------------------------------------
# 2. packing_agent
# ---------------------------------------------------------------------------

def packing_agent(state: PackingState) -> Dict[str, Any]:
    """生成木箱/铁箱方案（调用装箱算法）。"""
    assert_tool_allowed("run_packing")
    materials = list(state.get("materials") or [])
    instruction = state.get("user_instruction") or ""
    warnings: List[str] = []

    if "去掉" in instruction or "删除" in instruction:
        materials = _apply_remove_instruction(materials, instruction)

    materials, w = validate_materials(materials)
    warnings.extend(_raise_or_warn(w, "packing_agent.materials"))

    result = run_packing(materials)
    result, w = validate_packing_result(result)
    warnings.extend(_raise_or_warn(w, "packing_agent.boxes"))
    boxes = result.get("箱子列表") or []
    struct_summary = result.get("结构汇总") or {}

    # 结构不通过写入 warnings，便于 harness 观测
    for b in boxes:
        if (b.get("结构结论") or "") == "不通过":
            warnings.append(
                f"packing_agent: {b.get('箱号')} 结构不通过 "
                f"{(b.get('结构计算') or {}).get('风险点')}"
            )

    return {
        "materials": materials,
        "boxes": boxes,
        "structure_summary": struct_summary,
        "validation_warnings": warnings,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"装箱完成：共 {len(boxes)} 个箱子；"
                    f"结构：{struct_summary.get('结论', '-')}"
                ),
            }
        ],
    }


def _apply_remove_instruction(
    materials: List[Dict[str, Any]], instruction: str
) -> List[Dict[str, Any]]:
    m = re.search(r"(?:去掉|删除)\s*([^\s,，。]+)", instruction)
    if not m:
        return materials
    key = m.group(1)
    filtered = [
        mat
        for mat in materials
        if key not in str(mat.get("名称", ""))
        and key not in str(mat.get("规格", ""))
        and key not in str(mat.get("箱号", ""))
    ]
    return filtered if filtered else materials


# ---------------------------------------------------------------------------
# 3. consolidation_agent
# ---------------------------------------------------------------------------

def consolidation_agent(state: PackingState) -> Dict[str, Any]:
    """计算拼柜方案 + 好不好放。"""
    assert_tool_allowed("run_consolidation")
    boxes = state.get("boxes") or []
    ctype = normalize_container_type(state.get("container_type"))
    warnings: List[str] = []

    instruction = state.get("user_instruction") or ""
    for cand in ("45HQ", "40HQ", "40GP", "20GP"):
        if cand in instruction:
            ctype = cand
            break

    _, w = validate_packing_result({"箱子列表": boxes})
    warnings.extend(_raise_or_warn(w, "consolidation_agent.boxes"))

    plan = run_consolidation(boxes, container_type=ctype)
    plan, w = validate_container_plan(plan)
    warnings.extend(_raise_or_warn(w, "consolidation_agent.plan"))

    return {
        "container_type": ctype,
        "container_plan": plan,
        "validation_warnings": warnings,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"拼柜完成：{plan.get('柜型')} — {plan.get('结论')} "
                    f"(空间 {plan.get('空间利用率')}, 重量 {plan.get('重量利用率')})"
                ),
            }
        ],
    }


# ---------------------------------------------------------------------------
# 4. risk_check
# ---------------------------------------------------------------------------

def risk_check(state: PackingState) -> Dict[str, Any]:
    """检查超重、超尺寸、稳定性等。"""
    assert_tool_allowed("check_risks")
    boxes = state.get("boxes") or []
    plan = state.get("container_plan") or {}
    risks = check_risks(boxes, plan)

    polished = _llm_invoke(
        system=(
            "你是货运风险顾问。将下列风险点改写为简洁中文 bullet，"
            "保留全部事实，不要新增臆测。"
        ),
        user="\n".join(f"- {r}" for r in risks),
    )
    if polished and not polished.startswith("[LLM"):
        extra = [
            line.strip("- •").strip()
            for line in polished.splitlines()
            if line.strip()
        ]
        if extra:
            risks = extra

    return {
        "risks": risks,
        "messages": [
            {
                "role": "assistant",
                "content": f"风险检查完成：{len(risks)} 条提示。",
            }
        ],
    }


# ---------------------------------------------------------------------------
# 5. visualize
# ---------------------------------------------------------------------------

def visualize(state: PackingState) -> Dict[str, Any]:
    """生成 2D 布局图。"""
    assert_tool_allowed("draw_layout")
    plan = state.get("container_plan") or {}
    if not plan.get("布局"):
        return {
            "image_path": None,
            "messages": [{"role": "assistant", "content": "无布局数据，跳过出图。"}],
        }

    path = draw_layout(plan, output_dir=OUTPUT_DIR)
    return {
        "image_path": path,
        "messages": [
            {"role": "assistant", "content": f"布局图已生成：{path}"},
        ],
    }


# ---------------------------------------------------------------------------
# 6. summarize
# ---------------------------------------------------------------------------

def summarize(state: PackingState) -> Dict[str, Any]:
    """汇总最终回复；解析 next_action 供条件边使用。"""
    materials = state.get("materials") or []
    boxes = state.get("boxes") or []
    plan = state.get("container_plan") or {}
    risks = state.get("risks") or []
    image_path = state.get("image_path")
    instruction = state.get("user_instruction") or state.get("raw_input") or ""
    meta = state.get("harness_meta") or {}
    warns = state.get("validation_warnings") or []
    errors = state.get("errors") or []
    run_id = state.get("run_id") or "-"

    box_lines = []
    struct_lines = []
    for b in boxes:
        dims = b.get("外尺寸_mm") or {}
        sc = b.get("结构计算") or {}
        box_lines.append(
            f"  - {b.get('箱号')}: {b.get('箱型')} "
            f"{dims.get('长')}×{dims.get('宽')}×{dims.get('高')}mm, "
            f"净重 {b.get('净重_kg', '-')}kg / 毛重 {b.get('毛重_kg')}kg, "
            f"结构 {b.get('结构结论') or sc.get('结论') or '-'}, "
            f"属性 {b.get('特殊属性') or []}"
        )
        beam = (sc.get("底梁建议") or {}).get("截面建议_mm") or "-"
        floor = (sc.get("底面荷载") or {}).get("均布荷载_kg_m2")
        util = sc.get("结构利用率") or "-"
        risks_sc = "；".join((sc.get("风险点") or [])[:2]) or "无"
        struct_lines.append(
            f"  - {b.get('箱号')}: 结论={sc.get('结论')}, "
            f"利用率={util}, 底面荷载={floor}kg/m², 建议底梁={beam}, "
            f"风险={risks_sc}"
        )

    struct_summary = state.get("structure_summary") or {}
    risk_lines = "\n".join(f"  - {r}" for r in risks) or "  - 无"
    warn_lines = "\n".join(f"  - {w}" for w in warns[:10]) if warns else "  - 无"
    err_lines = "\n".join(f"  - {e}" for e in errors[:5]) if errors else "  - 无"

    template = f"""# 装箱与拼柜方案汇总
（远东新加坡陆路交通局办公楼项目 · 钢结构件）

## 材料清单
共 {len(materials)} 条

## 装箱方案（含结构计算）
共 {len(boxes)} 个箱子：
{chr(10).join(box_lines) or '  - 无'}

### 结构汇总
- 结论：{struct_summary.get('结论', '-')}
- 通过/需加强/不通过：{struct_summary.get('通过', 0)}/{struct_summary.get('需加强', 0)}/{struct_summary.get('不通过', 0)}
- 总净重：{struct_summary.get('总净重_kg', '-')} kg
- 总毛重：{struct_summary.get('总毛重_kg', '-')} kg

### 分箱结构明细
{chr(10).join(struct_lines) or '  - 无'}

## 拼柜方案
- 柜型：{plan.get('柜型', '-')}
- 结论：{plan.get('结论', '-')}
- 空间利用率：{plan.get('空间利用率', '-')}
- 重量利用率：{plan.get('重量利用率', '-')}

## 风险提示
{risk_lines}

## 布局图
{image_path or '未生成'}

## Harness
- run_id: {run_id}
- version: {meta.get('harness_version', '-')}
- packing: {meta.get('packing_algo', '-')}
- consolidation: {meta.get('consolidation_algo', '-')}
- validation_warnings:
{warn_lines}
- errors:
{err_lines}

---
如需调整，可说：「重新算」「去掉 钢梁」「换成 20GP」等。
"""

    llm_summary = _llm_invoke(
        system=(
            "你是面向项目现场的装箱顾问。根据结构化结果写清晰中文汇总，"
            "包含方案要点、能否顺利装柜、主要风险与下一步建议。简洁专业。"
        ),
        user=template,
    )
    final = (
        llm_summary
        if (llm_summary and not llm_summary.startswith("[LLM"))
        else template
    )

    next_action = "end"
    if state.get("enable_auto_reroute"):
        next_action = _infer_next_action(instruction)
        if (
            next_action != "end"
            and state.get("last_routed_instruction") == instruction
            and instruction
        ):
            next_action = "end"

    return {
        "final_response": final,
        "next_action": next_action,
        "last_routed_instruction": (
            instruction if next_action != "end" else state.get("last_routed_instruction")
        ),
        "messages": [{"role": "assistant", "content": final}],
    }


def _infer_next_action(instruction: str) -> Optional[str]:
    text = instruction or ""
    if any(k in text for k in ("重新装箱", "重做箱子", "重新算箱")):
        return "packing"
    if any(k in text for k in ("重新拼柜", "换柜", "换成", "重算拼柜")):
        return "consolidation"
    if any(k in text for k in ("重新算", "重算", "再算一遍")):
        return "packing"
    if any(k in text for k in ("去掉", "删除", "调整材料")):
        return "packing"
    return "end"
