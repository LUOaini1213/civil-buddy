"""
自然语言改方案。

契约：
- 能解析并执行 → 改方案，返回 status=applied
- 不能解析/不支持 → 不改任何状态，返回 status=unsupported（无此功能）

支持（规则 + 可选 LLM 增强）：
- 去掉/删除 某材料
- 柜型 40HQ/40GP/20GP
- 箱型偏好 / 强制箱型
- 详设截面：框架用槽钢16#、底板槽钢12#×3
- γ / 安全系数
- 拆箱/加固 意图
- max_containers
- 一排 / 两排（柜内并排放箱偏好）
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

# 对外可见的能力清单（无此功能时回显）
SUPPORTED_CAPABILITIES: List[str] = [
    "要一排 / 要两排",
    "柜型 40HQ/40GP/20GP/45HQ",
    "去掉/删除 某材料",
    "强制箱型（如 4米铁架）",
    "框架/底板截面、γ、图纸号",
    "最多 N 柜",
    "密装 / 标准箱 / 加固",
]

_HINTS = [
    "要一排",
    "要两排",
    "柜型改 40GP",
    "去掉 连接板",
    "框架用槽钢16#，γ=2.0",
]


def _unsupported(raw: str, message: str) -> Dict[str, Any]:
    """统一「无此功能」返回体（不改 state）。"""
    return {
        "ops": [],
        "logs": [],
        "raw": raw,
        "ok": False,
        "applied": False,
        "feature_available": False,
        "status": "unsupported",
        "message": message if message.startswith("无此功能") else f"无此功能：{message}",
        "notes": [],
        "hints": list(_HINTS),
        "supported_capabilities": list(SUPPORTED_CAPABILITIES),
    }


def parse_nl_revision(text: str) -> Dict[str, Any]:
    """解析自然语言 → 结构化 ops。不支持则 status=unsupported。"""
    t = (text or "").strip()
    ops: List[Dict[str, Any]] = []
    notes: List[str] = []

    if not t:
        return _unsupported("", "请输入改方案指令")

    # 柜型
    m = re.search(r"(?:柜型|集装箱|改成|换成|用)\s*(40HQ|40GP|20GP|45HQ)", t, re.I)
    if not m:
        m = re.search(r"\b(40HQ|40GP|20GP|45HQ)\b", t, re.I)
    if m:
        ops.append({"op": "set_container_type", "value": m.group(1).upper()})

    # 去掉材料（排除「不要两排/一排」等排法用语）
    _skip_rm = {
        "两排", "一排", "单排", "双排", "1排", "2排",
        "两排对齐", "密装", "标准箱", "标准铁架",
    }
    for m in re.finditer(r"(?:去掉|删除|不要|移除)\s*([^\s,，。；;]+)", t):
        kw = m.group(1).strip()
        if kw in _skip_rm or re.match(r"^[12]排$", kw):
            continue
        ops.append({"op": "remove_material", "keyword": kw})

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

    # 一排 / 两排（柜宽方向并放偏好）
    # 口语：「要一排的」「改成单排」「不要两排」「两排对齐」
    want_single = bool(
        re.search(
            r"(?:只要|强制|改成|换成|用)?\s*(?:一排|单排|1排)|"
            r"不要\s*两排|取消\s*两排|关(?:闭)?两排|禁止两排|"
            r"要一排|一排放|单排放",
            t,
        )
    )
    want_two = bool(
        re.search(
            r"(?:只要|强制|改成|换成|用)?\s*(?:两排|双排|2排)|"
            r"两排对齐|两排优先|要两排|双排放",
            t,
        )
    )
    # 「不要两排」已算单排；若同时命中两排字样但带否定，以单排为准
    if want_single and not re.search(r"不要\s*一排|取消\s*一排", t):
        ops.append({"op": "set_packing_option", "key": "prefer_single_row", "value": True})
        ops.append({"op": "set_packing_option", "key": "prefer_two_row", "value": False})
        # 两排 snappoint 只在定制外廓生效；关标准箱以便改宽
        ops.append({"op": "set_packing_option", "key": "standard_boxes", "value": False})
        notes.append("一排=外宽略超半柜，柜内只能并一列")
    elif want_two and not want_single:
        ops.append({"op": "set_packing_option", "key": "prefer_single_row", "value": False})
        ops.append({"op": "set_packing_option", "key": "prefer_two_row", "value": True})
        notes.append("两排=1100/1150 snappoint 优先")

    # 可选 LLM 增强（仅当规则零命中）
    if not ops and len(t) >= 4:
        llm_ops = _llm_parse(t)
        if llm_ops:
            ops.extend(llm_ops)
            notes.append("含 LLM 解析增强")

    if not ops:
        return _unsupported(
            t,
            f"当前不支持「{t}」这类改法",
        )

    return {
        "ops": ops,
        "raw": t,
        "ok": True,
        "applied": False,  # 应用后由 revise_with_natural_language 置 True
        "feature_available": True,
        "status": "parsed",
        "message": f"可执行：解析到 {len(ops)} 条操作",
        "notes": notes,
        "hints": [],
        "supported_capabilities": list(SUPPORTED_CAPABILITIES),
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
                "一排/单排 → set_packing_option key=prefer_single_row value=true，"
                "并 set_packing_option key=standard_boxes value=false；"
                "两排 → set_packing_option key=prefer_two_row value=true。"
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
    """
    解析并应用；不自动重跑图。

    - 可改：写入 materials/options/design_facts，status=applied
    - 不可改：原 state 不动，status=unsupported（无此功能）
    """
    parsed = parse_nl_revision(text)
    if not parsed.get("ok") or not parsed.get("ops"):
        nr = dict(parsed)
        nr.setdefault("status", "unsupported")
        nr.setdefault("feature_available", False)
        nr.setdefault("applied", False)
        if not str(nr.get("message") or "").startswith("无此功能"):
            nr["message"] = f"无此功能：{nr.get('message') or text}"
        return {
            **state,
            "nl_revision": nr,
            # 不写入失败为“已改”的 agent 步骤，仅记一条助手提示
            "messages": list(state.get("messages") or [])
            + [{"role": "assistant", "content": nr["message"]}],
        }
    new_s, logs = apply_revision_ops(state, parsed["ops"])
    if not logs:
        # 解析到 ops 但应用无效果 → 仍视为无有效改动
        nr = _unsupported(text, "指令已识别但未产生可应用变更")
        return {**state, "nl_revision": nr}

    msg = "已改方案：" + "；".join(logs)
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
            "artifacts": {"ops": parsed["ops"], "logs": logs, "status": "applied"},
            "role": "user",
            "status": "ok",
        }
    )
    new_s["messages"] = msgs
    new_s["agent_steps"] = steps
    new_s["nl_revision"] = {
        **parsed,
        "logs": logs,
        "ok": True,
        "applied": True,
        "feature_available": True,
        "status": "applied",
        "message": msg,
        "supported_capabilities": list(SUPPORTED_CAPABILITIES),
    }
    return new_s
