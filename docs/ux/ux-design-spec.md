# Civil Buddy UX 设计规范（ux round1 定稿）

> 本轮（ux round1）为后续 12 轮 UX 迭代立规矩：定公理、定 token、定语言、定路线。
> 本轮只加文档与 `:root{}` 变量块，**不改任何布局与现有样式**。
> 红线：中建内网运行 → **任何界面零 CDN、零外链资源**（已全量盘点通过，见附录 A）。

## 1. 设计公理

项目即"Civil Buddy = 土木版 Codex"，原则 **tools compute numbers; the model only routes**。四条公理：

1. **一个输入框**（借 Codex 简洁）：所有任务从同一个 composer 进入——自然语言、`/`指令、`@`文件、追问改方案同框；不做多入口分叉。
2. **一条流水线**（进度可见）：tools 算数字、模型只路由；流水线每个阶段（解析→组队→装柜→复核）在事件流上可见、可计时、可回放。
3. **一份正式交付物**（中建专业）：产出是可签认的文书（装柜单/作业单/交底/方案），带免责声明与签认栏，"内部讨论草稿 · 不是签认件"必须常驻。
4. **一道审批门**（HITL 合规）：`submit_blocked` 默认阻断；审批必须**显式决策**（确认/驳回），**Esc/关闭/刷新 ≠ 放行**；P0 资格、★、废标项一律"须人确认"。

### 三态交互模式（借自 Codex CLI TUI，pattern-only）

| 态 | Codex 做法 | Civil Buddy 落法 |
| --- | --- | --- |
| 普通提示 | 单一 composer，slash 弹窗、@ 文件搜索、粘贴预览、历史回溯都在这一个框里 | index/workbench/:8765 三端统一"一个输入框"；R2 输入轮、R9 指令面板轮落地 |
| 审批请求 | `approval_overlay.rs`：动作特定选项（accept/reject/always）+ 每次选择都发**显式决策事件**；Esc 映射为 Cancel，永不静默变成"继续" | R5 审批卡轮：审批卡按钮=动作特定（确认提交/驳回重做/补参数），决策写审计；关闭卡片=驳回 |
| 输出呈现 | `history_cell` 追加式会话流：turn、diff、exec 输出都是不可变历史 cell，浮层叠加不打断历史 | R6 审计时间线轮：流水线事件→追加式 cell 流，含签字/确认/阻断事件，可回放 |

## 2. 设计 token（`:root{}` 变量块，可直接粘进页面）

命名空间 `--cb-*`（Civil Buddy），与各页现有变量并存、不覆盖；后续轮逐步切换引用。

```css
:root {
  /* === Civil Buddy UX tokens · ux(round1) · 见 docs/ux/ux-design-spec.md === */
  /* 色板：工程蓝 / 安全橙 / 合规红 / 通过绿 / 中性灰阶（slate） */
  --cb-blue: #2563eb;        /* 工程蓝：主操作、链接、选中 */
  --cb-blue-strong: #1d4ed8; /* 工程蓝-深：hover/按下 */
  --cb-blue-soft: #eff6ff;   /* 工程蓝-底：选中行、信息底 */
  --cb-orange: #ea580c;      /* 安全橙：警示、待人工补全、UNSPECIFIED */
  --cb-orange-soft: #fff7ed;
  --cb-red: #dc2626;         /* 合规红：阻断、废标项、禁句拦截 */
  --cb-red-soft: #fef2f2;
  --cb-green: #059669;       /* 通过绿：PASS、已签认 */
  --cb-green-soft: #ecfdf5;
  --cb-gray-50: #f8fafc; --cb-gray-100: #f1f5f9; --cb-gray-200: #e2e8f0;
  --cb-gray-400: #94a3b8; --cb-gray-500: #64748b; --cb-gray-900: #0f172a;
  --cb-text: var(--cb-gray-900);
  --cb-text-muted: var(--cb-gray-500);
  --cb-line: var(--cb-gray-200);
  /* 字体（零外链，系统栈） */
  --cb-font: "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  --cb-mono: ui-monospace, "Cascadia Code", Consolas, monospace; /* 锚点[A001]/坐标/UNSPECIFIED 用 mono */
  /* 字号阶梯 */
  --cb-fs-xs: 12px; --cb-fs-sm: 13px; --cb-fs-md: 14px; --cb-fs-lg: 16px;
  --cb-fs-xl: 18px; --cb-fs-2xl: 22px; --cb-fs-3xl: 28px;
  /* 间距（4px 基） */
  --cb-space-1: 4px; --cb-space-2: 8px; --cb-space-3: 12px; --cb-space-4: 16px;
  --cb-space-5: 24px; --cb-space-6: 32px; --cb-space-7: 48px;
  /* 圆角 / 阴影 */
  --cb-radius-sm: 6px; --cb-radius-md: 10px; --cb-radius-lg: 14px; --cb-radius-full: 999px;
  --cb-shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
  --cb-shadow-md: 0 4px 18px rgba(15, 23, 42, 0.10);
  --cb-shadow-lg: 0 10px 32px rgba(15, 23, 42, 0.16);
}
```

落地位置：`frontend/workbench.html`（紧跟现有 `:root`）、`demo/static/styles.css`（:8765 UI）。`frontend/index.html` 色板已与 token 同源（slate+蓝），后续轮再切换引用。

## 3. 语言规范

### 3.1 界面语言
界面文案一律简体中文；代码标识符、API 路由、锚点（`[A001]`）、`UNSPECIFIED`、坐标/吨位数字保持原文等宽字体。

### 3.2 术语表

| 术语 | 用法 | 不说 |
| --- | --- | --- |
| 岗位 | 66 岗专家对外统一叫「岗位」（岗位/专家岗位） | 不用 "Agent 角色" 面向用户 |
| 装柜 | 拼柜/装柜/订柜（订柜 N0）；柜数与坐标由 tools 计算 | "模型摆箱子"（禁句） |
| 作业单 | 绑扎/空隙作业单（secureWorkOrder 产物） | "施工单" |
| 交底 | 班前白话交底（安全交底材料） | "培训材料" |
| 审批 | HITL 审批门：确认/驳回，决策留痕 | "自动通过"、"一键放行" |
| UNSPECIFIED | 数据哨兵：**界面上显示为「未提供」安全橙徽标**，点开可见原文哨兵；导出文书保留 `UNSPECIFIED` 原文与 `[A001]` 锚点供人工补全 | 不译、不藏、不伪填 |

### 3.3 禁句表（承 docs/competition-demo-script.md「不说的话」）

界面、文书、口播均不得出现：**中标率 / 可以投标 / 可以开工 / GeBIZ 代交（及任何代交官方系统表述）/ 模型自己摆箱子·模型决定几柜**。P0 字样必须连着"须人确认"。边界要直说：TMS/ERP 为 stub、VGM 须托运人签认、大票需绑扎复核。

## 4. 12 轮路线图（R2–R13，每轮一行：主题 + 验收标准）

| 轮 | 主题 | 验收标准 |
| --- | --- | --- |
| R2 | 输入：三端统一单输入框（自然语言+/指令+@文件+改方案） | 一个 composer 覆盖全部输入模式；Esc=取消且语义有提示；CI 标记不丢 |
| R3 | 进度：流水线事件流可视化（consumeSse→阶段步骤条） | 每阶段有状态色（蓝=进行/绿=过/红=断）+ 耗时；事件全量可回放 |
| R4 | 文书预览：装柜单/作业单/交底 A4 预览（PDF/docx 一致） | 预览内容与导出 docx 逐字段一致；UNSPECIFIED 显示「未提供」徽标 |
| R5 | 审批卡：submit_blocked 审批卡（动作特定选项+显式决策事件） | 决策必须显式点击；Esc/关闭=驳回不=放行；决策写入审计 |
| R6 | 审计时间线：追加式会话 cell 流（签字/确认/阻断全留痕） | 任一运行可回放全部事件；签认/确认有时间戳与操作者 |
| R7 | 错误恢复：HITL checkpoint 恢复 UI + 失败重试路径 | 断点续跑不丢状态；恢复入口从时间线可达 |
| R8 | 窄屏：响应式三栏→单栏（768px 断点） | 768/375 宽度下输入、流水线、审批卡全部可用 |
| R9 | 指令面板：`/` 命令 + 66 岗检索面板 | 66 岗可检索可点名；面板零 CDN、键盘可达 |
| R10 | 引导：空态三步剧本强化（装柜 demo 路径） | 新用户 3 分钟内完成首跑（demo_one_shot 同路径） |
| R11 | 主题：--cb-* token 全量接管 + 明暗双套（prefers-color-scheme） | 三端零硬编码色值引用旧变量；明暗切换无对比度回归 |
| R12 | 离线：内网离线资源自检（零外链断言入 CI） | 断网全功能；CI 增加"零 CDN/外链"静态断言 |
| R13 | 终评：scorecard + 禁句自查 + 可用性走查收官 | eval_competition_scorecard 分数不降；禁句全文检索为零 |

## 5. 借鉴来源清单

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| openai/codex `codex-rs/tui/src/bottom_pane/approval_overlay.rs` · `chat_composer.rs` · `history_cell/`（github.com/openai/codex） | Apache-2.0 | 三态交互模式：审批=动作特定选项+显式决策事件+Esc≠继续；单输入框承载所有输入；输出=追加式历史 cell。**pattern-only**（Rust TUI→Web 场景，不抄代码） |
| picocss/pico `css/pico.min.css`（picocss.com） | MIT | token 思路：单一 `--spacing`/`--border-radius` 变量派生全局、语义化变量命名、系统字体栈。可抄变量取值思路（本轮仅借模式） |
| watercss/water.css `out/water.css`（watercss.kkga.de） | MIT | token 思路：语义色命名（text-main/text-muted/focus/border）+ `prefers-color-scheme` 明暗双套同名词。R11 主题轮按此扩展 |

## 附录 A：UX 基线体检（ux round1 只读盘点）

| 资产 | 位置 | 行数 | CSS | CDN | 字体 | 主色 | 响应式 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 宿主页 | `frontend/index.html` | 850 | 内联 `<style>`，`:root` 17 变量（light slate） | **零** | Segoe UI/PingFang SC/Microsoft YaHei | --brand #2563eb | 1 个 @media |
| 大 Team 工程台 | `frontend/workbench.html` | 4971 | 内联 `<style>`，`:root` 26 变量（dark） | **零** | 同上 + Cascadia/Consolas mono | --accent #5b8def | 5 个 @media |
| Rust :8765 工作台 | serve `demo/static/`（`workbench/src/api.rs:75` ServeDir；index.html 148 / styles.css 209 / app.js 677 / studio.js 304） | 1338 | styles.css `:root` 12 变量（light paper） | **零**（styles.css 同源外链） | 同上 | --accent #0f766e | 2 个 @media |
| civil.py CLI | `packing_assistant/civil.py` | 225 | argparse CLI（tui/exec/app/mcp/serve/skills/resume），非富文本 TUI | 零 | 终端 | — | — |

三端 `:root` 命名互不一致（--accent 三种蓝/青）、明暗主题分裂（workbench 深、其余浅）→ 由 R11 统一。

**专业合规元素现状**：

- `submit_blocked`：`frontend/index.html:642/797/815`（submitBlocked 状态）；`gateway/app.py:331/598`（submit_blocked_default=True）。**workbench.html 无呈现**（R5 补审批卡）。
- 免责声明：仅 `demo/static/index.html:16`「内部讨论草稿 · 不是签认件」。index/workbench 缺（R4/R5 补）。
- 签认：`demo/static/index.html` confirmOk 勾选「我明白，将由持证人员签认」；`packing_assistant/civil.py:21` CONFIRM 常量同句。无独立签字栏（R6 时间线补签认留痕）。
- UNSPECIFIED：哨兵遍布 `packing_assistant/runtime/*` 与 `expert_turn.py` 等；**前端无显示规则**（本轮 spec §3.2 定规则，R4 落地）。
- 术语：装柜（workbench.html 5 处）、作业单/交底少量出现；三端无统一术语表（本轮 §3.2 定稿）。
- CI frontend 断言（`.github/workflows/ci.yml:24-40,100-107`）要求 workbench.html 保留：`大 Team / org-chart / /api/pipeline / consumeSse / hitl_summary / draw3d / TEAM_ROSTER / /api/whatif / What-if / 订柜 N0 / 3D 用柜 / perCabinCog / secureWorkOrder / big_team_a_b / /api/whatif/apply / /api/profiles / POR 装柜单 / 应用为当前方案`；index.html 保留 `Civil Buddy / /workbench`。每轮改 UI 前先对照此清单。

## 附录 B：阶段时间线 · 事件→阶段映射表（ux round3 定稿，后续轮共用）

> R3 落地「一条流水线（进度可见）」：把 SSE 事件流映射为固定 8 阶段轨道。
> 组件为纯 vanilla JS/CSS，两端同构：`frontend/workbench.html`（Vue2 内联，`CB_TL_*` 常量）与
> `demo/static/app.js`（`cbTlCreate()` + `CB_TL_STAGES`/`CB_PHASE_STAGE`）。零 CDN、零外链。

### B.1 阶段轨道与状态色

固定轨道（顺序即流水线顺序，阶段可被打回重做，重做计入 `reruns` 徽记）：

```
理解任务 → 召唤岗位 → 成箱 → 人工确认 → 拼柜 → 合规校核 → 落盘 → 收口
```

| 状态 | 图标 | token 色 | 语义 |
| --- | --- | --- | --- |
| 待执行 | `·` 空心 | --cb-gray-400 | 未到达 |
| 进行中 | spinner（prefers-reduced-motion 时静态圆） | --cb-blue 工程蓝 | 事件流正在此阶段 |
| 完成 | `✓` | --cb-green 通过绿 | 阶段事件闭合 |
| 打回/待人工 | `⚠` | --cb-orange 安全橙 | replan 打回、HITL 等待、UNSPECIFIED——不藏、不红字恐慌 |
| 阻断 | `⛔` | --cb-red 合规红 | 仅 agent status=error 等硬失败 |

### B.2 借鉴来源（pattern-only）

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| Aider-AI/aider `aider/waiting.py` `Spinner`（github.com/Aider-AI/aider） | Apache-2.0 | 进行中=单行 spinner+文字标签，不打扰历史流；渲染降级（unicode→ASCII → web 场景 prefers-reduced-motion 去动画） |
| openai/codex `codex-rs/tui/src/chatwidget.rs` + `history_cell.rs`（github.com/openai/codex） | Apache-2.0 | 追加式会话流；进行中事件合并为单格（active_cell），完成后定格为不可变历史（时间线折叠为一行摘要）；幂等去重 |
| VS Code Tasks presentation（code.visualstudio.com/docs/debugtest/tasks） | 文档 pattern-only | 长输出默认折叠成一行、出问题才展开；reveal 语义映射为"展开/收起"按钮 |

### B.3 :8000 `/api/pipeline/stream` 事件映射（gateway/app.py → packing_assistant/teams/big_team.py、agent_loop.py）

SSE 形状：`data: {...}\n\n`（fetch+ReadableStream 解析，workbench `consumeSse`/`onStreamEvent`，WS 同源 HUB 复用同一处理）。

| 事件 type | 关键字段 | → 阶段 | 人话 |
| --- | --- | --- | --- |
| `run_start` | run_id, team_mode | 重置时间线；理解任务=进行中 | 开始装柜任务 |
| `agent_start` | node | 见节点映射表 B.4 | 阶段进入进行中 |
| `agent_end` | node, status, duration_ms, step.message | 同上；status=error→阻断红 | 阶段完成（子行记一句话结果+耗时） |
| `tool_start` / `tool_end` | node, tool, duration_ms | node 映射优先，tool 映射兜底 | 当前阶段下缩进子行：工具名+结果 |
| `hitl` | hitl_summary, session_id | 人工确认=进行中+高亮 | "等待人工确认…"（R5 审批卡挂载点 `[data-r5-approval-slot]`） |
| `replan` | message, replan_round | 合规校核=⚠ 安全橙 | critic 打回重做 |
| `debate` | message | 成箱子行 | 有界辩论 |
| `done` | public, summary, artifact_paths | 收口=完成；未完成的落盘补完成 | 折叠为一行摘要：`流水线完成 · Ns` + 数字 chips（订柜 N0/实装柜数/成箱箱数/风险裁决/ship_ok，**只抄事件数值**） |
| `replay_start` / `replay_done` | run_id | 重置（带「回放」徽标）/ 收口 | 历史回放 |
| `error` | message | 当前阶段 ⚠ + 子行 | 事件流报错 |

### B.4 :8000 节点/工具 → 阶段（big_team 团队节点 + agent_loop 白名单工具）

| node（agent_start/end） | 阶段 | | tool（llm_scheduler 模式） | 阶段 |
| --- | --- | --- | --- | --- |
| `intent` | 理解任务 | | `intent.interpret` / `knowledge.search` | 理解任务 |
| `orchestrator` | 召唤岗位 | | `container.select` | 召唤岗位 |
| `material_parser` `structure` `box_scheme` `present_team_a` `bounded_debate` | 成箱 | | `team_a.run` / `team_a.rebox` | 成箱 |
| `hitl_wait` / `user_confirm` | 人工确认 | | `hitl.check` / `hitl.confirm` | 人工确认 |
| `planner` `loader` `evaluator` | 拼柜 | | `team_b.plan_load_eval` | 拼柜 |
| `risk_compliance` `replan_critic` | 合规校核 | | `team_b.risk` / `replan.critic` | 合规校核 |
| `visualizer` | 落盘 | | `team_b.visualize`、`manifest*` `tms*` `booking*` `secure*` `docx*` `plan.export*` 等前缀 | 落盘 |
| `finalize_run` / `finalize` | 收口 | | `finalize.run` | 收口 |

兜底规则：未列出工具 → 附在**当前进行中阶段**的子行（计数于 `cbTl.fallbackTools`，不产生「未知」桶）。

### B.5 :8765 `/api/chat` 事件映射（workbench/src/api.rs、agent.rs）

SSE 形状：`event: <name>\ndata: {...}\n\n`（demo/static/app.js `streamChat`→`cbTlCreate()`）。

| event | payload.phase | → 阶段 | 人话 |
| --- | --- | --- | --- |
| `context` | — | （不进时间线：已有 ctx 仪表） | 上下文用量 |
| `status` | `understand` / `compress` / `import` | 理解任务 | 听懂为 run/chat；上下文压缩 |
| `status` | `summon` / `queue` / `plain` | 召唤岗位 | 已召唤某岗；独立专家 i/N；未点名岗位 |
| `status` | `harness` / `scheme_gate` | 成箱 | 一人公司成套 harness steps |
| `status` | `hitl_gate` / `hitl` / `confirm` | 人工确认（高亮+R5 占位） | HITL：专项未确认不出施工草稿 |
| `status` | `plan_load_eval` / `pack` | 拼柜 | 规划→装载→评估 |
| `status` | `risk` | 合规校核 | 出运门禁 |
| `status` | `exclusive` / `write` / `price` / `doc` / `deliver` | 落盘 | 专属出稿工具步（pack-ship__plan/export/health 等）、价表/草稿写盘 |
| `status` | `done` | 收口 | 收口 |
| `status` | `think` / `talk` / `chat` / 工具名（`search_kb` `read_kb` `list_kb` `web_search` `web_open` `list_attachments` `read_attachment` 等） | 当前阶段子行（不落「未知」） | 解释轮次/出稿后白话说明/工具一句话结果 |
| `token` | — | （正文流式渲染，不进时间线） | 正文输出 |
| `error` | — | 当前阶段 ⚠ 安全橙 | 报错不恐慌 |
| `done` | mode, deliverables | 收口=完成 | 整条折叠为一行摘要：`完成 · 一人公司成套/岗位收工/回答完毕 · 文书 N 份`（N 只抄 `deliverables.length`） |

### B.6 CI

frontend 断言沿用 §附录 A 的 18 标记清单；时间线组件不删任何标记。`frontend/workbench.html` 保留 `consumeSse`（R3 起重新用于 `/api/pipeline/stream` 全流程流式）与 `hitl_summary`。
