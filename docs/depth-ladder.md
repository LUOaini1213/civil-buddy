# 66 岗深度分级（Depth Ladder · 对人诚实）

> 更新：2026-09-12（设计 20 岗逐岗专业文书与 105 项实测通过）· 依据 [product-plan.md](civil-buddy/product-plan.md) §3.2 / §6 / §7.2。
> **铁律：广度以"路线图"形态出现，深度以"可复跑证据"形态出现。** 本页每一条深度声明都挂验收文件或可复跑命令；不确定的岗宁可标低不标高。

## 三级阶梯

| 级 | 定义 | 覆盖 | 验收（可复跑） |
|----|------|------|----------------|
| **L1 KB 草稿岗** | 每岗四件套：faq≥5 + README 字段表 + outline 缺数栏 + `search_kb` 命中本岗（且不见兄弟岗私库） | **66/66** | `python scripts/test_kb_k4_depth.py` → `PASS kb_k4_depth experts=66 faq5=66 fields=66 gaps=66 search_hit=66` |
| **L2 工具写盘岗** | 该岗有自己的成稿栏位/写盘函数（非通用 `_draft_markdown` 骨架句） | **66/66** | 依据 product-plan §3.2/§7.2 逐岗字段和测试证据；T044–T047 新增 20 岗，真实 Markdown 与 Excel 的四组回归共 105 项通过；新分发包另做本地验收 |
| **L3 引擎岗** | 硬数字走本仓引擎：NL→IntentSpec→白名单 tools→HITL→影子评测 | **1**（pack-ship） | `python scripts/demo_one_shot.py` → ALL_PASS；`python scripts/eval_competition_scorecard.py --skip-phase0` → 综合分 **8.85**（本地校准、对外口径）门禁全 PASS |

**L3 pack-ship 证据链（冻结口径，演示日不现场重跑大票对照）：**

- 446t 单票：现行全 Agent **25×40HQ**（`phase=done / risk=WARN / ship_ok=true`），命令 `python scripts/compare_446t_agent_vs_tool.py --full-agent`。**注意**：该命令依赖本地业务数据 `output/cases_446t/materials.json`（客户衍生清单，按本仓 local-only 政策不进仓），净仓环境跑不了属预期；冻结数字以 [docs/competition-evidence-one-pager.md](competition-evidence-one-pager.md) 存档记录为准，演示/评审不现场重跑。早期的「29 柜」基线已废弃，README 与本页均不再引用；可在净仓复跑的公开货样评测是 `docs/eval/fanout16x8-2026-09-02/`
- **mid50 0.594**：同一对照产物，贴 CTU 严格偏好 60% 线，风险 WARN；少柜 light 路径 mid≈0.17 仅参考、不作出运结论
- 综合分 **8.85**：本地校准评分卡，phase0 quick（n=12，pass_rate 1.0）封顶口径，**不报 10.0**

**UNSPECIFIED 是特性，不是未完成。** 每岗成稿缺数处一律写 `[A001]` / `UNSPECIFIED` / `TBD`，不编造数字、不冒充签认件——这是产品纪律（tools compute numbers; the model only routes）的直接体现，也是 L1 验收闸（gaps=66）的一部分。

**R5 每岗记分卡抽样（L2 附加验收）**：`python scripts/eval_post_scorecard.py --all-pilots` 对 5 个试点岗（bid-parse / bid-compliance / bid-tech / cost / safety-brief，覆盖 bid/commercial/hse 三大类）跑四门禁——G1 意图命中（金句 intent+skill）、G2 KB 检索命中私有库、G3 exclusive 工具离线产出覆盖 README 字段表必需栏、G4 缺数空态保留 `[A001]`/UNSPECIFIED 且 `forbidden_hits==0`。当前 5/5 全 PASS；该脚本已登记 precommit（quick 预算跑 2 岗）。

## 16 车道 × L1/L2/L3 分级表

数据提取自 product-plan §6（车道/岗数）与 §7.2（逐岗字段与验收，该表为状态权威）。设计 20 岗已各有专业文书，本地发布验收已完成，后续按用户试用反馈迭代；不把文书写盘提升为设计求解能力。

| # | 车道 | 大类 | 岗数 | L1 | L2 | L3 | 已富化岗（写盘） | 验收 |
|---|------|------|------|----|----|----|------------------|------|
| 1 | `lane-bid` | 经营投标 | 3 | 3 | 3 | 0 | bid-parse / bid-compliance / bid-tech（handoff 三列 + 评分点目录） | `python scripts/test_tender_handoff.py` |
| 2 | `lane-design` | 勘察设计 | 20 | 20 | 20 | 0 | 基础设计 4 岗、机电及钢结构 5 岗、专项 5 岗、基础设施及统筹 6 岗；只整理用户输入 | 四个 `scripts/test_design_*_drafts.py`，逐岗证据见下 |
| 3 | `lane-bim` | BIM | 3 | 3 | 3 | 0 | bim-coord / bim-qto / bim-deliver（专用记录，不执行 IFC 检查） | `python scripts/test_bim_drafts.py` |
| 4 | `lane-planning` | 计划 | 3 | 3 | 3 | 0 | plan-master / plan-lookahead / plan-resource（T032） | product-plan §7.2 行 12–14 |
| 5 | `lane-construction` | 施工生产 | 4 | 4 | 4 | 0 | construction（十一章 + fill_scheme/`docx_pending`）、method-hazard（判定书）、survey / dispatch（T030） | `python scripts/test_construction_skill_path.py` |
| 6 | `lane-hse` | 安质环 | 4 | 4 | 4 | 0 | safety-brief（11 栏，毫米/电话 `[A001]`）/ quality / env / emergency（T035） | product-plan §7.2 行 19–22 |
| 7 | `lane-commercial` | 商务造价 | 5 | 5 | 5 | 0 | cost（takeoff，无单价 UNSPECIFIED）/ variation / claim / subcontract / interim（T031） | product-plan §7.2 行 5、8–11 |
| 8 | `lane-procurement` | 采购 | 3 | 3 | 3 | 0 | proc-plan / proc-compare / proc-vendor（T037） | product-plan §7.2 行 26–28 |
| 9 | `lane-plant` | 物机 | 4 | 4 | 4 | **1** | pack-ship（引擎岗）+ equip / warehouse / material-site（T036） | `python scripts/demo_one_shot.py` + `python scripts/eval_competition_scorecard.py --skip-phase0` |
| 10 | `lane-lab` | 试验室 | 3 | 3 | 3 | 0 | lab-mix / lab-sample / lab-record（T033） | product-plan §7.2 行 15–17 |
| 11 | `lane-finance` | 财务 | 3 | 3 | 3 | 0 | finance-tax（日历页述 9%、申报期空栏）/ finance-book / finance-fund（T038） | product-plan §7.2 行 6、29–30 |
| 12 | `lane-docs` | 资料监理 | 1 | 1 | 1 | 0 | supervision（T034） | product-plan §7.2 行 18 |
| 13 | `lane-hr` | 人力 | 3 | 3 | 3 | 0 | hr-recruit / hr-labor / hr-train（合同与人员分表、三级培训） | `python scripts/test_hr_drafts.py` + `scripts/test_expert_turn.py` |
| 14 | `lane-admin` | 行政 | 2 | 2 | 2 | 0 | admin-doc / admin-office（请示、纪要、用印及会务；不代决定） | `python scripts/test_admin_drafts.py` |
| 15 | `lane-it` | IT | 3 | 3 | 3 | 0 | it-ops / it-data / it-app（独立系统记录及凭据过滤） | `python scripts/test_it_drafts.py` |
| 16 | `lane-people` | 项目与工人 | 2 | 2 | 2 | 0 | worker-brief（三段口播，无尺寸不报毫米）/ pm-daily（T039） | product-plan §7.2 行 31–32 |
| — | **合计** | | **66** | **66** | **66** | **1** | | |

> 代码证据：`packing_assistant/expert_turn.py` 的原有专业函数，以及 `packing_assistant/post_drafts/` 中按岗位分派的纯起草器。L2 指专业章节、用户字段、提资与缺项表进入真实产物。
> 设计 20 岗的依据名称、版本、参数均只登记用户资料并标未核验；未知辖区为 UNSPECIFIED，DUAL 依据与接口分栏。未连接新的设计计算器、IFC 解析、碰撞或仿真引擎；L3 仍是 1。

## 设计 20 岗逐岗证据

| 岗位 | 已实现的专业栏位与边界 | 实际产物回归 |
|------|------------------------|--------------|
| architecture（建筑） | 单体总平面、分区面积与功能、消防分区及疏散用户值、无障碍、竖向、节能和专业接口；缺面积、宽度不推算 | `scripts/test_design_basic_drafts.py` |
| structure（结构） | 单体体系、构件荷载与组合、材料、基础输入、抗震资料及复核清单；承载力、配筋和截面计算结果保持 UNSPECIFIED | `scripts/test_design_basic_drafts.py` |
| geotech（岩土勘察） | 孔号与分层、c/φ/水位和来源、勘探试验、地基比选、监测及提资；孔层缺项不借值，不替正式勘察报告 | `scripts/test_design_basic_drafts.py` |
| facade（幕墙） | 幕墙体系、风压与分格、预埋后锚固、气密水密变位、防火防雷、加工检测和维护接口；不选厚度或签验收结论 | `scripts/test_design_basic_drafts.py` |
| plumbing（给排水） | 系统水源/水压、市政接驳、室内出户及井标高、给排水分区、雨水回用、消防水资料；管径和选泵计算待核 | `scripts/test_design_services_drafts.py` |
| hvac（暖通） | 室内外参数、逐时冷热负荷、风水系统、防排烟联锁、机房竖井与消声保温；主机、风管及排烟量不代算 | `scripts/test_design_services_drafts.py` |
| electrical（电气） | 市政电源、容量和负荷系数、变配电用户方案、照明、防雷接地、线路及消防/弱电接口；不选变压器或电缆 | `scripts/test_design_services_drafts.py` |
| fire-protect（消防） | 救援条件、防火分区、疏散避难、消防水、防排烟、报警联动、电气及报审目录；不作审图通过或放行结论 | `scripts/test_design_services_drafts.py` |
| steel（钢结构） | 构件体系与跨度、荷载、材料规格、螺栓焊缝、稳定支撑、防腐防火及加工安装接口；截面和连接计算未执行 | `scripts/test_design_services_drafts.py` |
| landscape（园林景观） | 软硬分区、竖向灌排、铺装及苗木规格数量、顶板覆土、室外设施和消防交通接口；未给苗木表不选规格 | `scripts/test_design_specialties_drafts.py` |
| interior（室内装修） | 房间地墙顶及隔墙、防水材料厚度上翻、防潮隔声、门窗五金、天花开洞和外窗收口；只抄用户样板资料 | `scripts/test_design_specialties_drafts.py` |
| intel-weak（智能化弱电） | 子系统范围、点数及品牌、桥架路由、点位关联、供电 UPS 接地与消防网络接口；不编品牌或布点 | `scripts/test_design_specialties_drafts.py` |
| civil-defense（人防） | 防护单元等级及平战功能、口部/设备归属、通风滤毒超压、给排水和转换接口；不互换 CN/SG 概念或代审图 | `scripts/test_design_specialties_drafts.py` |
| hydraulic（水利） | 水工对象、水文断面和地勘孔、堤防护岸、闸泵用户参数、导流度汛和观测；无水文地质不选尺寸或流量 | `scripts/test_design_specialties_drafts.py` |
| port（港航） | 泊位船型、水位波浪潮流、结构比选、前沿尺度、航道回旋水域、装卸堆场与水利接口；不计算桩长或靠船力 | `scripts/test_design_infrastructure_drafts.py` |
| municipal（市政道路） | 路段桩号、平纵横断、路面结构、排水标高、管线权属及导改接口；不拆算车道宽或选路面厚度 | `scripts/test_design_infrastructure_drafts.py` |
| bridge（桥梁） | 桥位跨径及桥型比较、上下部结构、支座桥面、水文通航抗震及施工接口；不锁最优桥型或计算钢束桩长 | `scripts/test_design_infrastructure_drafts.py` |
| tunnel（隧道） | 用途净空、工法地层、开挖支护、防水接缝、监控量测、洞口及机电防灾接口；支护参数和监测阈值待核 | `scripts/test_design_infrastructure_drafts.py` |
| traffic（交通工程） | 交通影响/施工导改任务、调查来源与独立情景、组织及标志信号、仿真资料和指标；未运行仿真或优化配时 | `scripts/test_design_infrastructure_drafts.py` |
| design-coord（设计统筹） | 图纸版本、会审问题、提资责任期限、变更记录、逐条决议和闭环证据；不代签发，不内置审批面积阈值 | `scripts/test_design_infrastructure_drafts.py` |

四组脚本覆盖给定/缺失数据、记录与辖区隔离、真实 Markdown/Excel，以及 chat 和高风险门控。本地 66 岗源码包已完成解压验收，内容与命令见 product-plan §11；本轮未发布 GitHub Release。

## 一句话口径（对外只说这句）

覆盖 16 大类 66 岗的 AI 工作台：**66 岗都能起草（L1 可复跑）、66 岗有专属写盘实现（L2 逐行对账与实测）、1 岗走全链路引擎并交出可复跑证据链（L3 pack-ship）**。宽度是路线图，深度是证据；缺数标 UNSPECIFIED 是特性不是未完成。
