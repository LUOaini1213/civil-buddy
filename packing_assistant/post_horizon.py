"""Per-post capability records and boundaries vs 易标 or pack-agent."""

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
        if exp.category == "design":
            return "已有 · 用户字段与附件表格按对象登记；扫描图像无 OCR 不读取，原始资料未核验"
        if exp.id == "bid-parse":
            return "已有 · bid-parse__extract / run_tender_pipeline（exact_text）"
        if any(x in " ".join(exp.exclusive) for x in ("extract", "takeoff", "parse", "record", "recon")):
            return f"部分 · 独有 {', '.join(exp.exclusive)} 可抄用户原文，无扫描 PDF"
        return "缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝"
    if step == "outline":
        if exp.category == "design":
            return "已有 · 本专业章节、提资与缺项表；Markdown + Excel，未连接设计计算引擎"
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
    "architecture": "已实现 T044 architecture：单体总平面、分区面积与功能、消防分区及疏散用户值、无障碍、竖向、节能和专业接口；缺面积、宽度不推算。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "structure": "已实现 T044 structure：单体体系、构件荷载与组合、材料、基础输入、抗震资料及复核清单；承载力、配筋和截面计算结果保持 UNSPECIFIED。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "geotech": "已实现 T044 geotech：孔号与分层、c/φ/水位和来源、勘探试验、地基比选、监测及提资；孔层缺项不借值，不替正式勘察报告。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "plumbing": "已实现 T045 plumbing：系统水源/水压、市政接驳、室内出户及井标高、给排水分区、雨水回用、消防水资料；管径和选泵计算待核。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "hvac": "已实现 T045 hvac：室内外参数、逐时冷热负荷、风水系统、防排烟联锁、机房竖井与消声保温；主机、风管及排烟量不代算。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "electrical": "已实现 T045 electrical：市政电源、容量和负荷系数、变配电用户方案、照明、防雷接地、线路及消防/弱电接口；不选变压器或电缆。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "fire-protect": "已实现 T045 fire-protect：救援条件、防火分区、疏散避难、消防水、防排烟、报警联动、电气及报审目录；不作审图通过或放行结论。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "steel": "已实现 T045 steel：构件体系与跨度、荷载、材料规格、螺栓焊缝、稳定支撑、防腐防火及加工安装接口；截面和连接计算未执行。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "landscape": "已实现 T046 landscape：软硬分区、竖向灌排、铺装及苗木规格数量、顶板覆土、室外设施和消防交通接口；未给苗木表不选规格。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "interior": "已实现 T046 interior：房间地墙顶及隔墙、防水材料厚度上翻、防潮隔声、门窗五金、天花开洞和外窗收口；只抄用户样板资料。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "facade": "已实现 T044 facade：幕墙体系、风压与分格、预埋后锚固、气密水密变位、防火防雷、加工检测和维护接口；不选厚度或签验收结论。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "intel-weak": "已实现 T046 intel-weak：子系统范围、点数及品牌、桥架路由、点位关联、供电 UPS 接地与消防网络接口；不编品牌或布点。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "civil-defense": "已实现 T046 civil-defense：防护单元等级及平战功能、口部/设备归属、通风滤毒超压、给排水和转换接口；不互换 CN/SG 概念或代审图。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "hydraulic": "已实现 T046 hydraulic：水工对象、水文断面和地勘孔、堤防护岸、闸泵用户参数、导流度汛和观测；无水文地质不选尺寸或流量。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "port": "已实现 T047 port：泊位船型、水位波浪潮流、结构比选、前沿尺度、航道回旋水域、装卸堆场与水利接口；不计算桩长或靠船力。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "municipal": "已实现 T047 municipal：路段桩号、平纵横断、路面结构、排水标高、管线权属及导改接口；不拆算车道宽或选路面厚度。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "bridge": "已实现 T047 bridge：桥位跨径及桥型比较、上下部结构、支座桥面、水文通航抗震及施工接口；不锁最优桥型或计算钢束桩长。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "tunnel": "已实现 T047 tunnel：用途净空、工法地层、开挖支护、防水接缝、监控量测、洞口及机电防灾接口；支护参数和监测阈值待核。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "traffic": "已实现 T047 traffic：交通影响/施工导改任务、调查来源与独立情景、组织及标志信号、仿真资料和指标；未运行仿真或优化配时。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "design-coord": "已实现 T047 design-coord：图纸版本、会审问题、提资责任期限、变更记录、逐条决议和闭环证据；不代签发，不内置审批面积阈值。依据仅抄用户资料、未核验；辖区与接口分栏。",
    "bim-coord": "已做 T043 bim-coord。bim-coord__clash 按 outline 出碰撞表（硬/间隙/留洞/4D），无模型整表待填。",
    "bim-qto": "已做 T043 bim-qto。bim-qto__rules 把过滤说明拆成行表，工程量只抄用户明确值，否则 UNSPECIFIED；单价 TBD。不接 IFC 真抽量。",
    "bim-deliver": "已做 T043 bim-deliver。bim-deliver__lod 一次写出坐标系/拆分/命名/LOD 表头，不宣称报审。",
    "plan-master": "plan-master__network 固定 WBS|紧前|里程碑待填|关键线路=待计算。",
    "plan-lookahead": "已做 T032 plan-lookahead。plan-lookahead__week 出四周表；制约未清不得写入本周承诺。",
    "plan-resource": "已做 T032 plan-resource。plan-resource__peak 拆劳动力|机具|材料三表，数量待填。",
    "construction": "run_expert_steps 在 scheme_draft 之后调用 fill_scheme_docx，不再跳过；仍是讨论提纲。",
    "method-hazard": "重写 judge-card.md 默认 SG WSH/PTW + 信息不足；37 号令只放 CN 栏。",
    "survey": "survey__record 读本会话附件，只抄已给点号坐标；都无则表头+[A001]。",
    "dispatch": "dispatch__daily 按 outline 十一章落表头；敏感作业只列名，判定交 method-hazard。",
    "safety-brief": "已做 T035 safety-brief。safety-brief__talk 按 outline 写全 11 栏；毫米/电话 [A001]；确认句后才写盘。",
    "quality": "已做 T035 quality。quality__lot 出主控|一般|隐蔽三表，结果=未检；写盘后 hse__scan_forbidden。",
    "env": "已做 T035 env。env__list 拆扬尘/弃土/污水/夜间/市容五行，限值 UNSPECIFIED。",
    "emergency": "已做 T035 emergency。emergency__plan 出综合目录+用户点名专项+演练表头，电话医院待填。",
    "cost": "cost__takeoff 按行 parse 清单成规则|量待填|单价 TBD，不编综合单价。",
    "variation": "variation__form 先判定文种再出事实|依据|签认空栏；无变更编号则依据待填。",
    "claim": "claim__notice 出意向栏+证据行+条款原文待贴；工期金额 TBD。",
    "subcontract": "subcontract__sheet 按行 parse 细目；无总包/业主确认不编金额。",
    "interim": "interim__measure 出开累/本期/监理审/业主核空表；无确认不编应付合价。",
    "proc-plan": "已做 T037 proc-plan。proc-plan__schedule 先分甲供/甲指/自采再列表；无供方周期则提前期 UNSPECIFIED。",
    "proc-compare": "已做 T037 proc-compare。proc-compare__table 一行一家多列；定商标待制度定；写盘后 scan_forbidden。",
    "proc-vendor": "已做 T037 proc-vendor。proc-vendor__eval 出准入|考察|短名单；分数/结论待核；禁止成交结论。",
    "equip": "已做 T036 equip。equip__ledger 写出与 Rust 同表头台账，只抄用户设备名与已给证件。",
    "warehouse": "已做 T036 warehouse。warehouse__log 按行 parse 收发原文；有数只抄、无数 TBD；无盘点不编盈亏。",
    "pack-ship": "sidecar/packing_summary 快照抄进 pack-ship__plan/export；先 health；无则四字段字面 UNSPECIFIED；禁止重算 xyz。",
    "material-site": "已做 T036 material-site。material-site__recon 按行 parse 应耗/领料/盘点；算不出节超则 TBD。",
    "lab-mix": "已做 T033 lab-mix。lab-mix__report 四层目录；无试验数据则施工配比整节待填。",
    "lab-sample": "已做 T033 lab-sample。lab-sample__list 出类别|部位|见证人空|升级路径；组数 [A001]。",
    "lab-record": "已做 T033 lab-record。lab-record__ledger 加报告编号待核|仪器检定|结论待填。",
    "finance-book": "已做 T038 finance-book。finance-book__check 出报销勾选+科目对照+对账缺口，金额 [A001]。",
    "finance-fund": "已做 T038 finance-fund。finance-fund__plan 出收入/支出窗口，金额 TBD，不当付款指令。",
    "finance-tax": "finance-tax__calendar 按辖区分行核对主体、税种、期间与来源；缺税率依据保留 UNSPECIFIED，用户给值仅作待核输入，不抄历史 KB 当现行税率。",
    "supervision": "已做 T034 supervision。supervision__reply：来文复述|拟办|证据目录；暂停/复工只出目录，不写复工许可。",
    "hr-recruit": "已做 T040 hr-recruit。hr-recruit__brief 出职责|任职|面试问法；薪资仅当用户给数才抄。",
    "hr-labor": "已做 T040 hr-labor。hr-labor__check 按合同类型分表+必备条款对照；补偿 [A001]。",
    "hr-train": "已做 T040 hr-train。hr-train__plan 出公司/项目/班组三层课题表+签到空栏。",
    "admin-doc": "已做 T041 admin-doc。admin-doc__draft 按文种套请示/纪要/用印三套栏，禁止代用印。",
    "admin-office": "已做 T041 admin-office。admin-office__list 出场地|议程|与会|资料目录，决定栏留空。",
    "it-ops": "已做 T042 it-ops。it-ops__runbook 出系统|角色|升级路径|联系人待填，禁止写密钥。",
    "it-data": "已做 T042 it-data。it-data__backup 按系统行出 RPO/RTO/介质/演练空，禁止编小时数。",
    "it-app": "已做 T042 it-app。it-app__srs 按行 parse 需求笔记成角色|场景|验收待填，禁止接口地址。",
    "worker-brief": "已做 T039 worker-brief。worker-brief__talk 按 script.md 写三段口播；无尺寸不报毫米。",
    "pm-daily": "已做 T039 pm-daily。pm-daily__log 出天气待填|部位|形象（不编百分比）|出勤待填。",
}

_DESIGN_TESTS = {
    "architecture": "scripts/test_design_basic_drafts.py",
    "structure": "scripts/test_design_basic_drafts.py",
    "geotech": "scripts/test_design_basic_drafts.py",
    "facade": "scripts/test_design_basic_drafts.py",
    "plumbing": "scripts/test_design_services_drafts.py",
    "hvac": "scripts/test_design_services_drafts.py",
    "electrical": "scripts/test_design_services_drafts.py",
    "fire-protect": "scripts/test_design_services_drafts.py",
    "steel": "scripts/test_design_services_drafts.py",
    "landscape": "scripts/test_design_specialties_drafts.py",
    "interior": "scripts/test_design_specialties_drafts.py",
    "intel-weak": "scripts/test_design_specialties_drafts.py",
    "civil-defense": "scripts/test_design_specialties_drafts.py",
    "hydraulic": "scripts/test_design_specialties_drafts.py",
    "port": "scripts/test_design_infrastructure_drafts.py",
    "municipal": "scripts/test_design_infrastructure_drafts.py",
    "bridge": "scripts/test_design_infrastructure_drafts.py",
    "tunnel": "scripts/test_design_infrastructure_drafts.py",
    "traffic": "scripts/test_design_infrastructure_drafts.py",
    "design-coord": "scripts/test_design_infrastructure_drafts.py",
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
        if exp.id in _DESIGN_TESTS:
            rec["evidence"] = _DESIGN_TESTS[exp.id]
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
        "5. T044–T047 的 20 岗已有逐岗专业文书；四组岗位回归见 product-plan §7.2，整体交付已通过本地解压验收。",
        "6. 本地发布验收已完成，后续按用户试用反馈迭代；未发布 GitHub Release。分页订阅等延期项不自动成为新主链。",
    ]


def render_markdown(plans: List[Dict[str, Any]] | None = None) -> str:
    plans = plans or build_post_plans()
    lines = [
        "# 66 岗对照易标 / pack-agent 的长程规划（2026-08-17）",
        "",
        "> 2026-09-12 更新：已做/未做以 [product-plan.md](product-plan.md) §7 / §15 为准；K4 内容闸已覆盖 66/66。",
        "> 本页保留 2026-08-17 的对照结构；设计 20 岗更新为实际专业栏位与测试证据，其余历史下一刀不得单独当成当前队列。",
        "",
        "每岗一条。车道 = `lane-<大类>`。设计岗新文书只整理用户明确给定的数字、规范名称和版本，全部未核验；未知辖区 UNSPECIFIED，DUAL 的依据与接口分别登记。历史 KB 的官方标题、版本或门槛不是新起草器自动填充的规则，不据此宣称法规范已复核。",
        "易标完成度 = parse → outline → qa → kb → write。pack-agent = 数字只抄 solver + list/plan/export + 断线 UNSPECIFIED。",
        "内部讨论草稿。不以可以投标、可以开工、中标率 +N% 为完成目标。L2 专业文书不等于设计求解、IFC 检查或法定签认；L3 仍仅 pack-ship。",
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
        label = "专业实现与边界" if p.get("evidence") else "历史下一刀 / 保持边界"
        lines += [f"- {label}：{p['next_knife']}"]
        if p.get("evidence"):
            lines.append(f"- 岗位回归：`{p['evidence']}`（给定/缺失输入、真实 Markdown/Excel、chat 与高风险门）")
        lines.append("")
    return "\n".join(lines)
