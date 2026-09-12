# 岗位 Skill 与工具能力核对

2026-09-12，以当前 Python 工作台源码及只读运行时探针为准。

结论：66 岗都有不同的 Skill 和岗位工具绑定，当前足够做资料整理、专用文书起草与下载；距离能自主完成工程计算和外部操作的土木工作台，仍缺模型调度接线、可靠参数契约及专业执行工具。

## Skill 的差异有多深

- 66 个岗位 ID 均有 SKILL.md，正文散列也各不相同；`.agents` 和 `.codex` 镜像一致。
- 差异来自职责、触发词、交付物、专属工具、知识库、风险及骨架。它们共用生成模板和相同的阶段工序；16 岗有额外专段，50 岗采用岗位 outline 的前 10 个非空行。因此“不同 Skill”不代表已有 66 套深入独立的决策策略。
- 模型问答确实加载所选 Skill 全文，且仅加载该岗：`demo/chat_service.py:_model_chat` → `demo/agent.py:build_expert_prompt` → `runtime/expert_skills.py:prompt_suffix`。
- 隐式选择是词匹配，尚不是完整语义路由：普通短标签少于 4 字不自动命中，例如“帮我写日报”未命中，而“帮我写项目日报”或“@日报”可命中。明确选岗或使用 @岗位名更可靠。
- 离线文书由岗位 Python 起草器生成。`skill_sop_loaded` 只是存在性标记，不能证明模型按该 SOP 自主规划或执行了工具。
- 本次修正了危大识别专段残留的“SG 默认”：现要求明确 SG/DUAL 才采用该分栏，辖区未知保持 UNSPECIFIED。已重新生成两套技能镜像，并通过技能及双栈一致性检查。

## 现在的工具偏好如何生效

`workbench/yibiao-map.json` 定义各岗 exclusive 工具；`runtime/agent_loop.py:_plan_calls` 决定实际顺序。普通岗位选择首个已注册主工具，施工的填模板步骤单独处理；招标解析走 `tender.parse`；装箱固定 health → list → plan → export。当前主链没有可学习的偏好权重，也不会因为编辑 Skill 中的工具排序就自动改变代码的调用顺序。

工作台 `/api/chat` 的两条主分支不同：问答先检索知识库，再调用不带工具列表的模型文本流；成稿调用本地 `run_agent`，模式固定 `steps`。因此配置模型 Key 不会自动把所有岗位升级为自主 tool calling。旧 `demo/agent.py:run_expert` 和装箱实验调度属于另一些入口，不能作为当前页面已启用的证据。

## 工具数量与实际执行能力

| 口径 | 实测结果 | 解释 |
|---|---|---|
| 当前 ToolEngine | 74 个，70 个岗位绑定、4 个公共 | 64 岗各 1 个 exclusive，施工 2 个，装箱 4 个；无声明但未注册的岗位工具 |
| 岗位工具实现 | 66 个起草/检查/填表入口，4 个装箱快照操作 | 专属名称不等于独立计算算法；多数复用岗位分派入口 |
| 公共运行时工具 | tender.parse、tender.review、write_deliverable、spawn_helper | 最后一个只做沙箱判断，返回 spawned=false，不执行 shell |
| 按岗 MCP 工具并集 | 93 个名称 | 这是另一个暴露口径，不能与 74 相加；当前这些定义的 inputSchema.properties 全为空 |
| 运行时参数验证 | 仅 write_deliverable 声明必填 path | 其余 73 个无 schema_keys；内部处理器可能另做校验，但尚无完整统一的类型、单位、范围和必填字段契约 |
| 装箱子系统工具目录 | 39 条能力描述 | 包括真实成箱、柜数和三维装载代码，属于另一条执行链，不能视为当前工作台均已接通 |

仓库有真实装箱计算器，但当前工作台的 pack-ship 工具主要投影已有 solver 快照；缺连接时保持 UNSPECIFIED，健康接口声明 packing=false。包装箱结构校核也不能当作建筑主体结构求解器。

## 哪些够用，哪些还缺

| 目标 | 当前判断 | 需要补的实际能力 |
|---|---|---|
| 日报、行政、人力、资料、专业提纲 | 可进行内部起草试用 | 复杂输入的抽取质量、真实业务样本评价和逐岗 SOP 深度仍可继续提高 |
| 由模型自主选择并连续执行工具 | 未形成当前工作台主链 | 统一工具目录与完整 JSON Schema；岗位前置条件、必需/可选步骤、校验器、失败恢复及模型调度接线 |
| 工作台内直接完成装箱计算 | 计算代码已有，当前入口未直连 | 把求解调用、参数校验、结果快照及证据链接到同一任务 |
| 工程量、报价与进度计算 | 文书能力，计算不足 | 来源可追踪的数量/单位/金额计算、网络计划关键路径和资源计算 |
| BIM 与专业设计 | 能整理资料，不能替代专业计算 | IFC 几何读取/算量/碰撞工具，以及各专业的求解器或已授权软件接口 |
| 扫描件及复杂工程资料 | 现有文本 PDF/Office 可读 | OCR、图纸/复杂表格的结构识别和可核对的来源定位 |

优先顺序：先补已有工具的参数和结果契约、接通当前宿主，再接已有装箱引擎；随后按真实业务需求增加少量可复用的计算工具。每岗应定义自己的调用条件与验证规则，不必给每岗复制一整套文件读写、表格计算工具。

来源：`packing_assistant/expert_roster.py`、`runtime/expert_skills.py`、`runtime/agent_loop.py`、`runtime/tool_engine.py`、`demo/chat_service.py`、`demo/mcp_surface.py`、`scripts/build_codex_expert_skills.py`。逐岗只读快照：`output/skill-tool-audit-2026-09-12.json`。本次未调用联网模型、未执行专业工程计算，判断没有把文件数量或模板出稿测试当作计算能力证据。

## 逐岗映射

以下为当前默认成稿计划，不代表每轮必须执行；纯问答、缺确认、只读与取消会改变是否执行。

| 岗位 | ID | Skill 专段 | 声明专属工具 | 默认计划 |
|---|---|---|---|---|
| 招标解析 | bid-parse | SPECIAL | `bid-parse__extract` | `tender.parse` |
| 废标检查 | bid-compliance | SPECIAL | `bid-compliance__gaps` | `bid-compliance__gaps` |
| 技术标 | bid-tech | SPECIAL | `bid-tech__expand` | `bid-tech__expand` |
| 建筑 | architecture | outline excerpt | `architecture__memo` | `architecture__memo` |
| 结构 | structure | SPECIAL | `structure__calc_outline` | `structure__calc_outline` |
| 岩土勘察 | geotech | SPECIAL | `geotech__brief` | `geotech__brief` |
| 给排水 | plumbing | outline excerpt | `plumbing__memo` | `plumbing__memo` |
| 暖通 | hvac | outline excerpt | `hvac__memo` | `hvac__memo` |
| 电气 | electrical | outline excerpt | `electrical__memo` | `electrical__memo` |
| 消防 | fire-protect | outline excerpt | `fire-protect__brief` | `fire-protect__brief` |
| 钢结构 | steel | outline excerpt | `steel__memo` | `steel__memo` |
| 园林景观 | landscape | outline excerpt | `landscape__memo` | `landscape__memo` |
| 室内装修 | interior | outline excerpt | `interior__schedule` | `interior__schedule` |
| 幕墙 | facade | SPECIAL | `facade__brief` | `facade__brief` |
| 智能化弱电 | intel-weak | outline excerpt | `intel-weak__memo` | `intel-weak__memo` |
| 人防 | civil-defense | outline excerpt | `civil-defense__brief` | `civil-defense__brief` |
| 水利 | hydraulic | outline excerpt | `hydraulic__outline` | `hydraulic__outline` |
| 港航 | port | outline excerpt | `port__outline` | `port__outline` |
| 市政道路 | municipal | outline excerpt | `municipal__memo` | `municipal__memo` |
| 桥梁 | bridge | outline excerpt | `bridge__outline` | `bridge__outline` |
| 隧道 | tunnel | outline excerpt | `tunnel__outline` | `tunnel__outline` |
| 交通工程 | traffic | outline excerpt | `traffic__skeleton` | `traffic__skeleton` |
| 设计统筹 | design-coord | outline excerpt | `design-coord__minutes` | `design-coord__minutes` |
| 模型协调 | bim-coord | outline excerpt | `bim-coord__clash` | `bim-coord__clash` |
| 模型算量 | bim-qto | outline excerpt | `bim-qto__rules` | `bim-qto__rules` |
| 模型交付 | bim-deliver | outline excerpt | `bim-deliver__lod` | `bim-deliver__lod` |
| 总控计划 | plan-master | outline excerpt | `plan-master__network` | `plan-master__network` |
| 周月计划 | plan-lookahead | outline excerpt | `plan-lookahead__week` | `plan-lookahead__week` |
| 资源负荷 | plan-resource | outline excerpt | `plan-resource__peak` | `plan-resource__peak` |
| 施工方案 | construction | SPECIAL | `construction__scheme_draft` / `construction__fill_scheme_docx` | `construction__scheme_draft` |
| 危大识别 | method-hazard | SPECIAL | `method-hazard__judge_hazard` | `method-hazard__judge_hazard` |
| 测量 | survey | SPECIAL | `survey__record` | `survey__record` |
| 生产调度 | dispatch | outline excerpt | `dispatch__daily` | `dispatch__daily` |
| 安全交底 | safety-brief | SPECIAL | `safety-brief__talk` | `safety-brief__talk` |
| 质量 | quality | SPECIAL | `quality__lot` | `quality__lot` |
| 环保文明 | env | outline excerpt | `env__list` | `env__list` |
| 应急 | emergency | outline excerpt | `emergency__plan` | `emergency__plan` |
| 造价 | cost | SPECIAL | `cost__takeoff` | `cost__takeoff` |
| 变更签证 | variation | outline excerpt | `variation__form` | `variation__form` |
| 索赔调概 | claim | outline excerpt | `claim__notice` | `claim__notice` |
| 分包结算 | subcontract | outline excerpt | `subcontract__sheet` | `subcontract__sheet` |
| 验工计价 | interim | outline excerpt | `interim__measure` | `interim__measure` |
| 采购计划 | proc-plan | outline excerpt | `proc-plan__schedule` | `proc-plan__schedule` |
| 比价询价 | proc-compare | outline excerpt | `proc-compare__table` | `proc-compare__table` |
| 供应商 | proc-vendor | outline excerpt | `proc-vendor__eval` | `proc-vendor__eval` |
| 设备管理 | equip | outline excerpt | `equip__ledger` | `equip__ledger` |
| 仓管 | warehouse | outline excerpt | `warehouse__log` | `warehouse__log` |
| 装箱拼柜 | pack-ship | SPECIAL | `pack-ship__list` / `pack-ship__plan` / `pack-ship__export` / `pack-ship__health` | `pack-ship__health` → `pack-ship__list` → `pack-ship__plan` → `pack-ship__export` |
| 现场材料 | material-site | outline excerpt | `material-site__recon` | `material-site__recon` |
| 配合比 | lab-mix | outline excerpt | `lab-mix__report` | `lab-mix__report` |
| 见证取样 | lab-sample | outline excerpt | `lab-sample__list` | `lab-sample__list` |
| 试验台账 | lab-record | outline excerpt | `lab-record__ledger` | `lab-record__ledger` |
| 核算 | finance-book | outline excerpt | `finance-book__check` | `finance-book__check` |
| 资金 | finance-fund | outline excerpt | `finance-fund__plan` | `finance-fund__plan` |
| 税务 | finance-tax | SPECIAL | `finance-tax__calendar` | `finance-tax__calendar` |
| 资料监理 | supervision | SPECIAL | `supervision__reply` | `supervision__reply` |
| 招聘 | hr-recruit | outline excerpt | `hr-recruit__brief` | `hr-recruit__brief` |
| 劳动关系 | hr-labor | outline excerpt | `hr-labor__check` | `hr-labor__check` |
| 培训 | hr-train | outline excerpt | `hr-train__plan` | `hr-train__plan` |
| 公文印章 | admin-doc | outline excerpt | `admin-doc__draft` | `admin-doc__draft` |
| 会务后勤 | admin-office | outline excerpt | `admin-office__list` | `admin-office__list` |
| 运维权限 | it-ops | outline excerpt | `it-ops__runbook` | `it-ops__runbook` |
| 数据备份 | it-data | outline excerpt | `it-data__backup` | `it-data__backup` |
| 系统需求 | it-app | outline excerpt | `it-app__srs` | `it-app__srs` |
| 工友白话 | worker-brief | SPECIAL | `worker-brief__talk` | `worker-brief__talk` |
| 项目日报 | pm-daily | outline excerpt | `pm-daily__log` | `pm-daily__log` |
