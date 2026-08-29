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
| R9 | 指令面板：`/` 命令 + 66 岗检索面板（ux round9 落地，见附录 H） | 66 岗可检索可点名；面板零 CDN、键盘可达 |
| R10 | 引导：空态三步剧本强化（装柜 demo 路径，ux round10 落地，见附录 I） | 新用户 3 分钟内完成首跑（demo_one_shot 同路径） |
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

## 附录 G：窄屏 / 工地手机适配（ux round8 定稿）

> R8 落地验收（§4 路线图）：768/375 宽度下输入、流水线、审批卡全部可用。
> 真实场景：项目主任/工友在工地用手机**看进度、批 HITL、看交底**——落地可行性的直观证据。
> 借鉴 pattern-only：GitHub Primer（min viewport 320px、移动触控目标 44px 到 AAA、
> 内容定断点、constrained fluid layout）、antd mobile / TDesign Mobile（列表式/卡片式布局、
> 卡片纵排、主操作全宽按钮）、PWA 最小件（manifest + theme-color；SW 离线缓存留给 R12）。

### G.1 断点 token（两端 `:root` 已落）

| token | 值 | 档位 | 说明 |
| --- | --- | --- | --- |
| `--cb-bp-mobile` | 430px | ≤430 手机竖屏 | 375/414 落此档；时间线缩轨、审计节点单列 |
| `--cb-bp-tablet` | 768px | 431-768 平板 | 三栏折叠、触控 44px、正文 14px/1.6 |
| `--cb-bp-desktop` | 769px | ≥769 桌面 | 不收紧（桌面布局原样） |

媒体查询条件不支持 `var()`：规则内使用字面量并注释 token 名。附录 A 基线里散落的旧断点
（workbench 720/640/1100/820/768、demo 1100/720/768）语义归并入三档，旧规则保留不动；
round8 新增规则一律 `@media screen and (max-width: …)`——**打印仍走 `@media print` 的 A4 版式**。

### G.2 关键动线窄屏规则（优先级从高到低）

| 动线 | ≤430（手机竖屏） | 431-768（平板） | 桌面不变 |
| --- | --- | --- | --- |
| 聊天+时间线+审批卡 | 时间线左轨道缩窄（子行 margin 10→4px）；composer 按钮整行 | 审批卡决策区纵排全宽、主决策 48px（附录 D.2 打底补齐）；正文 14px/1.6 | 原样 |
| 文书预览 | A4 版心退化为流式宽（794→100%）、页边距 56/60→16/24 | 同左；`.cb-doc-md table` 块级横向滚动 + 粘性首列 | A4 版心 |
| 审计面板 | 节点 flex-wrap 单列（徽标/摘要/时间竖排）、JSON 展开全宽 | 触控 ≥44px | 原样 |
| 顶部导航 | 汉堡键 | workbench ≤820 汉堡键开 `.sidebar.mobile-open`（复用既有 CSS，`☰ 菜单`）；页签横向滚动；demo ≤768 汉堡键开 `.rail.mobile-open`（`☰ 栏目`）；顶栏换行 | 原样 |
| 表格（材料表） | 横向滚动 | `table.data` 块级横向滚动 + 粘性首列 | 原样 |

### G.3 触控与可读性

- 可点目标 `min-height: var(--cb-touch-min)` = 44px（Primer：视觉 32px 按钮在移动端须垫高到 44 才达 AAA）；
  审批卡主决策 `var(--cb-touch-lg)` = 48px（拇指优先）。
- 正文 ≥14px、行高 1.6（≤768 生效：聊天正文/交底/纠偏卡话术）；徽标、时间戳等辅助信息可 10-12px。
- **大字模式钩子**：`html.cb-large` 把 `--cb-fs-*` 字号阶梯整体 +2 档
  （xs 12→14、sm 13→16、md 14→18、lg 16→22、xl 18→28、2xl 22→32、3xl 28→36），
  两端 CSS 已落，R11 主题轮在此之上接明暗切换即可。

### G.4 PWA 最小件（不做 Service Worker，离线缓存留 R12）

- `manifest.webmanifest` 两端同构（`frontend/` 与 `demo/static/` 各一份，改动须同步）：
  `name=土木伙伴 Civil Buddy`（中文）、`display=standalone`、`theme_color=#2563eb`、
  `background_color=#f8fafc`、`start_url=/`、icons（SVG any + PNG 192/512 maskable）。
- 图标：`icons/cb-icon.svg` + `icons/cb-icon-{192,512}.png`（`scripts/gen_pwa_icons.py` 纯标准库生成，零第三方）。
- head 三件：`<meta name="viewport" … viewport-fit=cover>`（刘海屏安全区）+ `<meta name="theme-color" content="#2563eb">` + `<link rel="manifest">`。
- 服务：:8000 由 gateway `app.mount("/static", frontend/)` 提供清单；:8765 由 `ServeDir(demo/static)` 同理——零新端点、零 CDN。
- 本轮顺手修红线遗留：`frontend/index.html` 的 jsdelivr CDN `<script>` 换成同源 vendored 副本（承附录 C.3）。

### G.5 借鉴来源（pattern-only）

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| GitHub Primer Responsive/Layout foundations（primer.style） | 文档 pattern-only | min viewport 320px 起步；移动触控目标垫到 44px（AAA）；内容定断点、constrained fluid、按可用性收拢布局 |
| antd mobile（mobile.ant.design）+ 设计稿 750=2×375 惯例 | MIT | 卡片式/列表式布局；移动端主操作全宽按钮；整卡纵排 |
| Tencent TDesign Mobile（tdesign.tencent.com） | 文档 pattern-only | 样式属性全部收敛进主题 token（对齐 --cb-* 命名空间做法） |
| web.dev / MDN Web App Manifest | 文档 pattern-only | manifest 最小字段：name/short_name + start_url + display + theme_color + icons |

## 附录 H：快捷指令面板 · / 命令 + 常用任务模板（ux round9 定稿）

> R9 落地「指令面板」：输入 `/` 弹命令面板（与 R2 @岗补全同一浮层体系）——老手直达、新手有路。
> 两端同构（:8000 `frontend/workbench.html` Vue 内联 / :8765 `demo/static/app.js` vanilla），
> 零 CDN、零外链、全 `--cb-*` token、全键盘可达。**面板任何动作都不自动发送**（承附录 F.3 红线）。

### H.1 交互模式

| 行为 | 落法 | 来源（pattern-only） |
| --- | --- | --- |
| 唤起 | 输入 `/`（行首/空白后）即弹面板；继续输入按名过滤 | codex slash popup |
| 模糊过滤+排序 | 前缀命中(0) > 中文子串命中(1) > 子序列命中(3)；空查询=原序全量；别名命中不重复展示 | VS Code Command Palette「模糊必须带排序」 |
| 键盘 | ↑↓ 移动、Enter/Tab 确认、Esc 关闭（关闭记住 token，编辑后才重开——同 @岗）；票子菜单内 Esc=返回命令层 | codex / Raycast「子菜单 Esc=返回上一级」 |
| 模板填空 | 选中模板命令 → 整框替换为带 `<待填>` 占位的结构化草稿，先改后发 | GitHub Saved replies / Issue templates、Raycast argument placeholder |
| 最近任务 | 面板顶部「最近 3 条任务」（localStorage `cb_recent_tasks_v1`，去重存 8 条），点击重填不发送 | VS Code palette recency |
| 老手直达 | 直接发送 `/pack <票名>`、`/bid <要点>`、`/safety <要点>` → 发送前展开成任务文本再走正常链路；`/audit /doc /eval` 就地执行不发送；未带参给用法提示 | codex Tab-queue 语义（就地化） |

### H.2 命令清单（两端同构；图标 = `--cb-*` 色块 + 单字，不引图标库）

| 命令 | 图标/色 | 名称 | 一句说明 | 动作 |
| --- | --- | --- | --- | --- |
| `/pack` | 装·蓝 | 装箱拼柜 | 选 sim_materials 票，预填装柜任务 | 票选择子菜单 → 模板 |
| `/bid` | 标·深蓝 | 招标解析 | 预填招标解析模板（@招标解析） | 模板 |
| `/safety` | 安·安全橙 | 安全交底 | 预填班前白话交底模板 | 模板 |
| `/audit` | 审·合规红 | 审计面板 | 打开跨运行审计时间线 | 跳转（附录 E 面板） |
| `/doc` | 文·通过绿 | 最近交付物 | 预览最近一份交付物文书 | 跳转（附录 C 预览） |
| `/eval` | 评·中性灰 | 记分卡摘要 | 竞赛记分卡 / 离线自检 | 跳转（见 H.4） |
| （:8765 附加）`/skills /new /threads /bg /help` | 灰 | 既有客户端命令 | 面板给发现性；确认后预填命令文本 | 预填命令 |

### H.3 模板文案（`<待填>` 占位；数字一概不预编）

- `/pack`（选中票 `<票名>` 后）：`pack test/sim_materials/<票名>/materials.xlsx（<story>）` + `要求：40HQ 高利用率装柜；柜数与坐标由 tools 计算，模型不摆箱子；出装柜单草稿，须人工确认后才拼柜。`（:8000 网关 `_load_materials_from_text` 原生解析 NL 中的仓库相对 xlsx 路径——模板路径即真实可用数据路径）
- `/bid`：`@招标解析 解析这份招标文件：项目名称：<待填> 关键条款：<待填：工期 / 资质 / 报价上限> 请列出资格条件与废标项清单；P0 资格须人工确认，是否投、怎么投由人决定。`
- `/safety`：`@安全交底 写一份班前白话交底：作业内容：<待填> 主要风险与防护：<待填> 给工友的白话版，一条一个动作；先讨论，说「写一份」才出草稿。`

### H.4 数据源

| 数据 | 来源 | 说明 |
| --- | --- | --- |
| 票选择子菜单（/pack 第二级） | `test/sim_materials/*/materials.xlsx` 磁盘枚举 + `INDEX.json` 元数据 | 由 `scripts/gen_cb_tickets.py` 生成静态清单（gen_cb_posts.py 同款双产物）：`demo/static/tickets.js`（window.CB_TICKETS）+ workbench 内嵌 BEGIN/END 块；**无目录枚举端点**（:8000 `/api/artifact` 只读文件、:8765 `/api/file` 仅 out_root），故走静态清单，与磁盘一致由生成脚本保证 |
| 最近任务 | `localStorage["cb_recent_tasks_v1"]` | 记录时机：:8765 form submit、:8000 runTeamA/runPipelineTrace；仅本地，不上传 |
| /audit | :8000 `POST 无`（Vue 跳历史页 + `loadAudit()`）；:8765 `#auditPanel.scrollIntoView` + `loadAuditPanel()` | 附录 E 既有只读端点 |
| /doc | :8000 `docArtifacts[0]` → `GET /api/artifact`；:8765 `done` 事件 deliverables 最近一份 → `/api/file` | 附录 C 既有预览组件 |
| /eval | :8000 `GET /api/artifact?path=output/competition/scorecard_latest.json` → cbDocOpen 渲染摘要；:8765 `GET /api/eval/live` → 状态行闸门通过数（只抄返回值） | 无新端点 |

### H.5 借鉴来源（pattern-only）

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| openai/codex `slash_command.rs` / `command_popup.rs`（github.com/openai/codex） | Apache-2.0 | 输入 / 弹浮层、按名过滤、命令行=名称+一句描述、别名不重复展示、Esc 关闭记忆 token |
| VS Code Command Palette（code.visualstudio.com、issue #1964） | 文档 pattern-only | 模糊过滤必须带模糊排序（前缀>子串>子序列）；全程键盘可达；最近项前置 |
| Raycast Manual：Search Bar / Arguments / Snippets | 文档 pattern-only | 别名直达；参数 placeholder 提示；子菜单 Esc=返回上一级 |
| GitHub Saved replies / Issue templates | 文档 pattern-only | 模板选择器（名称+描述）；选中=插入带占位草稿，先编辑后提交 |

## 附录 I：空态与三步新手引导（ux round10 定稿）

> R10 落地「引导」门面（§4 路线图 R10）：评委/试用者打开页面 30 秒内知道
> **这是什么、能干什么、第一步点哪**。组件两端同构 vanilla 实现
> （:8765 `demo/static/index.html`+`app.js`+`styles.css`；:8000 `frontend/workbench.html` Vue 内联），
> 零 CDN、零外链、全 `--cb-*` token；示例卡动作一律**预填不自动发送**（承附录 F.3 红线）。

### I.1 空态卡（无任何会话/无结果时）

结构（shadcn/ui Empty / Tailwind UI empty state 四段式 pattern-only：图标+定位句+主动作+诚实小字）：

```
.cb-empty
  .cb-empty-media    "CB" 图标块（--cb-blue 底白字）
  .cb-empty-title    土木版 Codex：66 岗工作台
  .cb-empty-desc     工具算数、模型只路由。输入任务，或点一张示例卡预填（不会自动发送）。
  .cb-empty-cards    三张示例任务卡（等宽 grid，≤768 单列；点击=预填输入框，不发送）：
    tone-blue   装  /pack 装一张票      sim_materials 票 → 装柜单草稿，柜数由 tools 算（预填真实小票 small_one_container）
    tone-strong 标  /bid 解析一段招标    资格条件与废标项清单 · P0 资格须人工确认
    tone-orange 安  /safety 出安全交底   工友班前三分钟白话，一条一个动作
  .cb-empty-note     产出永远是 AI 草稿，高风险岗需人工确认。
```

- :8765 挂在 `#log`（原一行 `.welcome` 欢迎语升级为本卡，**保留 `.welcome` 类**——发送首条消息时沿用既有移除逻辑，空态卡即 Codex 历史流的第 0 号 cell）；示例卡点击走 `cbEmptyPrefill()`，复用附录 H `cbSlashTemplate` 生成草稿。
- :8000 挂在 `workspace-inner`（`v-if="!hasAnyResult"`，简洁/完整两种模式都显示，位于演示剧本/empty-hero 之后）；点击走 `cbEmptySample()` → 左栏 composer 预填（`cmdApplyDraft`），不发送。
- 三卡预填文案=附录 H.3 模板原文，`<待填>` 占位数字一概不预编。

### I.2 三步引导 checklist（首访一次性）

- 存储：`localStorage["cb_onboarded_v1"]` = `{s:[b,b,b], done, dismissed}`；键不存在=首访自动弹出；✕ 关闭=不再自动弹出；右上角 **?** 按钮（:8765 顶栏 `#onboardHelp` / :8000 顶栏 `@click="cbObReopen"`）随时重开；全部完成 → 1.2s 后自动收起。
- 三步与打勾条件（只抄真实交互事件，不靠估算）：

| 步 | 文案 | 打勾触发（:8765） | 打勾触发（:8000） |
| --- | --- | --- | --- |
| ① | 输入任务，或点一张示例卡（预填，不自动发送） | `#input` input 非空、`data-fill` chips、指令面板/最近任务 `cbCmdApplyDraft`、示例卡 `cbEmptyPrefill` | `watch: userInput` 非空（打字/示例卡/面板预填同源） |
| ② | 看时间线跑完：8 阶段收口 ✓ | `streamChat` done 事件 | `onStreamEvent` type=`done`/`replay_done` |
| ③ | 在审批卡点确认 · 或文书预览 / 下载 .md | 审批卡 `cb-apr-confirm` 点击、`openDeliverable`、交付物卡「下载」、预览层「下载 .md」（`docpreview.js` 调 `global.cbObStep(3)`） | `cbAprConfirm`（显式确认并拼柜）、`openDocArtifact`、预览层「下载 .md」（`vendor/cb-doc.js` 同构钩子） |

- 未完成的下一步高亮蓝边（`li.now`），已完成划线灰化（`li.on`）；卡脚常驻诚实句「产出永远是 AI 草稿，高风险岗需人工确认 · 全部完成自动收起」。
- R10 路线图验收「新用户 3 分钟内完成首跑（demo_one_shot 同路径）」：示例卡预填的 `/pack small_one_container` 即 demo 同款真实数据路径，发送即走 `runTeamA`/`/api/chat` 正常链路，与演示共用一条管线。

### I.3 网关兜底空态（加载失败 / 后端未起）

触发条件与文案（纠偏卡三段式：发生了什么 + 为什么 + 现在能做什么，承附录 F；命令一键复制）：

| 端 | 触发 | 呈现位置 | 启动命令（复制按钮） |
| --- | --- | --- | --- |
| :8000 `workbench.html` | `refreshHealth()` catch（/api/health 不可达）或网关自检 DOWN 且无任何结果 | 工作区顶部 `.cb-empty-down`（合规红边） | `python -m uvicorn gateway.app:app --port 8000` |
| :8000 `index.html` | `loadExperts()`（/api/experts 探测）失败；探测恢复自动撤卡 | 页头下方纠偏卡（--err-bg） | 同上 |
| :8765 | `boot()` /api/health 失败（此前为裸 unhandled rejection，本轮修复） | `#log` 顶部 `#cbDownCard`（带「重试检测」自愈按钮） | `cargo run --release --bin civil-workbench`（或 zip 内 start-workbench.bat） |

- 卡上一律带「重试检测」：:8000 重调 `refreshHealth`/探测，:8765 重拉 /api/health，成功即撤卡并提示「后端已恢复」。
- 复制走 `navigator.clipboard`（127.0.0.1 安全上下文可用），失败回退为提示手选，不静默。

### I.4 借鉴来源（pattern-only）

| 来源 | 许可 | 借什么 |
| --- | --- | --- |
| shadcn/ui `Empty` 组件（ui.shadcn.com/docs/components/base/empty） | MIT | 四段结构：Header→Media(icon)→Title→Description→Content(主动作)；图标块居中、一句话定位 |
| Tailwind UI / Tailwind Plus empty state | 文档 pattern-only | 图标+标题+一句描述+单个主 CTA；列表空态即引导 |
| PostHog / Appcues 首访 checklist | 文档 pattern-only | 3 步 checklist：逐项打勾、全完成自动收起、✕ 可跳过、随时可重开；步骤=产品真实动作 |
| openai/codex 首启欢迎（session header + 单 composer 聚焦） | Apache-2.0 | 欢迎区只占一屏不堆字；首条输入前不产生历史噪音；空态即第 0 号历史 cell |
| NN/g Empty-State / Onboarding 指南 | 文档 pattern-only | 空态=教育时机：说清"为什么空"和"下一步做什么"，不放占位图表 |
