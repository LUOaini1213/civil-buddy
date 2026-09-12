# Civil Buddy 产品完善规划

> **切片。** 全量产品规划书：[product-plan.md](product-plan.md)。  
> 本文只勾选文档 / KB / MCP / Skill 执行刀。  
> 2026-08-19 建立；2026-09-12 更新专业文书完成记录 · **不定时限** · **不准空转**
> 废止：[overnight-eval-iterate-2026-08-19.md](overnight-eval-iterate-2026-08-19.md)（sleep 评测环）

本文件是产品完善的**执行规划**。每一条都必须交出：代码或文稿 + 驱动已上线入口的测试 + 本表勾选。评测是刀后的证明，不是工作本身。

- [x] 2026-09-12 工作台使用流程：可靠启动、无 Key 本地起草、模型设置、PDF/Office 附件、会话及岗位恢复、文书快照/下载、失败与签认等待反馈。入口 `civil app`；验收 `scripts/test_workbench_flow.py`、`test_app_launcher.py`、`test_workbench_settings.py`、`test_workbench_uploads.py`，并有实际浏览器验收。日报字段内容另由 `test_daily_report_content.py` 验证。
- [x] 2026-09-12 使用缺口补齐：可编辑 Word、后台协作取消、任务 ZIP 备份与跨目录导入、项目索引跨进程事务和损坏保护。回归入口 `test_word_export.py`、`test_workbench_cancel.py`、`test_session_bundle.py`、`test_project_storage.py`。导入只建新任务并清空高风险授权；取消保留实际文书。

对照（不替代本文）：

- 运行时内核：[product-improvement-handbook.md](product-improvement-handbook.md)
- 66 岗独有工具下一刀：[post-horizon-2026-08-17.md](post-horizon-2026-08-17.md)
- MCP 三原语长程：[kb-mcp-horizon.md](kb-mcp-horizon.md) · [yibiao-mcp-map.md](yibiao-mcp-map.md)
- Grok skill：`skills/civil-buddy/SKILL.md`
- 装箱引擎 skill 契约：`docs/skills/README.md`

---

## 0. 身份与空转定义

### 我们是

土木企业 **内部讨论 AI 起草搭子 + 证据工作台**：

| 层 | 职责 |
|----|------|
| Skill | 怎么起草（禁语、辖区、确认句、十一章） |
| MCP | 能调什么（KB、招标解析、solver 投影、写盘门） |
| 知识库 | 岗可见的官方标题与口径，不是规范全文 |
| 技术文档 | 人能按文档把产品跑起来、接上宿主、改一刀 |
| 运行时 | understand → Scheduler → ToolEngine → 沙箱 |

默认产出永远是 **AI 草稿**。`submit_blocked=true`。不判定可投标，不判定可以开工。

### 空转（禁止再做）

| 空转 | 为什么不算完善 |
|------|----------------|
| 定时 sleep 再跑一遍已绿的测试 | 没有新产物 |
| 卡死「明早 8:30」当完成条件 | 墙钟不是交付 |
| 联网抓门户但不改 KB/文档/工具 | 日志不是产品 |
| 66 岗再写一遍人格 prompt | 手册已否决 |
| 只改总判句「部分合格→合格」 | 行为没变 |
| 再写一份与本文重复的「下一步」而不改文件 | 文档通胀 |

一轮工作结束时，必须能指出 **新的路径**：某个 `SKILL.md` / `web-knowledge.md` / MCP tool / API / 测试脚本。指不出路径 = 没做。

### 不定时限

按刀完成，不按小时完成。可以连续做，也可以隔天做。停手条件只有：本文件各工作包的验收勾上，或人明确改范围。

---

## 1. 四条产品面（不要再混）

```
用户 / Grok / Claude / Cursor
        │
        ├─ Skill（SOP）     skills/civil-buddy/** 、docs/skills/**
        ├─ MCP（动作）      civil-mcp stdio · demo/mcp_surface.py · /api/mcp/*
        ├─ 知识库（只读）    demo/kb/** （岗） · knowledge_base/** （装箱引擎）
        └─ 技术文档（给人）  README · docs/civil-buddy/** · docs/ARCHITECTURE.md
                │
                v
        运行时  packing_assistant/runtime + workbench + gateway
```

| | Skill | MCP | 知识库 | 技术文档 |
|--|-------|-----|--------|----------|
| 解决 | 怎么写、何时停、确认句 | 可发现/可调用的工具与 `kb://` | 岗可见口径与官方标题 | 人如何安装、接宿主、改一刀 |
| 初始现网（2026-08-19） | 一份土木 SKILL.md（V1 只写满 construction）；装箱另有契约表 | tools/resources/prompts 名齐；Python HTTP 的 **tools 几乎只有 pack-ship** | 66 岗目录齐，多数是 08-14 摘录 + 骨架 faq/outline | 装箱文档厚、土木文档散、65/66 打架 |
| 完善后 | SOP 与 66 岗名册对齐；渐进披露；V1 施工真能出十一章+扫描 | 真 Host 能 `tools/list` 到 KB+招标+装箱；越权拒绝 | 分层不泄兄弟私库；门户标题单一来源；缺数 UNSPECIFIED | 一张图能指到模块；入口与 API 不互相否定 |

装箱 `knowledge_base/` 与岗 `demo/kb/` **两套库**：前者给 solver/harness 检索，后者给专家起草。pack-ship 岗只抄官方标题 + 指向引擎库，不把 xyz 写进岗 KB。

---

## 2. 初始现状测绘（2026-08-19 历史快照）

以下百分比与缺口是规划建立时的记录，不代表当前状态。2026-09-12 的专业文书实现为 66/66；当前本地发布验收状态见 §8 和 product-plan §7.2/§11。历史门户标题不自动转为新起草器的适用依据。

### 2.1 已经能跑、不要改坏

1. 默认面 `POST /api/agent` 与 `POST /api/turn`：提问不写盘。  
2. 66 岗同一套 chat/run；高风险确认句。  
3. 主线 C 招标矩阵 + `tender.handoff.json`（P1-1）+ 再审。  
4. pack-ship 投影 solver；断线四字段字面 `UNSPECIFIED`。  
5. 应用沙箱：写根 / `.env` / 通用 spawn。  
6. `GET /api/eval/live` 离线针（GST 9%、Fire Code、CTU、GeBIZ≠评分）。  
7. Python `GET /api/mcp/resources|prompts`；Rust `civil-mcp` stdio 源码在。  
8. `skills/civil-buddy` 硬规则 + 十一章 + `scan_forbidden_inventions.py`。

### 2.2 缺口（完善对象）

| 面 | 完成度 | 具体洞 |
|----|--------|--------|
| 技术文档 | 40% | 名册已改 66；`harness.md` 仍是 Rust 评测路由与 Python `/api/agent` 两套；没有 GETTING-STARTED / MCP.md / SKILLS.md / KB.md |
| 知识库 | 目录齐 + K4 内容闸 | 66/66 四件套；faq≥5、README 字段表、`search_kb` 命中本岗（`test_kb_k4_depth.py`）。独有写盘栏位仍按 product-plan §15 |
| MCP | 40% | 三原语宣告了；**可调用 tools 在 Python 面几乎只有 pack-ship**；Grok 宿主已挂 `civil-bid` / `civil-buddy` / `civil-commercial` / `civil-construction` 四个 stdio，其余 12 大类未挂；无仓内 `mcp.json` / `config.toml` 样例；无 Python stdio 回退（无 MSVC 时 Host 挂不上 Rust 二进制） |
| Skill | 40% | Grok skill 专家 id 只有 6 个且 V1 只写满 construction；工作台是 66 岗。两套名册未在 skill 里讲清。装箱 `docs/skills/` 与 Grok skill 同叫 skill，接 Host 的人会混 |
| 独有写盘 | 25% | bid 三岗 + pack-ship 已有真栏位；其余岗 `write_deliverable` 骨架 md。post-horizon 每岗下一刀已写好，本文不复制 66 遍 |

### 2.3 数字锁死

- 专家：**66**（`workbench/seed.json` + `yibiao-map.json`）。文档里的 65 一律改 66。  
- 大类：**16**。  
- 易标五段：parse → outline → qa → kb → write。  
- MCP 规范对照：2026-07-28 tools / resources / prompts。

---

## 3. 完善成功的样子

一个人（或一个 MCP Host）能做到：

1. 打开 `README.md` 按一页指令起 8000 + 8765，知道 Skill 与 MCP 各干什么。  
2. 把 `civil-mcp --pack bid`（或 Python stdio 回退）写进 Host 配置，`tools/list` 看到 `search_kb` / `tender.parse` / `bid-parse__extract`，`resources/list` 只有 bid 可见层。  
3. `/civil-buddy` 写临边讨论提纲：十一章、确认句、扫描器、无「可以开工」。  
4. 问 GST → 只聊，回复含 IRAS 页述 **9%**，不写盘。  
5. 出装箱作业单 → 数字来自 solver 或字面 `UNSPECIFIED`。  
6. 任意岗 `kb://` 读不到兄弟私库。

行业总判仍可以是 **部分合格**（不做签认/递交）。「产品完善」指起草搭子的文档、库、协议、SOP 齐，不指变成投标机器人。

---

## 4. 工作包（按依赖，不按日期）

规则：同一时间只做 **一个工作包里的一刀**。刀绿了才开下一刀。评测脚本只在刀后跑。

```
D0 文档收口 ──► D1 技术文档完整
                 │
                 ├─► K 知识库产品化（schema + 门户单一来源 + 检索闸）
                 ├─► M MCP 可被真 Host 调用（stdio + 工具表 + 样例配置）
                 └─► S Skill 名册对齐 + 施工 V1 做实
                          │
                          └─► P 岗独有写盘按 post-horizon（已有下一刀）
```

D0 阻塞一切。K / M / S 可穿插，但每刀仍串行提交。P 在 M 的 `write_deliverable` 与 K 的可见层稳定之后再富化，避免写盘栏位对不上 KB。

---

## D0 · 文档收口（先做，否则永远两套真相）

**产物**

| 文件 | 改什么 |
|------|--------|
| `README.md` | 66 岗；两入口；Skill vs MCP 各一句；链到本文 |
| `docs/README.md` | 土木文档置顶本文；65→66；标明装箱文档是引擎 |
| `docs/civil-buddy/enterprise-experts.md` | 65→66；状态列与 seed 一致 |
| `docs/civil-buddy/harness.md` | 补 Python `/api/agent` `/api/eval/live`；Rust 路由标「工作台」 |
| `docs/civil-buddy/yibiao-mcp-map.md` | 65→66 |
| `skills/civil-buddy/SKILL.md` | 开篇声明：Grok skill V1 = 6 专家路由（construction 写满）；工作台 66 岗走 demo/workbench，不是本 skill 一次全加载 |
| 本文 | 唯一「产品完善」入口；其它 next-steps 只链过来 |

**验收**

```
rg "65 专家|65 岗|65 名" docs skills README.md
# 只允许历史归档与「已废止」页出现
```

仓库内检索不得再把 65 当成现网名册。

**不做：** 重写装箱算法文档；删 `docs/archive`。

---

## D1 · 完整技术文档（给人用的说明书，不是研究笔记）

新建（短、可执行、与代码同路径）：

| 新文档 | 内容（一页能跑） |
|--------|------------------|
| `docs/civil-buddy/GETTING-STARTED.md` | 起 8000/8765；填 `demo/.env`（不提交）；打开默认面问 GST；召唤 pack-ship |
| `docs/civil-buddy/PROTOCOL.md` | chat/run/both；ToolEngine 错误码；沙箱根；HITL 确认句原文 |
| `docs/civil-buddy/MCP.md` | stdio 命令、`--pack` / `--expert`、URI `kb://`、Host 配置片段、与 HTTP `/api/mcp` 对照表 |
| `docs/civil-buddy/SKILLS.md` | Grok skill 目录树；装箱 `skills_registry` 对照；禁止把装箱 skill 名当 MCP tool 名 |
| `docs/civil-buddy/KB.md` | `demo/kb` 分层；`knowledge_base/` 引擎库；谁可读谁不可写 |

`GETTING-STARTED.md` 里的命令必须是本机刚跑过的。过时即文档红。

**验收：** 新人只读 GETTING-STARTED + MCP.md 能把一个 Host 的 `tools/list` 打出来（见 M1）。`python scripts/test_docs_completion.py` 检查：上述五篇存在、含 66、含 `submit_blocked`、不含「可以投标」当能力。

**不做：** 再写一篇「与易标对比」营销文；把 `docs/research/` 搬进必读。

---

## K · 知识库产品化

岗库已经「有文件」。完善 = **有 schema、有单一事实源、有检索闸**，不是 16 类全量 embedding。

### K1 库 schema（强制目录契约）

每个专家目录必须：

```
demo/kb/<category>/<id>/
  README.md          # 本岗产出、风险、独有工具名
  faq.md             # 白话问答；禁语出现时必须是否定句
  outline.md         # 成稿章节，缺数 [A001]
  web-knowledge.md   # 官方标题 + URL + 页更；禁止条款号
```

大类 `_shared/` 与 `company/` 保持现结构。  
**验收：** `python scripts/test_kb_schema.py` 遍历 66 岗，缺文件即失败。先允许内容短，不允许缺文件。

### K2 门户标题单一来源

GST 9%、Fire Code 2023、CTU Code 2014、GeBIZ≠评分、APPBCA-2026-12 只在 `demo/kb/company/web-portals.md` 写「权威句」。各岗 `web-knowledge.md` **链到该页或抄同一句**，禁止各岗各写一个税率。

**验收：** `GET /api/eval/live` 针改读 company 页；岗文件若写 GST 必须含 `9%`。抓 IRAS 失败不得删 9%。

### K3 检索与隔离当产品

| 规则 | 测试 |
|------|------|
| `list_kb(expert)` 不含兄弟私库 | `test_mcp_surface.py` 扩一条：bid-parse 看不见 `method-hazard/` |
| `kb://` 越权返回拒绝句，不 404 装成空库 | 已有雏形，写成必测 |
| 文件名加权检索 | 已有则挂到 `scripts/test_kb_search_filename.py` 作为完善闸 |

**不做：** 规范全文进仓；16 类季更 embedding；把 packing `knowledge_base/` 合并进 demo/kb。

### K4 内容富化顺序（有 schema 之后）

2026-08-28：**内容闸已对 66/66 收口**（faq≥5、README 字段表、outline 缺数栏、`search_kb` 命中本岗）。验收 `python scripts/test_kb_k4_depth.py`。K4 只证明知识库深度；T040–T047 的专业实现另按逐岗字段与真实文书测试登记，不能用本闸一行代替。禁止 16 类 embedding 季更。

---

## M · MCP 完善（让 Host 真能调）

现网最大洞：**协议名齐，可调用面窄**。Grok 已连接 `civil-bid` / `civil-buddy` / `civil-commercial` / `civil-construction`，但 Python HTTP `list_tools` 在非 pack-ship 时返回 `[]`。

### M1 Python stdio MCP（无 MSVC 也能挂 Host）

**产物：** `demo/mcp_stdio.py`（或 `packing_assistant/mcp_stdio.py`）实现 newline JSON-RPC：`initialize` / `tools/list` / `tools/call` / `resources/list` / `resources/read` / `prompts/list` / `prompts/get`。过滤参数与 Rust 相同：`--pack` / `--expert`。

**验收：** `python scripts/test_mcp_stdio.py` 用管道打 `tools/list`，pack=bid 时看到 KB + 招标工具，看不到 `pack-ship__plan`。

### M2 工具表（第一批必须可 call）

| name | 谁可见 | 行为 |
|------|--------|------|
| `search_kb` `read_kb` `list_kb` | 通用 | 只读当前层 |
| `write_deliverable` | run 且非 chat | 走 ToolEngine + 沙箱 |
| `tender.parse` | 经营岗 / bid-parse | 矩阵 + handoff；`submit_blocked` |
| `tender.review` | 成稿后 | 不改 can_fit |
| `bid-parse__extract` | 仅 bid-parse | 落 extract + `tender.handoff.json` |
| `bid-compliance__gaps` | 仅 bid-compliance | 三列 |
| `bid-tech__expand` | 仅 bid-tech | 无评分点不套模板 |
| `pack-ship__list/plan/export/health` | 仅 pack-ship | 投影，xyz 永不手写 |
| `*__scan_forbidden` | 本大类 | 写盘后 |

chat 调写盘 → `permission_denied`。兄弟调独有 → 拒绝。

**验收：** `scripts/test_mcp_surface.py` 扩：bid-parse list 含 extract、construction list 不含 extract、chat 调 write 拒绝。

### M3 Host 配置进仓库

`docs/civil-buddy/MCP.md` + 样例 `docs/civil-buddy/mcp-host.example.toml`：

```toml
[mcp_servers.civil-bid]
command = "python"
args = ["demo/mcp_stdio.py", "--pack", "bid"]

[mcp_servers.civil-construction]
command = "python"
args = ["demo/mcp_stdio.py", "--pack", "construction"]
```

有 `civil-mcp.exe` 时文档并列 Rust 命令。不要求用户装 MSVC。

**不做：** 自研第二个协议；horizon D 分页/订阅（仍等真 Host 先 list/call 成功）；把 16 个 pack 一次全挂进默认 Host（先 4 个已挂的大类做实）。

### M4 Prompts

在 bid / pack-ship 之外补：

- `civil.construction.scheme`（确认句、十一章、禁止开工断言）  
- `civil.method-hazard.judge`（WSH/PTW 默认 SG，不套 37 号令）  
- `civil.finance.tax-calendar`（页述 9%，税额待填）

prompt 文本不教「可投标 / 编 xyz / 编条款号」。

---

## S · Skill 完善

### S1 两套 skill 必须在 SKILLS.md 拆开

| 名称 | 路径 | 给谁 |
|------|------|------|
| Grok 土木 skill | `skills/civil-buddy/` | `/civil-buddy` 起草 SOP |
| 装箱引擎 skill | `docs/skills/` + `packing_assistant/skills_registry.py` | 成箱/拼柜节点契约 |
| MCP | `civil-mcp` / `mcp_stdio.py` | 动作，不是 SOP |

Grok skill **不**在 V1 里 `use_tool` 调 MCP（保持 skill 可离线出十一章）。V2 再写「可选只读 MCP」段落，与现网运行时对齐，删掉「V1 不调用 MCP」这种与仓库事实打架的句子——改成：

> Skill V1 离线可完成 construction 草稿。工作台 / Host 需要 KB 与装箱数字时走 MCP，不把 solver 数字写进 skill 正文。

### S2 把 construction V1 做实（skill 自己宣称的完成线）

对照 `SKILL.md` Step 5，现在缺的是**工作台/agent_loop 与 skill 同一套十一章+扫描**，不是再写一篇 SKILL。

**产物：**

- `expert_turn` / agent_loop 对 `construction`：读 `skills/civil-buddy/references/scheme-outline.md` 出 11 章，而不是泛化 `_draft_markdown`。  
- 写盘后跑 `scan_forbidden_inventions.py`，非 0 不得报成功。  
- 无确认句 0 份稿。  

**验收：** `python scripts/test_construction_skill_path.py`：chat 不写；未确认 HITL；确认后 11 个标题都在；禁语扫描 0。

### S3 Grok skill 专家文件

`references/experts/` 现有 6 个。V1 只要求 construction 写满——**保持**。补一句：另外五个文件允许提纲级，不假装与 66 岗一一对应。66 岗 SOP 的「下一刀」在 post-horizon，不塞进这一份 SKILL.md（避免巨无霸）。

**不做：** 66 份 Grok skill；把易标 AGPL 流程抄进 SKILL。

### S4 装箱 skill 表与 MCP 对账

`docs/skills/README.md` 每个 Skill ID 加一列「对应 MCP tool（若有）」。没有 MCP 的保持「仅引擎内部」。禁止给 `bin3d.pack` 再做一个会让模型改坐标的 MCP。

---

## P · 岗写盘（Skill/MCP/KB 稳定后）

逐岗状态以 [product-plan.md](product-plan.md) §7.2 为准；[post-horizon-2026-08-17.md](post-horizon-2026-08-17.md) 补充专业边界，不另开当前队列。

本规划只加一条纪律：每岗独有工具必须：

1. 在 MCP `tools/list`（该 expert）可见；  
2. 栏位来自 outline.md / KB，缺数 `[A001]` / `UNSPECIFIED`；  
3. `test_expert_turn.py` 对该 id 的 run 能断言 **至少一个栏位不是通用骨架句**。

T030–T047 已逐岗完成。设计 20 岗的专业字段与实际 Markdown/Excel 测试逐行列于下表；basic 37、services 20、specialties 28、infrastructure 20，共 105 项回归通过。统一检查 40/40 已通过（`output/workbench-complete-full-check.log`）；L2 为 66/66，L3 仍仅 pack-ship，不新增设计求解或 IFC 引擎能力。

| 批次 / 岗位 | 专业实现与保留边界 | 回归证据 |
|-------------|--------------------|----------|
| T044 / architecture ✅ | 单体总平面、分区面积与功能、消防分区及疏散用户值、无障碍、竖向、节能和专业接口；缺面积、宽度不推算 | `scripts/test_design_basic_drafts.py` |
| T044 / structure ✅ | 单体体系、构件荷载与组合、材料、基础输入、抗震资料及复核清单；承载力、配筋和截面计算结果保持 UNSPECIFIED | `scripts/test_design_basic_drafts.py` |
| T044 / geotech ✅ | 孔号与分层、c/φ/水位和来源、勘探试验、地基比选、监测及提资；孔层缺项不借值，不替正式勘察报告 | `scripts/test_design_basic_drafts.py` |
| T044 / facade ✅ | 幕墙体系、风压与分格、预埋后锚固、气密水密变位、防火防雷、加工检测和维护接口；不选厚度或签验收结论 | `scripts/test_design_basic_drafts.py` |
| T045 / plumbing ✅ | 系统水源/水压、市政接驳、室内出户及井标高、给排水分区、雨水回用、消防水资料；管径和选泵计算待核 | `scripts/test_design_services_drafts.py` |
| T045 / hvac ✅ | 室内外参数、逐时冷热负荷、风水系统、防排烟联锁、机房竖井与消声保温；主机、风管及排烟量不代算 | `scripts/test_design_services_drafts.py` |
| T045 / electrical ✅ | 市政电源、容量和负荷系数、变配电用户方案、照明、防雷接地、线路及消防/弱电接口；不选变压器或电缆 | `scripts/test_design_services_drafts.py` |
| T045 / fire-protect ✅ | 救援条件、防火分区、疏散避难、消防水、防排烟、报警联动、电气及报审目录；不作审图通过或放行结论 | `scripts/test_design_services_drafts.py` |
| T045 / steel ✅ | 构件体系与跨度、荷载、材料规格、螺栓焊缝、稳定支撑、防腐防火及加工安装接口；截面和连接计算未执行 | `scripts/test_design_services_drafts.py` |
| T046 / landscape ✅ | 软硬分区、竖向灌排、铺装及苗木规格数量、顶板覆土、室外设施和消防交通接口；未给苗木表不选规格 | `scripts/test_design_specialties_drafts.py` |
| T046 / interior ✅ | 房间地墙顶及隔墙、防水材料厚度上翻、防潮隔声、门窗五金、天花开洞和外窗收口；只抄用户样板资料 | `scripts/test_design_specialties_drafts.py` |
| T046 / intel-weak ✅ | 子系统范围、点数及品牌、桥架路由、点位关联、供电 UPS 接地与消防网络接口；不编品牌或布点 | `scripts/test_design_specialties_drafts.py` |
| T046 / civil-defense ✅ | 防护单元等级及平战功能、口部/设备归属、通风滤毒超压、给排水和转换接口；不互换 CN/SG 概念或代审图 | `scripts/test_design_specialties_drafts.py` |
| T046 / hydraulic ✅ | 水工对象、水文断面和地勘孔、堤防护岸、闸泵用户参数、导流度汛和观测；无水文地质不选尺寸或流量 | `scripts/test_design_specialties_drafts.py` |
| T047 / port ✅ | 泊位船型、水位波浪潮流、结构比选、前沿尺度、航道回旋水域、装卸堆场与水利接口；不计算桩长或靠船力 | `scripts/test_design_infrastructure_drafts.py` |
| T047 / municipal ✅ | 路段桩号、平纵横断、路面结构、排水标高、管线权属及导改接口；不拆算车道宽或选路面厚度 | `scripts/test_design_infrastructure_drafts.py` |
| T047 / bridge ✅ | 桥位跨径及桥型比较、上下部结构、支座桥面、水文通航抗震及施工接口；不锁最优桥型或计算钢束桩长 | `scripts/test_design_infrastructure_drafts.py` |
| T047 / tunnel ✅ | 用途净空、工法地层、开挖支护、防水接缝、监控量测、洞口及机电防灾接口；支护参数和监测阈值待核 | `scripts/test_design_infrastructure_drafts.py` |
| T047 / traffic ✅ | 交通影响/施工导改任务、调查来源与独立情景、组织及标志信号、仿真资料和指标；未运行仿真或优化配时 | `scripts/test_design_infrastructure_drafts.py` |
| T047 / design-coord ✅ | 图纸版本、会审问题、提资责任期限、变更记录、逐条决议和闭环证据；不代签发，不内置审批面积阈值 | `scripts/test_design_infrastructure_drafts.py` |

新设计稿的引用只来自用户资料且标为未核验；未知辖区 UNSPECIFIED，DUAL 的依据与接口分栏。历史硬编码官方版本、日期和阈值不属于此次自动文书功能，也不据本轮代码修改声称已复核法规范。

---

## 5. 每刀工作流（替代过夜空转）

```
1. 从本文取下一未勾选刀（只要一刀）
2. 改最少文件
3. 跑该刀验收脚本 + 快闸：
     test_understand.py
     test_sandbox.py
     test_agent_loop.py
     test_mcp_surface.py
     （刀相关脚本）
4. 绿 → 更新本文勾选 + next-steps 一行 + commit
5. 红 → 修好或回滚；禁止带着红测试「先睡一晚」
```

联网评测：只在改了官方标题 / GST / Fire Code / CTU / GeBIZ 口径之后做。日常不过 IRAS。抓失败保留 KB 9%。

---

## 6. 明确不做（完善时仍有效）

GeBIZ 代交、法定签认、十万字写标、标书查重产品化、模型手写 xyz/条款号、中标率 +N%、并 OpenBidKit AGPL、16 类知识库全量 embedding 季更、内核 Landlock、Grafana 必选、用睡眠循环冒充迭代、用截止钟点冒充交付。

---

## 7. 勾选表（落地时改本文，不要另开第三份「下一步」）

| 刀 | 状态 | 验收入口 |
|----|------|----------|
| D0 65→66 与入口收口 | ✅ | README / docs 索引 / yibiao-mcp-map / skill 开篇已 66；历史评测页可留 65 |
| D1 GETTING-STARTED / PROTOCOL / MCP / SKILLS / KB | ✅ | `python scripts/test_docs_completion.py` |
| D2 全量产品规划书 | ✅ | `docs/civil-buddy/product-plan.md` |
| K1 66 岗目录契约 | ✅ | `python scripts/test_kb_schema.py` |
| K2 门户标题单一来源 | ✅ | 五针 company（T003）+ 岗 GST/CORENET 扫描（T007/T008） |
| K3 kb:// 隔离 + 文件名检索闸 | ✅ | `test_mcp_surface.py` + `test_kb_search_filename.py` + `test_kb_k4_depth.py` |
| K4 66 岗 faq/字段表 | ✅ | `python scripts/test_kb_k4_depth.py`；独有写盘不在本刀 |
| M1 Python stdio MCP | ✅ | `python scripts/test_mcp_stdio.py` |
| M2 工具表（KB+招标+装箱+扫描） | ✅ | pack=bid 含 tender.parse，不含 pack-ship__plan |
| M3 Host 样例 toml | ✅ | `mcp-host.example.toml` |
| M4 construction / 危大 / 税务 prompts | ✅ | `civil.construction.scheme` 等 |
| S1 两套 skill 拆开写清 | ✅ | SKILLS.md |
| S2 construction 十一章 + 扫描接 turn | ✅ | `python scripts/test_construction_skill_path.py` |
| S3 skill 文案与 66 岗关系 | ✅ | SKILL.md 开篇 |
| S4 装箱 skill↔MCP 对账 | ✅ | SKILLS.md + docs/skills/README.md |
| P 专业文书 | ✅ 66/66 | §P 逐岗字段；四个 `test_design_*_drafts.py`；本地发布包另验收 |

P0 运行时、P1-1 handoff、Agent 循环+沙箱、pack-ship 投影：**已做**，见 handbook / next-steps。不要在完善文档面时把它们重做一遍。

---

## 8. 本地发布验收已完成，后续按用户试用反馈迭代

全量任务号与状态见 [product-plan.md](product-plan.md) §7.2 / §11 / §15。T044–T047 已有逐岗专业代码、105 项回归及统一检查证据，均已完成。**本地发布验收已完成**：最终源码构建、解压启动、隔离依赖、无 Key 聊天与生成、66 岗产物及门控、CSV/DOCX/XLSX 表格上传到实际 Markdown/Excel 下载恢复、HTTP 非法确认拒绝、重启恢复和进程清理。zip/SHA256 与 `acceptance.json` 存于包外验收目录。

0.5.0-preview 已按当前 66 岗源码完成本地验收。开发仓库运行 `python scripts/build_workbench_release.py --version 0.5.0-preview`，再运行 `python scripts/smoke_workbench_release.py dist/civil-buddy-python-workbench-0.5.0-preview.zip --python "独立虚拟环境路径/python.exe" --all-experts` 可复验；解释器可由 `--fresh-install` 首次建包内虚拟环境安装，不能借用系统 site-packages。

后续按用户试用反馈迭代。本地打包不表示 GitHub Release 已发布。延期项不自动成为新主链；行业历史总判和法定签认边界保持。
