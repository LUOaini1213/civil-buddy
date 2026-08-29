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
| 纠偏卡 | 错误/拒绝/缺数的统一可行动卡片（R7）：发生了什么+为什么(code)+现在能做什么，见附录 F | 不用「失败了」「出错了」裸文本收尾 |
| 熔断 | 连续失败/超预算自动停下止损（`circuit_open`/`deny_budget`），卡上写明数字 | 不说"崩了/挂了/系统故障" |
| 降级 | 工具失败后标 `UNSPECIFIED` 不编数（recovery 层），卡上写明已尝试次数 | 不说"部分成功"掩盖失败 |

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

## 附录 C：交付物文书预览组件（ux round4 定稿）

> R4 落地「一份正式交付物」：聊天/工作台里的 markdown 交付物按正式文书呈现，
> 而非终端输出。两端同构 vanilla 组件；零 CDN、零外链字体。

### C.1 组件结构（`cbDocOpen` / `cbDocClose` / `cbDocDecorate`）

| 端 | 组件源 | 样式 | 接入点 |
| --- | --- | --- | --- |
| :8765 | `demo/static/docpreview.js`（canonical） | `demo/static/styles.css` 追加 `.cb-doc-*` 块 | `index.html` 引入；`app.js` done 后聊天流内交付物卡片（预览/下载），侧栏 `#files` .md 点开即预览（`/api/file`，out_root 内） |
| :8000 | `frontend/vendor/cb-doc.js`（同构副本，头部注明 canonical） | `frontend/workbench.html` 内联同构 CSS 块 | `workbench.html` done 事件捕获 `ev.artifact_paths` → 「交付物文书」面板（`[data-cb-doc-panel]`），`openDocArtifact` 走 `GET /api/artifact`（gateway/app.py，限 ROOT 内 .md/.markdown/.json/.txt/.jsonl 文本） |

DOM 结构（追加到 `document.body`，打印时独占文档流）：

```
.cb-doc-overlay[hidden] > .cb-doc-backdrop + .cb-doc-modal
  .cb-doc-toolbar（标题/字符数 · 复制 Markdown / 下载 .md / 打印存 PDF / 关闭）
  .cb-doc-scroll > article.cb-doc-page（白底 A4 版心 794×1000）
    header.cb-doc-head   页眉：项目名 + 岗位（等宽）
    .cb-doc-body.cb-doc-md   marked 渲染正文（经 sanitize：去 script/iframe/on*）
    footer.cb-doc-foot   页脚：生成时间 + 「ux(round4) 文书预览 v1」
                         + .cb-doc-disclaim「内部讨论 AI 草稿 · 不签认」（合规红，常驻）
```

### C.2 版式与诚实元素

- 版式：正文系统仿宋/宋体栈（`FangSong → 仿宋_GB2312 → SimSun → …`），标题黑体栈，表格实线边框（GB/T 9704 工程文书惯例 pattern，自拟）；零外链字体。
- 诚实元素（spec §3.2 落地）：`UNSPECIFIED`/待填类 → 安全橙徽章「未提供」（title 保留原文哨兵）；`[A001]` → 橙色虚线锚点徽章；标题含「工具计算/回传/只抄/非本岗编造」的小节 → 浅蓝底 + `tool-computed` 徽记；正文首段含「不构成/仅供内部讨论/不是签认」→ 合规红横幅样式。
- 打印：`@media print` 隐藏聊天/工作台 chrome 只留文书本体；页眉页脚 `position:fixed` 每页复现。

### C.3 vendored 依赖清单（零 CDN，运行时全部同源）

| 名 | 版本 | 体积 | 许可 | 来源 URL | 落位 |
| --- | --- | --- | --- | --- | --- |
| marked | 12.0.2 | 35,479 B | MIT | https://registry.npmjs.org/marked/-/marked-12.0.2.tgz | `demo/static/vendor/marked.min.js` + `frontend/vendor/marked.min.js`（LICENSE 同目录） |
| vue | 2.7.16 | 107,679 B | MIT | https://registry.npmjs.org/vue/-/vue-2.7.16.tgz | `frontend/vendor/vue.min.js` + `vue.LICENSE`（**修复**：workbench.html 原直连 jsdelivr CDN，违背零外链红线，本轮改同源引用） |

`frontend/vendor/cb-doc.js` 为 `demo/static/docpreview.js` 同构副本（非第三方依赖，改动须同步两份）。

## 附录 D：HITL 审批卡组件（ux round5 定稿）

> R5 落地「一道审批门」：把"等确认"从文本提示变成正式审批交互。
> 契约（承 U-R1 / codex `approval_overlay.rs` pattern-only）：**审批必须 = 显式决策事件 + Esc/关闭=驳回永不放行 + 决策进审计链**。
> 组件为两端同构 vanilla 实现，零 CDN、零外链、全 token 化。

### D.1 组件结构（`.cb-apr`，挂载点 `[data-r5-approval-slot]`）

| 端 | 挂载位置 | 实现 |
| --- | --- | --- |
| :8000 | `frontend/workbench.html` 时间线「人工确认」阶段（`#cb-hitl-slot`，`cbTlOnEvent` 的 `type==='hitl'` 分支挂载） | Vue2 内联组件（`cbApr` 状态 + `cbAprConfirm/cbAprReject/cbAprLater/cbAprEsc`） |
| :8765 | `demo/static/app.js` 聊天流内本条消息的时间线（`cbTlCreate` 的 `mountApproval`，`done` 事件 `hitl.pending=true` 时挂载） | vanilla DOM + `CB_APR_WAITING` 全局 Esc 注册表 |

```
.cb-apr（合规红左边条 .cb-apr-bar；approved→绿、rejected→橙）
  .cb-apr-head   标题「人工确认 · 成箱方案」+ 风险徽章（high=橙 / low=灰）+ 状态徽 + ✕
  .cb-apr-body
    .cb-apr-chips    方案摘要：只抄事件/状态字段（N0*、柜型、箱数、材料数、毛重、can_fit 若有）——不编数字
    .cb-apr-block    风险与阻断（非标 overall/ship_gate、结构不通过、待详设、超长、VGM 待签；无则直说"工具未报告阻断项"）
    .cb-apr-actions  决策区三按钮：确认并拼柜（主，--cb-blue）/ 驳回（红 --cb-red）/ 稍后（灰）
    .cb-apr-foot     Esc/关闭=驳回永不放行 · 高风险岗提示确认句「我明白，将由持证人员签认」（流程层已强制门禁，UI 只提示不重复实现）
  审计行 .cb-tl-audit-row（追加式、折叠态常驻、永不可折叠消失；R6 全量审计时间线承接）
    格式：`审计 · <决策>（<理由>） · YYYY-MM-DD HH:MM:SS · 操作者=本地用户 · 未静默放行`
```

### D.2 决策事件与三态

| 态 | 触发 | 事件 | 后续 |
| --- | --- | --- | --- |
| 等待 waiting | `hitl` 事件 / `hitl.pending` | 无决策，checkpoint 已落盘（durable） | 「稍后」折叠为等待条，可重新展开；刷新回来自恢复 |
| 已确认 approved | 显式点「确认并拼柜」 | :8000 `POST /api/confirm action=confirm`（既有链路）；:8765 勾选 confirm_ok 句并重提原文 | 拼柜继续；卡片定格「已确认」+ 审计行 |
| 已驳回 rejected | 显点点「驳回」/ ✕ / **Esc（全局）** | :8000 `POST /api/confirm action=cancel`（引擎 `phase=cancelled`）；:8765 不重提、不出稿 | 橙 ⚠ need_revision 式呈现「已驳回 · 未放行 · 请修改输入后重跑」，不粉饰；审计行 |

- Esc 映射=Cancel（永不静默变成"继续"）；关闭按钮与 Esc 同语义；网络失败不改变本地驳回判定。
- 高风险 = `hitl_summary.cards[].level∈{warn,err}` 或结构不通过 / 超长 / 非标 FAIL·WARN·NEED_DESIGN；:8765 闸门（scheme/exclusive_write）按 expert.risk=high 恒为高风险。
- 移动端：`@media (max-width: 768px)` 决策按钮全宽纵排（R8 打底）。

### D.3 借鉴来源（pattern-only）

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| openai/codex `approval_overlay.rs`（github.com/openai/codex） | Apache-2.0 | 选择必发显式决策事件；Esc=Cancel 不随键位变；动作特定选项（confirm/reject/later）；决策插入历史 cell（→审计行） |
| GitHub PR review 三态（approve/request changes/comment） | 交互 pattern | 三态决策区 + 决策可追溯；驳回必须给理由位（此处由引擎状态承载） |
| Temporal/Argo 人工审批节点 | 交互 pattern | 等待卡常驻 + 超时/升级提示语义（此处为"durable checkpoint 可安全关闭后 resume"提示） |

## 附录 E：跨运行审计时间线组件（ux round6 定稿）

> R6 落地「任一运行可回放全部事件；签认/确认有时间戳与操作者」：把 U-R5 单次运行内的审计行
> 扩展为**跨运行全量可回放审计时间线**——"谁来都得说清楚 AI 做了什么、人批了什么"。
> 两端同构 vanilla 实现，零 CDN、零外链、全 token 化；数据端点**只读**，越界 403。

### E.1 数据源与关联键（全部只读）

| 数据源 | 位置 | 关键字段 | 说明 |
| --- | --- | --- | --- |
| 事件流 trace.jsonl | `output/runs/<run_id>/trace.jsonl`（:8000） | `type, run_id, session_id, seq, ts, t_ms, duration_ms, status, node, tool` | `packing.stream.v1`；每事件带 session_id → **跨 run 串联键 = session_id** |
| HITL checkpoint | `output/runs/<run_id>/checkpoint.json`（:8000） | `user_action(confirm/cancel), status, phase, saved_at` | U-R5 交接：服务端已持久 user_action → 决策节点的权威来源 |
| session 索引 | `output/sessions/<session_id>.json`（:8000） | `run_id, status, saved_at` | 无 session 参数时返回最近会话列表 |
| demo trace | `demo/out/<session>/runs/<run_id>/trace.json`（:8765） | `steps[]{expert,tool,ok,legal,note}, hitl{required,confirmed,pending,gate}` | Rust Run 结构；run 间排序用目录 mtime |

### E.2 端点（只读聚合）

| 端 | 端点 | 实现 |
| --- | --- | --- |
| :8000 | `GET /api/audit?session=<id>`（`gateway/app.py`） | 聚合 trace.jsonl + checkpoint.json + session 索引；tool_start/end 成对合并；无 session → 最近会话列表；`..`、路径分隔符、控制字符 → **403**；schema=`civil.audit.v1` |
| :8765 | `GET /api/harness/audit/{session}`（`workbench/src/api.rs` + `harness.rs::audit_session`） | 扫描 `demo/out/<session>/runs/*/trace.json`；同语义 403；schema=`civil.audit.v1` |

### E.3 节点类型 → 配色 → 来源映射（四色）

| kind | 色 | 语义 | :8000 来源事件 | :8765 来源 |
| --- | --- | --- | --- | --- |
| `tool` 工具执行 | --cb-blue 蓝 | AI 做了什么（岗位节点/工具步/辩论） | `agent_start/end`（合并）、`tool_start/end`（合并）、`debate` | `steps[]`（ok 且 note 非"已写入"） |
| `decision` 人工决策 | --cb-red 合规红边 | 人批了什么（**永久置顶 · 不可折叠**） | `hitl`（等待）+ checkpoint `user_action`（confirm=放行 / cancel=未放行） | `Run.hitl`（confirmed/pending/rejected） |
| `error` 错误/重试 | --cb-orange 橙 | 失败与打回，不藏不恐慌 | `status=error` 的事件、`replan` | `steps[]`（ok=false 或 legal=false 非法工具拦截） |
| `write` 写盘 | --cb-green 绿 | 产物落了哪些盘 | `tool_end` 工具名匹配落盘前缀（承附录 B.4：`manifest* tms* booking* secure* docx* plan.export* export* vgm* …`）、`done`（artifact_paths） | `steps[]`（note 含「已写入」） |

节点行：`类型徽 + 一句话摘要 + 耗时（ms，仅 :8000 有）`；点「原始」展开 JSON 负载（折叠模式同 U-R3/U-R4）。
**决策节点永久置顶**：面板顶部固定"人工决策"区块，跨 run 汇总（标题/时间/run_id/操作者=本地用户 · 未静默放行），不随折叠消失。

### E.4 组件与导出

| 端 | 组件 | 样式 |
| --- | --- | --- |
| :8000 | `frontend/workbench.html` 历史页 `[data-cb-audit-panel]`（Vue2：`loadAudit/auditRunsDesc/auditToggleRaw/auditExport`；session 框默认跟随当前 sessionId） | `.cb-audit-*` 内联块 |
| :8765 | `demo/static/index.html` 侧栏 `#auditPanel` + `app.js`（`loadAuditPanel/auditNodeEl/refreshAuditSoon`；done 事件后自动刷新） | `demo/static/styles.css` `.cb-audit-*` 块 |

- 分组：按 session 一次加载全部匹配 run（新 run 在上），run 内节点按 `ts/seq` 时间正序（可回放）。
- 导出（人机协同履历表素材）：「复制 JSON / 下载 JSON」→ `{schema, exported_at, product, session_id, counts, decisions, runs[]}`，文件名 `audit-<session>.json`；只抄数据源字段，不编数字。
- 借鉴来源（pattern-only）：Langfuse session→trace→observation 分层与单列 trace log view（MIT）、Argo Workflows 节点时间线与重试标记（Apache-2.0）、Git 提交图纵向时间轴+泳道分组（pattern）。

## 附录 F：纠偏卡片 · 错误与恢复话术映射（ux round7 定稿）

> R7 落地「错误恢复」门面：把散在事件流/日志里的拒绝、熔断、降级、缺数变成**用户能行动的卡片**
> （海之子杯评审维度二：AI 纠偏管理）。统一结构三段式：
> **发生了什么（一句人话）+ 为什么（策略 code/规则名，等宽）+ 现在能做什么（≤3 条动作/指引）**。
> 两端同构 vanilla 实现，零 CDN、零外链、全 `--cb-*` token；动作**预填输入框草稿，不自动发送**（重试除外=重放同 payload）。

### F.1 组件结构（`.cb-fix`）

| 端 | 分类/渲染源 | 挂载点 |
| --- | --- | --- |
| :8765 | `demo/static/fixcard.js`（canonical：`CB_FIX.classify/classifyMissing/cardEl`）+ `app.js` 端侧动作句柄 | 聊天流内失败消息体后（catch / SSE error）；`done` 正文含哨兵时挂缺数提示条 |
| :8000 | `frontend/vendor/cb-fix.js`（同构副本，改动须同步两份）+ Vue2 组件 `cb-fix-card` | 时间线错误位（`cbTlOnEvent` error/agent_end）、总览报错条下方、`revise-nl` unsupported、`done` public 缺数提示条 |

```
.cb-fix（左边条：拦截/熔断=合规红，其余=安全橙；role=alert）
  .cb-fix-head   徽章（已拦截/已熔断/已降级/可重试/暂不支持/缺数/合规阻断/失败）+ 一句人话标题
  .cb-fix-why    code 徽片（等宽，如 deny_cross_expert）+ 规则一句话
  .cb-fix-meta   重试/退避信息——只抄事件字段（attempts、audit 动作序列 call→retry→degrade），不编
  .cb-fix-what   「现在能做什么」≤3：按钮（prefill/retry）或纯指引（note）
  .cb-fix-raw    <details>「原始记录」折叠原文（一次点击看原始负载，Sentry 卡模式）
```

### F.2 话术映射表（code → 人话 → 动作；模式对准后端 reason 原文，不编数字）

| code（来源） | 触发原文（摘要） | 发生了什么（人话） | 现在能做什么（≤3） |
| --- | --- | --- | --- |
| `deny_chat_write`（policy.py） | 拒绝：提问回合不能调写盘工具 X | 这是提问回合，AI 不会写盘：X 被策略拦下 | [改成出稿任务]预填「写一份 」；指引：说成「写一份…」即 run 意图 |
| `deny_cross_expert` | 拒绝：岗 A 不能调 T（exclusive 属于 B） | 岗 A 越权调了 B 的专属工具 T，已拦截 | [召唤 @B]预填「@B 」；指引：或改写成 B 岗的活 |
| `circuit_open` | 熔断：工具 T 连续失败 n 次 | 工具 T 连着失败 n 次，先熔断止损 | [重试]重放同 payload；指引：稍后再试/换个说法 |
| `deny_budget` | 熔断：session 成本超限 steps s/ms tokens t/mt | 本轮预算用完（steps s/ms · tokens t/mt），已停下 | [缩短输入重跑]预填；[新开会话]（:8765）；指引 |
| `deny_production` | 拒绝：目标 P 视为生产数据 | 目标 P 是生产数据区，写入被拒 | 指引：输出只落本次运行输出目录，禁 D:\layout / prod |
| `deny_secret` | 拒绝：…secret/.env | 目标碰到密钥/敏感文件，写入被拒，文件未落地 | 指引：密钥永不写盘，走环境变量/密钥管理 |
| `deny_sandbox` | 拒绝：…沙箱/越界 | 操作超出本次运行的沙箱范围，被拦下 | 指引：读写限于本次会话工作区 |
| `deny_cancelled` / `deny_unknown` | 已取消 / 未知工具 X | 任务已取消未执行 / 调用了未注册工具 X | 指引（检查工具名/已取消） |
| `invalid_args` | 拒绝：工具 T 缺少参数 K | 工具 T 缺参数 K，没跑成 | [重试]；指引：参数由调用方组装，AI 不编 |
| `revise_unsupported`（nl_revision） | 无此功能：…（status=unsupported） | 这个改法还不会：方案保持原样，没有假装成功 | hints[] 预填 chips（≤2）+ 能力清单 note（总 ≤3） |
| `recovery_degrade`（recovery.py） | 下游失败 code，工具 T 降级，不编柜数 | 工具 T 重试后仍失败，已降级：数字标「未提供」，不编造 | [重试本工具]；指引；meta=共尝试 n 次 · call→retry→degrade |
| `timeout` | 失败：工具 T 下游超时（t s） | 工具 T 等了 t 秒没回应 | [重试]重放同 payload；指引 |
| `compliance_block`（risk/BOX 类） | 阻断/非标/ship_gate/废标/超载 | 合规校核拦下，不是工具坏了：按下面改即可重跑 | [改箱型重跑]预填；[减载重重跑]预填；指引：阻断项见原文 |
| `missing_data`（UNSPECIFIED/[A001] 扫描） | done 正文/public 含哨兵 | 还有 n 处数据未提供——补一句话即可重跑 | [去补数]预填「补充：[Axxx] …」；指引：发送即重跑，缺的数 AI 不编 |
| （兜底）`error` | 其余报错 | 原文截断呈现 | 可重试则[重试]，否则修改输入重跑指引 |

### F.3 交互红线（承公理 3/4）

- 动作按钮一律**预填草稿，不自动发送**；唯一例外=重试（重放同 payload，:8765 重发 `state.lastSend`，:8000 重跑 `runPipelineTrace`）。
- 「重试次数与退避」只抄 middleware/recovery 事件字段（`attempts`/`audit`），前端不编、不估算。
- 合规阻断不粉饰成"失败了"：列出阻断原文 + 改箱型/减载重引导；熔断写明止损语义与预算数字。
- 错误不用 toast（自动消失不可达），一律常驻卡片 + 折叠原文；Esc/刷新不丢失（卡片随历史消息定格）。

### F.4 借鉴来源（pattern-only）

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| Sentry issue 卡（docs.sentry.io/product/issues/issue-details） | 文档 pattern-only | 卡头=类型+上下文；动作直接在卡上；「原始记录」一次点击展开（堆栈→原始 reason） |
| NN/g Error-Message Guidelines | 文档 pattern-only | 错误三要素：可见、建设性（说清下一步）、尊重用户付出；禁"something went wrong"式空话 |
| GitHub Primer 禁 toast 共识 / toasts-are-bad-UX 辩论 | 文档 pattern-only | 错误与需行动的决策不用自动消失的 toast，用常驻卡 |
| Linear 乐观更新+持久重试入口 | 文档 pattern-only | 失败可回滚重试：卡上直接给「重试」，重放同 payload |
| openai/codex `exec_cell`/`history_cell` | Apache-2.0 | 错误=不可变历史 cell 的一部分，重试不改写历史只追加（承 R3 追加式会话流） |
