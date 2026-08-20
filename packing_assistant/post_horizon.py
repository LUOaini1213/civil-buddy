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


# Distinctive next-knives from lane-bid / lane-construction / lane-plant /
# lane-design / remaining-12 plan children. One string per seed id.
_NEXT = {
    "bid-parse": "expert_turn 把 run_tender_pipeline 的 handoff 另存 tender.handoff.json，供后岗读；本岗 submit_blocked 仍 true。",
    "bid-compliance": "expert_turn 专用 gaps：读 handoff 或重跑 pipeline，落盘三列已响应/未响应/招标未提供正文，不代判废标。",
    "bid-tech": "expert_turn 读 scoring_points 调 build_tech_outline_from_handoff；无评分点不套上个项目目录。",
    "architecture": "architecture__memo 按 outline.md 一次写 10 章，面积/疏散 [A001]，文末只贴已核官方标题。",
    "structure": "structure__calc_outline 按大纲落十章 + qa 自检表；无地勘不定承载力。",
    "geotech": "geotech__brief 只抄用户 SI 分层/孔号；未出现的 c/φ、水位写未在原文检出。",
    "plumbing": "plumbing__memo 按大纲落十章；管径/水压只抄用户资料，消防水量交消防岗。",
    "hvac": "hvac__memo 按大纲扩写；无负荷则主机/风管/排烟量 [A001]。",
    "electrical": "electrical__memo 落供配电/应急/防雷/消防电源；弱电整节交 intel-weak。",
    "fire-protect": "fire-protect__brief 按大纲写 11 章专篇目录；无来源限值，不替代审图。",
    "steel": "steel__memo 按大纲落体系/材料/连接；无跨度荷载不写梁高螺栓焊缝。",
    "landscape": "官方标题表锁定 Greenery 5.1；landscape__memo 只准抄表，胸径无苗木表则待填。",
    "interior": "interior__schedule 收成房间×饰面界面表；无样板不编品牌。",
    "facade": "facade__brief 按大纲落体系；无风压不写厚度；SG 稿禁 38 号/JGJ。",
    "intel-weak": "标题表锁定 COPIF 2018；2026 征求意见标非已生效；点数品牌待填。",
    "civil-defense": "成稿强制 SG/CN 分栏；SG 只抄 HS/SS 与 TRHS/THSS 标题，不写墙厚门樘。",
    "hydraulic": "三本 PUB COP 带生效日；Coastal Protection 必须同时写 2028 生效。",
    "port": "CN/SG 分栏标题表；SG 稿无 JTS；无水位波浪不写桩长。",
    "municipal": "municipal__memo 灌 principles.md；只抄 CDC A3 / SDRE Rev I 标题。",
    "bridge": "bridge__outline 比选不锁定最优；无跨径则梁高钢束失败。",
    "tunnel": "按用户工法分节；无地质不写支护参数；防火标题公路/轨交/房建不混。",
    "traffic": "traffic__skeleton 先选建成后 TIA 或施工导改；无流量不写饱和度。",
    "design-coord": "纪要收成表；文首只抄 APPBCA-2026-12（GFA≥5000 强制 Gateway）。",
    "bim-coord": "bim-coord__clash 按 outline 出碰撞表（硬/间隙/留洞/4D），无模型整表待填。",
    "bim-qto": "bim-qto__rules 把过滤说明拆成行表，工程量单价列固定 TBD。不接 IFC 真抽量。",
    "bim-deliver": "bim-deliver__lod 一次写出坐标系/拆分/命名/LOD 表头，不宣称报审。",
    "plan-master": "plan-master__network 固定 WBS|紧前|里程碑待填|关键线路=待计算。",
    "plan-lookahead": "已做 T032 plan-lookahead。plan-lookahead__week 出四周表；制约未清不得写入本周承诺。",
    "plan-resource": "已做 T032 plan-resource。plan-resource__peak 拆劳动力|机具|材料三表，数量待填。",
    "construction": "run_expert_steps 在 scheme_draft 之后调用 fill_scheme_docx，不再跳过；仍是讨论提纲。",
    "method-hazard": "重写 judge-card.md 默认 SG WSH/PTW + 信息不足；37 号令只放 CN 栏。",
    "survey": "survey__record 读本会话附件，只抄已给点号坐标；都无则表头+[A001]。",
    "dispatch": "dispatch__daily 按 outline 十一章落表头；敏感作业只列名，判定交 method-hazard。",
    "safety-brief": "safety-brief__talk 按 outline 写全 11 栏；毫米/电话 [A001]；确认句后才写盘。",
    "quality": "quality__lot 出主控|一般|隐蔽三表，结果=未检；写盘后 hse__scan_forbidden。",
    "env": "env__list 拆扬尘/弃土/污水/夜间/市容五行，限值 UNSPECIFIED。",
    "emergency": "emergency__plan 出综合目录+用户点名专项+演练表头，电话医院待填。",
    "cost": "cost__takeoff 按行 parse 清单成规则|量待填|单价 TBD，不编综合单价。",
    "variation": "variation__form 先判定文种再出事实|依据|签认空栏；无变更编号则依据待填。",
    "claim": "claim__notice 出意向栏+证据行+条款原文待贴；工期金额 TBD。",
    "subcontract": "subcontract__sheet 按行 parse 细目；无总包/业主确认不编金额。",
    "interim": "interim__measure 出开累/本期/监理审/业主核空表；无确认不编应付合价。",
    "proc-plan": "proc-plan__schedule 先分甲供/甲指/自采再列表，提前期 UNSPECIFIED。",
    "proc-compare": "proc-compare__table 一行一家多列；定商标待制度定；写盘后 scan_forbidden。",
    "proc-vendor": "proc-vendor__eval 出准入|考察|短名单，分数/结论待核，禁止中标结论。",
    "equip": "expert_turn 用 equip__ledger 写出与 Rust 同表头台账，只抄用户设备名与已给证件。",
    "warehouse": "warehouse__log 按行 parse 收发原文；有数只抄、无数 TBD；无盘点不编盈亏。",
    "pack-ship": "sidecar/packing_summary 快照抄进 pack-ship__plan/export；先 health；无则四字段字面 UNSPECIFIED；禁止重算 xyz。",
    "material-site": "material-site__recon 按行 parse 应耗/领料/盘点；算不出节超则 TBD。",
    "lab-mix": "已做 T033 lab-mix。lab-mix__report 四层目录；无试验数据则施工配比整节待填。",
    "lab-sample": "lab-sample__list 出类别|部位|见证人空|升级路径；组数 [A001]。",
    "lab-record": "lab-record__ledger 加报告编号待核|仪器检定|结论待填。",
    "finance-book": "finance-book__check 出报销勾选+科目对照+对账缺口，金额 [A001]。",
    "finance-fund": "finance-fund__plan 出收入/支出窗口，金额 TBD，不当付款指令。",
    "finance-tax": "finance-tax__calendar 加税种|节点|资料是否齐全；税率空白，只可抄 IRAS 页述 9%。",
    "supervision": "supervision__reply：来文复述|拟办|证据目录；暂停/复工只出目录，不写复工许可。",
    "hr-recruit": "hr-recruit__brief 出职责|任职|面试问法；薪资仅当用户给数才抄。",
    "hr-labor": "hr-labor__check 按合同类型分表+必备条款对照；补偿 [A001]。",
    "hr-train": "hr-train__plan 出公司/项目/班组三层课题表+签到空栏。",
    "admin-doc": "admin-doc__draft 按文种套请示/纪要/用印三套栏，禁止代用印。",
    "admin-office": "admin-office__list 出场地|议程|与会|资料目录，决定栏留空。",
    "it-ops": "it-ops__runbook 出系统|角色|升级路径|联系人待填，禁止写密钥。",
    "it-data": "it-data__backup 按系统行出 RPO/RTO/介质/演练空，禁止编小时数。",
    "it-app": "it-app__srs 按行 parse 需求笔记成角色|场景|验收待填，禁止接口地址。",
    "worker-brief": "worker-brief__talk 按 script.md 写三段口播；无尺寸不报毫米。",
    "pm-daily": "pm-daily__log 出天气待填|部位|形象（禁编百分比）|出勤待填。",
}


def _next_knife(exp) -> str:
    if exp.id in _NEXT:
        return _NEXT[exp.id]
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
