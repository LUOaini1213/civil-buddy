# 海之子杯申报 · 定位陈述与证据包（Civil Buddy）

> 更新：2026-08-29（R5 补每岗记分卡证据、履历表正式稿）· 服务 [knowledge_base/06_competition/constraints-hzzb.md](../../knowledge_base/06_competition/constraints-hzzb.md) 的提交物四件。
> 官方章程：<https://aicampus.3311csci.com/rules.html>（以官方页为准）。评审三维度官方原文见 constraints-hzzb.md。
> 所有"可复跑命令"均在本仓根目录实际执行验证过；冻结数字口径见 [docs/competition-demo-script.md](../competition-demo-script.md)。

## a) 一段话定位陈述

**Civil Buddy 是面向土木企业的"土木版 Codex"**：覆盖 16 大类 66 个岗位的 AI 工作台，每岗以"程序记忆（SOP）+ 岗位知识库 + 独有工具"起草内部交付物；策略引擎与失败恢复两层中间件护航；铁律 **"tools compute numbers; the model only routes"**——数字只由工具算，模型只做路由与组织语言。

本次提交展示一条**深度证据链**：从招标解析、废标检查、技术标目录，到集装箱装柜出运（446t 单票对照 **29→25 柜**、mid50 **59.4%**、对外校准综合分 **8.85**），以及一张诚实的 **66 岗分级地图**（L1 知识库草稿 66/66、L2 工具写盘 36/66、L3 全链路引擎岗 1——pack-ship）。宽度是路线图，深度是可复跑证据；**缺数标 UNSPECIFIED 是产品特性，不是未完成**。

**红线（产品设计与本申报共同的边界）**：不出签认件、不自动判定可投标、不承诺中标率、不代交任何官方系统。P0 资格/★/废标项与人身安全相关写盘一律人工确认（HITL），未确认时 `submit_blocked=true`。

## b) 三维度证据→命令映射

### 维度一：场景创意价值（真实痛点 + 落地可行 + 产业推广价值）

| 官方考察点 | 证据 | 可复跑命令 / 入口 |
|------------|------|--------------------|
| 真实痛点：土木企业 66 类岗位日常起草工作靠人肉重复 | 66 岗工作台：每岗"程序记忆（SOP）+ 知识库 + 独有工具"起草内部交付物（方案提纲、交底、台账、报价栏……缺数标 `[A001]`/`UNSPECIFIED`） | `python scripts/test_kb_k4_depth.py`（66/66 岗知识库深度闸） |
| 真实痛点：装柜出运凭经验拍柜数、拍坐标 | pack-ship 引擎岗：NL 一句话 `pack <表>` → 引擎出真数字作业单（柜数/坐标是 tools 输出） | 启动 `python scripts/demo_one_shot.py` 后在 :8765 工作台输入 `pack test/sim_materials/small_one_container/materials.xlsx` |
| 落地可行：不依赖云、自带 Key、免编译冒烟 | 冒烟无需 API Key；工作台 exe 可从 GitHub Releases 下载试用 | `python scripts/demo_one_shot.py` → ALL_PASS |
| 产业推广价值：16 大类车道覆盖投标→生产→商务→后勤全链条 | 16 车道分级表与富化批次（T030–T039 滚动推进） | [docs/depth-ladder.md](../depth-ladder.md)（每行挂验收） |

### 维度二：AI 协同能力（人机协同规划 + AI 交互迭代 + AI 纠偏）

| 官方考察点 | 证据 | 可复跑命令 / 入口 |
|------------|------|--------------------|
| 人机协同规划：HITL 高风险写盘前人确认 | 高风险岗未确认 0 稿；确认句"我明白，将由持证人员签认"；成箱→HITL→拼柜 | `python scripts/demo_agent_middleware.py`（第三拍含 HITL）；`http://127.0.0.1:8000/workbench` |
| AI 交互迭代：一句话自然语言入口 + 意图路由（chat/run/both） | NL→IntentSpec→白名单 tools；无 Key 时 policy fallback 功能不哑；每岗金句冻结（41 条）Python/Rust 双侧实跑守护 | :8765 输入 `pack test/sim_materials/small_one_container/materials.xlsx`；`python main.py --eval`（phase0 quick 12/12）；`python scripts/test_stack_parity.py` |
| AI 纠偏管理：策略引擎（越权拒绝弹原因）+ 失败恢复（retry→`UNSPECIFIED` 审计链）+ 成本熔断 | Agent Middleware 四拍剧本：正常下单 → 越权被拒 → 工具挂掉自动恢复 → 成本超限熔断 | `python scripts/demo_agent_middleware.py` |
| 纠偏落到成稿：缺数不编造 | safety-brief 成稿 11 栏中毫米/电话为 `[A001]` 待填；各岗 TBD/UNSPECIFIED | `grep -n "A001" demo/kb/hse/safety-brief/outline.md`；或在 :8765 召唤安全交底专家看成稿待填栏 |

### 维度三：技术创新能力（创新构思 + 技术应用 + 工具整合 + 完成度）

| 官方考察点 | 证据 | 可复跑命令 / 入口 |
|------------|------|--------------------|
| 创新构思：土木版 Codex（IDE 隐喻搬进土木企业） | 技能一岗一份 `.agents/skills/<id>/SKILL.md`；任务选用 SOP；沙箱写盘 | `python -m packing_assistant.civil`（TUI）· `ide/README.md` |
| 技术应用：NL→IntentSpec→确定性流水线（`agent_mode=steps`）→影子评测 | 引擎正例过 30 项结构校核；负例 `--preset structure_fail` 证明合规门是活的（REJECT=门生效） | `python main.py --demo` · `python main.py --demo --preset structure_fail` |
| 工具整合：Rust 工作台 + Python 引擎 + MCP + KB 检索 + 前端 3D/CoG | 一个仓库三入口（:8765 工作台 / :8000 主线 C / TUI）；MCP stdio 工具表 | `npm run check`；`python scripts/test_mcp_stdio.py` |
| 完成度：诚实分级 + 评测口径不注水 | L1 66/66、L2 36/66、L3 1；446t 单票对照 29→25 柜（mid50 0.594）；对外校准综合分 8.85（不报 10.0） | `python scripts/eval_competition_scorecard.py --skip-phase0`；大票对照 `python scripts/compare_446t_agent_vs_tool.py --full-agent`（依赖本地业务数据 `output/cases_446t/materials.json`，不进仓；冻结数字以 [docs/competition-evidence-one-pager.md](../competition-evidence-one-pager.md) 为准，不现场重跑） |
| 完成度：每岗质量门禁可抽样复跑（R5） | 每岗记分卡四门禁（意图命中/KB 检索/交付物 schema/诚实度），试点 5 岗全 PASS、全离线零 Key | `python scripts/eval_post_scorecard.py --all-pilots`（产物 `output/posts/<岗>.json`） |

## c) 视频脚本表（3 分钟，单屏录制成片）

| 时间 | 画面 | 口播要点 | 操作 |
|------|------|----------|------|
| 0:00–0:15 | 工作台 66 岗目录/热力图一闪而过 | "土木版 Codex：16 大类 66 岗；数字只由工具算，模型只路由。" | 打开 :8765 工作台首页扫一圈 |
| 0:15–1:35 | pack-ship 闭环 + 纠偏一拍 | "一句话装柜：表格进、真数字出；柜数坐标是引擎算的。" 插一拍纠偏：改错表让引擎拒绝并给原因 | 聊天框输入 `pack test/sim_materials/small_one_container/materials.xlsx` → 出装箱作业单；随后给一份故意超载的表，展示引擎拒绝/拆箱提示 |
| 1:35–2:20 | 主线 C 投标应答 + 交付 | "招标文本进来，条款级响应矩阵出去；装柜 tools 就是交付证据；资质栏留给人。" | POST `/api/tender/delivery`（`http://127.0.0.1:8000`），展示矩阵 → handoff 三列 → 交付页 `submit_blocked=true` |
| 2:20–2:45 | 纠偏专场 | "策略引擎+失败恢复两层中间件：越权拒、挂了恢复、超限熔断；成稿缺数标 [A001] 不编数。" | `python scripts/demo_agent_middleware.py` 四拍剧本；切 safety-brief 成稿放大 `[A001]` 待填栏 |
| 2:45–3:00 | 红线收口 | "不出签认件、不自动判定可投标；人确认之前，submit_blocked=true。" | 定格 `/api/tender/delivery` 应答中 `submit_blocked: true` 字样，黑屏出仓库名 |

录制注意：先跑通 `python scripts/demo_one_shot.py` 与 :8000 网关再开录；NL pack 与纠偏各留一条备选镜头；口播禁句见 [docs/competition-demo-script.md](../competition-demo-script.md)「不说的话」。

## d) 人机协同履历表

> 官方提交物第四件。**正式稿见 [haizizhi-resume.md](haizizhi-resume.md)**（10 行真实素材，2026-07-24 ~ 08-29，每行挂 git 证据与具体纠偏点）。下表保留最早的三行素材：

| 阶段（日期） | 人做什么 | AI 做什么 | 纠偏点 |
|--------------|----------|-----------|--------|
| 2026-08-28 泄漏审计 | 人发起历史提交泄漏审计，决定清洗范围并复核结果 | 脚本执行 filter-repo 历史清洗，随后全量回归测试跑绿 | 泄漏在合入前被审计拦截；清洗后以回归全绿证明功能未受损 |
| 2026-08-29 NL pack 断链 | 人在彩排中发现一句话 pack 入口断链，拍板修复优先级 | 定位断链五处并逐一修复，端到端复跑出真数字 | 彩排即纠偏：入口断了说明集成测试没覆盖到，补进冒烟口径 |
| 规划书每章复查 | 人定各章口径与"明确不做"边界 | 子代理逐章复查 product-plan，列出内部错误清单 | 人复核后改口（product-plan §14"规划书审阅发现必须改口"），机器不改总判 |

## e) 提交前待办勾选清单

- [ ] **报名**：队长在活动官网 <https://aicampus.3311csci.com> 完成报名（截止 2026-08-31）
- [ ] **组队**：确认每队 ≤4 人、队员学籍信息齐全（海内外全日制在校生）
- [ ] **学籍/身份材料**：按官网要求准备在校证明或学生证材料
- [ ] **视频录制**：按上表 3 分钟脚本录制，≤2 分钟候选备选剪辑各一条，核对官方时长/格式限制
- [ ] **技术说明文档**：以本文定位陈述 + 三维度映射表为底稿成文，补团队信息
- [ ] **人机协同履历表**：正式稿已成（[haizizhi-resume.md](haizizhi-resume.md)，10 行带 git 证据），按官方模板格式导出
- [ ] **格式核对**：四件套（智能体链接或代码包 / 技术说明 / 视频 / 履历表）命名、大小、附件格式逐项对照官方页
- [ ] **提交前全绿复跑**：`python scripts/test_kb_k4_depth.py` · `python scripts/demo_one_shot.py` · `python scripts/eval_competition_scorecard.py --skip-phase0` · `python scripts/eval_post_scorecard.py --all-pilots` 四连，退出码全 0
- [ ] **红线自查**：全文检索禁句（中标率 / 可以投标 / 可以开工 / 代交官方系统），P0 字样必须连着"须人确认"
