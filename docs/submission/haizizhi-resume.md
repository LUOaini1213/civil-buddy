# 海之子杯申报 · 人机协同履历表（正式稿）

> 更新：2026-08-29 · 对应 [haizizhi-positioning.md](haizizhi-positioning.md) §d 骨架的填实版。
> 口径：只写有仓内证据（git 提交 / 可复跑命令）的事；纠偏点必须具体到"改了什么决策/补了什么洞"。
> 人 = 团队成员（方向决策、口径拍板、验收）；AI = 本仓多智能体开发流（子代理实现、审查、回归）。
> 截止 2026-08-31（海之子杯），工作区间 2026-07-24 起，git log 全程可查。

## 履历表

| 阶段（日期） | 人做什么 | AI 做什么 | 纠偏点 |
|--------------|----------|-----------|--------|
| ① 2026-07-24 ~ 08-13 引擎与评测体系搭建（git: `72c75d3`…`ebe5625`） | 人定比赛主口径——"表格进、真数字出"的出运作业单，并每日复盘评测分数、拍板当日刀口 | AI 搭 pack-ship 装箱引擎（体积/承重/混装/多柜策略）与评测闭环：fanout 16×8 共 128 次真实管线评测（`8da28d7`）、netopt 在线调参（`79ca776`、`ebe5625`） | booking 指标曾静默回退默值被体积审计揪出（`11e2eec` close P0/P1 booking-metric fallbacks）：人拍板"指标缺数不许回退默值，宁可标 TBD"，该纪律沿用至今（`[A001]`/UNSPECIFIED 的雏形） |
| ② 2026-08-17 workbench 合并与 66 岗重塑（`f69f085`、`3132975`） | 人拍板把独立仓 packing-agent 并入 monorepo，产品从"装箱工具"重塑为 16 大类 66 岗工作台 | AI 执行合并与重塑：66 岗统一 chat/run 双模 turn、UI 先判意图再写盘（`71ff0db`）、tender 交接（`a73ac6f`） | 合并后出现"投标问题也落盘写文件"的越权行为，人补纪律"chat 零写盘"并由 AI 修复（`0df9a63` fix: tender questions stay chat and write zero files）——意图与写盘从此分层 |
| ③ 2026-08-25 策略引擎与失败恢复四拍（`96684ea`、`83a2cb5`） | 人定"四拍剧本"验收口径：正常下单 → 越权被拒 → 工具挂掉自动恢复 → 成本超限熔断，每拍有预期输出 | AI 实现 Agent Middleware（permission/sandbox/HITL/audit/cost）与策略引擎深化，落地 `scripts/demo_agent_middleware.py` | 失败恢复最初只重试不留痕：人要求"retry 失败必须落 UNSPECIFIED 审计链"，AI 补齐审计字段后四拍才算过——恢复不能以丢证据为代价 |
| ④ 2026-08-28 敏感数据联网审计与两轮清洗 | 人发起全历史提交泄漏审计，圈定清洗范围，复核清洗后功能完好 | AI 全历史扫描识别发票 PDF 与客户衍生 xlsx，执行 filter-repo 两轮清洗，随后全量回归跑绿；仓内沉淀 local-only 政策（.gitignore 真实业务数据规则，现仓 PDF=0） | 第一轮清洗漏了 xlsx 派生文件，第二轮补刀；"清洗后回归全绿"成为验收标准——只删数据不验功能等于没洗 |
| ⑤ 2026-08-29 NL pack 断链发现与五处修复（`8226574`） | 人在彩排中发现"一句话 pack 入口"断链，拍板当天修复并纳入演示主路径 | AI 顺链定位五处断点（意图路由/工具注册/网关/前端回显/评测口径）逐一修复，端到端复跑出真数字作业单 | 彩排即纠偏：入口断了说明冒烟口径没覆盖 NL 入口——修完后把 `pack test/sim_materials/...` 写进 demo 脚本主路径，防二次断链 |
| ⑥ R1 2026-08-29 评委路径体检（`8817310`） | 人以评委视角走 5 分钟路径，发现文档承诺的 main.py 入口与实际不一致 | AI 修复演示入口不一致，并把"文档每条命令必须实跑"固化为材料门禁 | 纠偏点：文档不是写完就算——"可复跑"从口头承诺变成验收动作，本轮（R5）复核 R1-R4 全部命令仍逐条实跑通过 |
| ⑦ R2 2026-08-29 官方章程核对与两赛口径拆分（`ec94c19`） | 人逐条读官方章程与 API 页，核对提交物四件、评审三维度原文，拍板两赛分别陈述 | AI 拆分两赛口径、落 66 岗分级诚实披露（L1 知识库 66/66、L2 工具写盘 36/66、L3 全链路引擎岗 1），起草申报定位文档 | AI 初稿把"路线图宽度"写成"已交付深度"：人按章程口径砍掉越界声明，改为"宽度是路线图，深度是可复跑证据"的分级表述 |
| ⑧ R3 2026-08-29 CI 三连败根因与 parity 守卫（`175b812`） | 人追 CI 连续三次红的三类根因（工作目录/依赖缺失/断言过期），定"守卫优先于修复"原则 | AI 落三栈 parity 守卫：understand.py==agent.rs 行为对齐、SKILL.md 三镜像（.agents/.codex/generator）、66 岗名册对账，并加提示词注入自检 | 纠偏点：不许"把断言改绿了事"——每类漂移必须变成防再发守卫；同根因二次出现视为守卫失效 |
| ⑨ R4 2026-08-29 意图契约单源化（`cd49632`） | 人拍板意图词表唯一真源 = `contract/intents.v1.json`，Python/Rust 双栈只读不存副本 | AI 完成双栈读取改造 + 行为金句双向守护：`test/eval/intents_golden.json` 同时被 Python（test_stack_parity 实跑）与 Rust（cargo test intents_golden 实跑）断言 | 契约加载禁止静默回退内联旧词表——文件缺失/损坏一律 fail-fast；金句漂移必须"先确认新行为是想要的，再同步金句并说明" |
| ⑩ R5 2026-08-29 每岗记分卡试点（本轮） | 人定四门禁口径（G1 意图命中/G2 KB 检索/G3 交付物 schema/G4 诚实度）并挑 5 个试点岗：bid-parse、bid-compliance、bid-tech、cost、safety-brief | AI 实现 `scripts/eval_post_scorecard.py`：5 岗 × 4 门禁全 PASS（全离线零 Key），行为金句扩至 41 条且 Python/Rust 双侧全绿，记分卡登记进 precommit | 联网终评发现 CI 红根因是 whatif 断言随 66 岗重塑过期（`team_mode` 已从 single_closed_loop 统一为 big_team_a_b）：按"断言同步引擎现实"修复，而不是回滚引擎或放松成永真 |

## 纠偏机制小结（对外一句话）

人管"口径与边界"（做什么、不做什么、数字从哪来），AI 管"实现与回归"；每次纠偏必须沉淀成守卫或纪律（评测断言、parity 守卫、金句冻结、precommit 登记），使同类错误不可二次发生——履历表中每一行"纠偏点"都对应仓内一条仍在生效的机制。

## 复跑方式

| 阶段 | 复跑命令 / 证据 |
|------|-----------------|
| ① 引擎与评测 | `python scripts/eval_competition_scorecard.py --skip-phase0`（综合分 8.85 门禁） |
| ② 66 岗重塑 | `python scripts/test_kb_k4_depth.py`（66/66）；Rust 侧 `cargo test --release`（workbench） |
| ③ 四拍剧本 | `python scripts/demo_agent_middleware.py` |
| ④ 数据清洗 | `git ls-files | grep -icE '\.pdf$'` → 0；`.gitignore` local-only 规则 |
| ⑤⑥ NL pack 与演示路径 | `python scripts/demo_one_shot.py` → ALL PASS；`python main.py --demo` |
| ⑦⑧⑨ 口径/parity/契约 | `python scripts/test_stack_parity.py`（41 金句实跑）；`cargo test --release --test intents_golden`（Rust 同份金句） |
| ⑩ 每岗记分卡 | `python scripts/eval_post_scorecard.py --all-pilots` → 5/5 PASS；产物 `output/posts/<岗>.json` |
