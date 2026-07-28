"""
自然语言改方案。

支持（规则 + 可选 LLM 增强）：
- 去掉/删除 某材料
- 柜型 40HQ/40GP/20GP
- 箱型偏好 / 强制箱型
- 详设截面：框架用槽钢16#、底板槽钢12#×3
- γ / 安全系数
- 拆箱/加固 意图
- max_containers
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


def parse_nl_revision(text: str) -> Dict[str, Any]:
    """解析自然语言 → 结构化 ops。"""
    t = (text or "").strip()
    ops: List[Dict[str, Any]] = []
    notes: List[str] = []

    if not t:
        return {"ops": [], "raw": t, "ok": False, "message": "空指令"}

    # 柜型
    m = re.search(r"(?:柜型|集装箱|改成|换成|用)\s*(40HQ|40GP|20GP|45HQ)", t, re.I)
    if not m:
        m = re.search(r"\b(40HQ|40GP|20GP|45HQ)\b", t, re.I)
    if m:
        ops.append({"op": "set_container_type", "value": m.group(1).upper()})

    # 去掉材料
    for m in re.finditer(r"(?:去掉|删除|不要|移除)\s*([^\s,，。；;]+)", t):
        ops.append({"op": "remove_material", "keyword": m.group(1)})

    # 强制箱型
    m = re.search(
        r"(?:强制|全部|统一)?(?:用|改成|换成)?\s*([0-9.]+米(?:铁架|木箱|框)|铁笼|木箱)",
        t,
    )
    if m:
        ops.append({"op": "force_box_type", "value": m.group(1)})

    # 详设：框架截面
    m = re.search(
        r"(?:框架|立柱|侧柱)(?:用|改为|改成|截面)?\s*([槽方矩]管?钢?[\d#x×*]+|[^\s,，]{2,20})",
        t,
    )
    if m:
        ops.append({"op": "set_frame_section", "value": _norm_section(m.group(1))})

    m = re.search(
        r"(?:底板|底梁|纵梁)(?:用|改为|改成|截面)?\s*(槽钢\d+#?|方管\d+x\d+x\d+)",
        t,
    )
    if m:
        sec = _norm_section(m.group(1))
        cnt_m = re.search(
            r"(?:底板|底梁|纵梁).{0,24}?(\d+)\s*根",
            t,
        )
        ops.append(
            {
                "op": "set_bottom_beam",
                "value": sec,
                "count": int(cnt_m.group(1)) if cnt_m else None,
            }
        )

    m = re.search(r"(?:γ|gamma|安全系数)\s*[=:：]?\s*([0-9.]+)", t, re.I)
    if m:
        ops.append({"op": "set_gamma", "value": float(m.group(1))})

    m = re.search(r"(?:图纸|详设|图号)\s*[=:：]?\s*([A-Za-z0-9\-_/\.]+)", t)
    if m:
        ops.append({"op": "set_drawing_no", "value": m.group(1)})

    m = re.search(r"(?:最多|上限|封顶)?\s*(\d+)\s*柜", t)
    if m:
        ops.append({"op": "set_max_containers", "value": int(m.group(1))})

    if re.search(r"加固|加斜撑|加强", t):
        ops.append({"op": "flag_reinforce", "value": True})

    if re.search(r"密装|dense", t, re.I):
        ops.append({"op": "set_packing_option", "key": "dense_mode", "value": True})

    if re.search(r"标准箱|标准铁架", t):
        ops.append({"op": "set_packing_option", "key": "standard_boxes", "value": True})

    # 可选 LLM 增强
    if not ops and len(t) >= 4:
        llm_ops = _llm_parse(t)
        if llm_ops:
            ops.extend(llm_ops)
            notes.append("含 LLM 解析增强")

    return {
        "ops": ops,
        "raw": t,
        "ok": bool(ops),
        "message": f"解析到 {len(ops)} 条操作" if ops else "未识别可执行指令",
        "notes": notes,
    }


def _norm_section(s: str) -> str:
    s = (s or "").strip().rstrip("，。；;")
    s = s.replace("×", "x").replace("*", "x")
    # 槽钢16 → 槽钢16#
    if re.match(r"^槽钢\d+$", s):
        s = s + "#"
    return s


def _llm_parse(text: str) -> List[Dict[str, Any]]:
    try:
        from packing_assistant.llm import chat_json_array, llm_available

        if not llm_available():
            return []
        arr = chat_json_array(
            system=(
                "你是装箱方案修改助手。把用户中文改成 JSON 数组，每项 op 只能是："
                "set_container_type, remove_material, force_box_type, set_frame_section, "
                "set_bottom_beam, set_gamma, set_drawing_no, set_max_containers, flag_reinforce, "
                "set_packing_option。"
                "字段用 value/keyword/count/key。只输出数组。"
            ),
            user=text,
        )
        out = []
        for x in arr or []:
            if isinstance(x, dict) and x.get("op"):
                out.append(x)
        return out
    except Exception:
        return []


def apply_revision_ops(
    state: Dict[str, Any],
    ops: List[Dict[str, Any]],
    *,
    target_box_type: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """应用 ops 到 state 副本，返回 (new_state, log_lines)。"""
    s = deepcopy(state)
    logs: List[str] = []
    mats = list(s.get("materials") or [])
    facts = dict(s.get("design_facts") or {})
    facts.setdefault("box_types", {})
    facts.setdefault("defaults", {})
    opts = dict(s.get("packing_options") or {})

    for op in ops:
        kind = op.get("op")
        if kind == "set_container_type":
            s["container_type"] = str(op.get("value") or "40HQ").upper()
            logs.append(f"柜型→{s['container_type']}")
        elif kind == "remove_material":
            kw = str(op.get("keyword") or "")
            before = len(mats)
            mats = [
                m
                for m in mats
                if kw not in str(m.get("name") or "")
                and kw not in str(m.get("id") or "")
                and kw not in str(m.get("spec") or "")
            ]
            logs.append(f"去掉含「{kw}」材料：{before}→{len(mats)} 行")
        elif kind == "force_box_type":
            bt = str(op.get("value") or "")
            opts["force_box_type"] = bt
            logs.append(f"强制箱型→{bt}")
        elif kind == "set_frame_section":
            sec = str(op.get("value") or "")
            key = target_box_type or _default_box_key(facts)
            facts["box_types"].setdefault(key, {})
            facts["box_types"][key]["frame_section"] = sec
            facts["fidelity"] = "detailed_design"
            facts["source"] = facts.get("source") or "自然语言修订"
            logs.append(f"详设·{key} 框架截面→{sec}")
        elif kind == "set_bottom_beam":
            sec = str(op.get("value") or "")
            cnt = op.get("count")
            key = target_box_type or _default_box_key(facts)
            facts["box_types"].setdefault(key, {})
            facts["box_types"][key]["bottom_beam_section"] = sec
            if cnt:
                facts["box_types"][key]["bottom_beam_count"] = int(cnt)
            facts["fidelity"] = "detailed_design"
            facts["source"] = facts.get("source") or "自然语言修订"
            logs.append(f"详设·{key} 底梁→{sec}" + (f"×{cnt}" if cnt else ""))
        elif kind == "set_gamma":
            g = float(op.get("value") or 1.8)
            facts["defaults"]["gamma"] = g
            facts["fidelity"] = "detailed_design"
            logs.append(f"详设·γ→{g}")
        elif kind == "set_drawing_no":
            facts["drawing_no"] = str(op.get("value") or "")
            for _k, v in facts.get("box_types", {}).items():
                if isinstance(v, dict) and not v.get("drawing_no"):
                    v["drawing_no"] = facts["drawing_no"]
            logs.append(f"图纸号→{facts['drawing_no']}")
        elif kind == "set_max_containers":
            s["max_containers"] = int(op.get("value") or 0)
            logs.append(f"3D 封顶柜数→{s['max_containers']}")
        elif kind == "flag_reinforce":
            facts["defaults"]["require_reinforcement_note"] = True
            logs.append("标记需要加固")
        elif kind == "set_packing_option":
            opts[str(op.get("key"))] = op.get("value")
            logs.append(f"装箱选项 {op.get('key')}={op.get('value')}")

    s["materials"] = mats
    s["design_facts"] = facts
    s["packing_options"] = opts
    s["adjust_note"] = (s.get("adjust_note") or "") + " | NL: " + "; ".join(logs)
    s["nl_revision"] = {"ops": ops, "logs": logs}
    return s, logs


def _default_box_key(facts: Dict[str, Any]) -> str:
    bts = facts.get("box_types") or {}
    if bts:
        return next(iter(bts.keys()))
    return "4米铁架"


def revise_with_natural_language(state: Dict[str, Any], text: str) -> Dict[str, Any]:
    """解析并应用；不自动重跑图。"""
    parsed = parse_nl_revision(text)
    if not parsed.get("ok"):
        return {
            **state,
            "nl_revision": parsed,
            "messages": list(state.get("messages") or [])
            + [{"role": "assistant", "content": f"未能解析改方案指令：{text}"}],
        }
    new_s, logs = apply_revision_ops(state, parsed["ops"])
    msg = "自然语言改方案已应用：" + "；".join(logs)
    msgs = list(new_s.get("messages") or [])
    msgs.append({"role": "user", "content": f"【改方案】{text}"})
    msgs.append({"role": "assistant", "content": msg + "｜tools=nl_revision.parse_apply"})
    steps = list(new_s.get("agent_steps") or [])
    steps.append(
        {
            "node": "nl_revision",
            "title": "自然语言改方案",
            "message": msg,
            "tools_used": ["nl_revision.parse_nl", "nl_revision.apply_ops"],
            "artifacts": {"ops": parsed["ops"], "logs": logs},
            "role": "user",
        }
    )
    new_s["messages"] = msgs
    new_s["agent_steps"] = steps
    new_s["nl_revision"] = {**parsed, "logs": logs}
    return new_s
