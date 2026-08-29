# 66 岗深度分级（Depth Ladder · 对人诚实）

> 更新：2026-08-29（R5 补记分卡抽样验收）· 依据 [product-plan.md](civil-buddy/product-plan.md) §3.2 / §6 / §7.2。
> **铁律：广度以"路线图"形态出现，深度以"可复跑证据"形态出现。** 本页每一条深度声明都挂验收文件或可复跑命令；不确定的岗宁可标低不标高。

## 三级阶梯

| 级 | 定义 | 覆盖 | 验收（可复跑） |
|----|------|------|----------------|
| **L1 KB 草稿岗** | 每岗四件套：faq≥5 + README 字段表 + outline 缺数栏 + `search_kb` 命中本岗（且不见兄弟岗私库） | **66/66** | `python scripts/test_kb_k4_depth.py` → `PASS kb_k4_depth experts=66 faq5=66 fields=66 gaps=66 search_hit=66` |
| **L2 工具写盘岗** | 该岗有自己的成稿栏位/写盘函数（非通用 `_draft_markdown` 骨架句） | **36/66** | 依据 product-plan §3.2/§7.2 逐行 ✅ 状态（约 30 岗为 T030–T039 批次富化，行业评测复核滚动进行）；抽样函数证据见下 |
| **L3 引擎岗** | 硬数字走本仓引擎：NL→IntentSpec→白名单 tools→HITL→影子评测 | **1**（pack-ship） | `python scripts/demo_one_shot.py` → ALL_PASS；`python scripts/eval_competition_scorecard.py --skip-phase0` → 综合分 **8.85**（本地校准、对外口径）门禁全 PASS |

**L3 pack-ship 证据链（冻结口径，演示日不现场重跑大票对照）：**

- 446t 单票对照 **29→25 柜**：`python scripts/compare_446t_agent_vs_tool.py --full-agent`（旧基线 29 已废弃，现行全 Agent 25×40HQ，`phase=done / risk=WARN / ship_ok=true`）。**注意**：该命令依赖本地业务数据 `output/cases_446t/materials.json`（客户衍生清单，按本仓 local-only 政策不进仓），净仓环境跑不了属预期；冻结数字以 [docs/competition-evidence-one-pager.md](competition-evidence-one-pager.md) 存档记录为准，演示/评审不现场重跑
- **mid50 0.594**：同一对照产物，贴 CTU 严格偏好 60% 线，风险 WARN；少柜 light 路径 mid≈0.17 仅参考、不作出运结论
- 综合分 **8.85**：本地校准评分卡，phase0 quick（n=12，pass_rate 1.0）封顶口径，**不报 10.0**

**UNSPECIFIED 是特性，不是未完成。** 每岗成稿缺数处一律写 `[A001]` / `UNSPECIFIED` / `TBD`，不编造数字、不冒充签认件——这是产品纪律（tools compute numbers; the model only routes）的直接体现，也是 L1 验收闸（gaps=66）的一部分。

**R5 每岗记分卡抽样（L2 附加验收）**：`python scripts/eval_post_scorecard.py --all-pilots` 对 5 个试点岗（bid-parse / bid-compliance / bid-tech / cost / safety-brief，覆盖 bid/commercial/hse 三大类）跑四门禁——G1 意图命中（金句 intent+skill）、G2 KB 检索命中私有库、G3 exclusive 工具离线产出覆盖 README 字段表必需栏、G4 缺数空态保留 `[A001]`/UNSPECIFIED 且 `forbidden_hits==0`。当前 5/5 全 PASS；该脚本已登记 precommit（quick 预算跑 2 岗）。

## 16 车道 × L1/L2/L3 分级表

数据提取自 product-plan §6（车道/岗数）与 §7.2（逐岗 ✅ 状态，该表为唯一状态权威）；§6「现网富化」列的 1/4、0/5 等为 2026-08-19 快照、已被 §7.2 的 T030–T039 批次覆盖，以 §7.2 为准。车道间不确定处已按"宁可标低"处理（如 hr 车道另两岗仍按骨架计）。

| # | 车道 | 大类 | 岗数 | L1 | L2 | L3 | 已富化岗（写盘） | 验收 |
|---|------|------|------|----|----|----|------------------|------|
| 1 | `lane-bid` | 经营投标 | 3 | 3 | 3 | 0 | bid-parse / bid-compliance / bid-tech（handoff 三列 + 评分点目录） | `python scripts/test_tender_handoff.py` |
| 2 | `lane-design` | 勘察设计 | 20 | 20 | 0 | 0 | —（骨架；条款 UNSPECIFIED、DUAL 分栏是设计目标） | `python scripts/test_kb_k4_depth.py`（L1 闸） |
| 3 | `lane-bim` | BIM | 3 | 3 | 0 | 0 | —（不假装 IFC 全量抽量） | 同上 |
| 4 | `lane-planning` | 计划 | 3 | 3 | 3 | 0 | plan-master / plan-lookahead / plan-resource（T032） | product-plan §7.2 行 12–14 |
| 5 | `lane-construction` | 施工生产 | 4 | 4 | 4 | 0 | construction（十一章 + fill_scheme/`docx_pending`）、method-hazard（判定书）、survey / dispatch（T030） | `python scripts/test_construction_skill_path.py` |
| 6 | `lane-hse` | 安质环 | 4 | 4 | 4 | 0 | safety-brief（11 栏，毫米/电话 `[A001]`）/ quality / env / emergency（T035） | product-plan §7.2 行 19–22 |
| 7 | `lane-commercial` | 商务造价 | 5 | 5 | 5 | 0 | cost（takeoff，无单价 UNSPECIFIED）/ variation / claim / subcontract / interim（T031） | product-plan §7.2 行 5、8–11 |
| 8 | `lane-procurement` | 采购 | 3 | 3 | 3 | 0 | proc-plan / proc-compare / proc-vendor（T037） | product-plan §7.2 行 26–28 |
| 9 | `lane-plant` | 物机 | 4 | 4 | 4 | **1** | pack-ship（引擎岗）+ equip / warehouse / material-site（T036） | `python scripts/demo_one_shot.py` + `python scripts/eval_competition_scorecard.py --skip-phase0` |
| 10 | `lane-lab` | 试验室 | 3 | 3 | 3 | 0 | lab-mix / lab-sample / lab-record（T033） | product-plan §7.2 行 15–17 |
| 11 | `lane-finance` | 财务 | 3 | 3 | 3 | 0 | finance-tax（日历页述 9%、申报期空栏）/ finance-book / finance-fund（T038） | product-plan §7.2 行 6、29–30 |
| 12 | `lane-docs` | 资料监理 | 1 | 1 | 1 | 0 | supervision（T034） | product-plan §7.2 行 18 |
| 13 | `lane-hr` | 人力 | 3 | 3 | 1 | 0 | hr-recruit（专属 `_hr_recruit_md`，`packing_assistant/expert_turn.py`）；另两岗骨架 | product-plan §6 现网富化 1/3 + 函数证据 |
| 14 | `lane-admin` | 行政 | 2 | 2 | 0 | 0 | —（不自动盖章） | `python scripts/test_kb_k4_depth.py`（L1 闸） |
| 15 | `lane-it` | IT | 3 | 3 | 0 | 0 | —（禁止密钥进稿） | 同上 |
| 16 | `lane-people` | 项目与工人 | 2 | 2 | 2 | 0 | worker-brief（三段口播，无尺寸不报毫米）/ pm-daily（T039） | product-plan §7.2 行 31–32 |
| — | **合计** | | **66** | **66** | **36** | **1** | | |

> 抽样代码证据（"L2 = 有专属写盘函数，不是通用骨架"）：`grep -n "def _hr_recruit_md\|def _safety_brief_md\|def _plan_master_md" packing_assistant/expert_turn.py`。
> 其余 ~30 岗（设计 20 + BIM 3 + 行政 2 + IT 3 + hr 另 2 等）仍在 `_draft_markdown` 骨架，下一刀见 product-plan §15 D. 车道批次——**已富岗勿再当缺口，骨架岗勿吹成已富**。

## 一句话口径（对外只说这句）

覆盖 16 大类 66 岗的 AI 工作台：**66 岗都能起草（L1 可复跑）、36 岗有专属写盘栏位（L2 逐行对账）、1 岗走全链路引擎并交出可复跑证据链（L3 pack-ship）**。宽度是路线图，深度是证据；缺数标 UNSPECIFIED 是特性不是未完成。
