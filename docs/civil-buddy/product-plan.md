# Civil Buddy 全量产品规划书

| 项 | 值 |
|----|----|
| 产品 | Civil Buddy |
| 版本 | 2026-08-19 · **联网审阅同日** |
| 仓库 | https://github.com/LUOaini1213/civil-buddy |
| 岗 / 大类 | **66 / 16**（`workbench/seed.json`） |
| 总判 | **部分合格**的内部起草搭子，不是签认/递交机器人 |
| 纪律 | **不定时限 · 不准空转**。墙钟和睡眠评测环不是交付 |
| 本文地位 | **产品规划唯一总入口**。切片文档只执行、不另开第三套「下一步」 |

**怎么用：** 改产品前先读 §1 边界、§10 不做、§13 联网口径。开工只取 **§15 主链头指针**（此刻 = §11 的 T039）。岗栏位细节可读 post-horizon 该 id；已做/未做以 §7 / §15 为准。  
2026-08-19：§1–§15 各派一子代理对照现网，结论已并入本文。

切片（从属于本文，不平行）：

| 切片 | 管什么 |
|------|--------|
| [product-completion-plan.md](product-completion-plan.md) | 文档 / KB / MCP / Skill 执行勾选 |
| [product-improvement-handbook.md](product-improvement-handbook.md) | Scheduler · ToolEngine · Memory · Trace |
| [post-horizon-2026-08-17.md](post-horizon-2026-08-17.md) | 66 岗每岗下一刀 |
| [product-mainline-tender-delivery.md](../product-mainline-tender-delivery.md) | 主线 C 投标×交付 |
| [GETTING-STARTED.md](GETTING-STARTED.md) | 人怎么把服务跑起来 |

废止：过夜 sleep 环 [overnight-eval-iterate-2026-08-19.md](overnight-eval-iterate-2026-08-19.md)。历史评测页可留 65 字样，现网名册是 66。

---

## 1. 产品是什么

### 1.1 一句话

土木企业用的 **内部讨论 AI 起草搭子 + 交付证据工作台**：模型理解与编排，工具算数与抽原文，运行时决定谁跑、何时停、谁确认、留下痕迹。

默认产出永远是 **AI 草稿**。`submit_blocked=true`。不判定可投标。不判定可以开工。

对照腾讯云 WorkBuddy（2026-08-20 官网 [intl.cloud.tencent.com/products/workbuddy](https://intl.cloud.tencent.com/products/workbuddy) · [codebuddy.cn/work](https://www.codebuddy.cn/work/)）：它卖「自然语言 → 规划步骤 → **授权文件夹里读写 Word/Excel** → 成品」，另加桌面壳、IM、100+ 通岗、云端托管。本仓对齐 **同一条回路里的本地成稿**：作业根（`CIVIL_JOB_ROOT`）里读本机表、另存 `.xlsx`，点名已有工作簿时只改 `CB草稿-*` 表；construction 模板 `.docx`。**不**做桌面壳、IM、100 个办公专家、云端 7×24、接管 Word/Excel 窗口、默认 `D:\layout`。成品永远是内部讨论草稿，不是可直接验收的签认件。

### 1.2 三条产品线（一个仓库，三个用户问题）

| 线 | 用户问题 | 入口 | 数字从哪来 |
|----|----------|------|------------|
| **工作台** | 这个岗怎么起草 | HTTP `127.0.0.1:8765`（无 `/civil-buddy` 路由）。Grok 斜杠 `/civil-buddy` 是 skill。MCP 必须 `--pack` 或 `--expert` | 岗 KB 官方标题；缺数 `[A001]` / `UNSPECIFIED` |
| **主线 C** | 这个标怎么应、货怎么交 | :8000 默认页 · `/api/tender/*` · `/api/agent` | 招标 `exact_text`；装柜 solver |
| **装箱引擎** | 这批料怎么装进柜 | :8000/workbench · `run_big_team` | 仅 tools：xyz / N0 / can_fit / mid50 |

pack-ship 岗 **不是第二套装箱**。它只投影本仓 solver 快照。断线四字段字面 `UNSPECIFIED`。

### 1.3 我们不是

| 禁止写成产品能力 | 原因 |
|------------------|------|
| GeBIZ 代交 / 自动中标 | 门户不是评分办法；无签章 |
| 法定专项方案 / PE·QP·RTO 签认件 | 须持证人员 |
| 十万字写标、标书查重产品化 | 易标 AGPL；会编业绩 |
| 模型**发明** xyz / N0 / 条款号 / GST 税率 | 官方句可抄（如 IRAS 页述 9%）；不可追责的是编造 |
| 中标率 +N% | 没有、也不许编 |
| 66 份人格戏服 | 岗是工具栏位，不是角色扮演。Grok skill V1 只有 6 个路由 id |

### 1.4 锁死的数字与句子

- 岗 **66**，大类 **16**（`workbench/seed.json`）。  
- 确认句：`我明白，将由持证人员签认`。闸是 `confirm_ok` / `p0_confirmed` **布尔**，只挡 **high** 写盘；不是从用户正文抽句。  
- GST：抄 IRAS 页述 **9%**。抓门户失败不得改口「官方没写 9%」。7%/8% 只可当历史升档。  
- GeBIZ **不是**评分办法。Fire Code **2023**。CTU Code **2014** 非强制（权威句在 `demo/kb/company/web-portals.md`；pack-ship 岗页链同一句）。  
- CORENET X 2026-10-01 强制范围以 APPBCA-2026-12 为准（GFA≥5,000 m²）。  
- pack-ship 断线四字段：`utilization` / `can_fit` / `mid50` / `系固待办` 字面 `UNSPECIFIED`。`xyz` 恒不投影。  
- 易标五段：parse → outline → qa → kb → write（`yibiao-map.json`）。不 fork AGPL。  
- 土木成稿/矩阵出口 `submit_blocked` 恒 true。不要和装箱 VGM 的 `blocked_unsigned` 混名。

---

## 2. 给谁用、怎么用

| 角色 | 典型任务 | 走哪条线 |
|------|----------|----------|
| 经营岗 / 投标助理 | 粘招标节选进矩阵、出交接、再审禁语 | 主线 C |
| 施工员 / 方案讨论 | 临边十一章提纲 | 工作台 construction · Grok skill |
| 物机 / 物流 | 铁架装柜证据 | pack-ship 投影；要真算去 /workbench |
| 财务 | 问 GST / 税率 | 默认面或 finance-tax **chat**；日历栏页述 9%、申报期空栏、税额待填（T004 ✅） |
| 宿主（Grok/Cursor/Claude） | `tools/list` + `kb://` | `demo/mcp_stdio.py --pack …` |
| 持证人员 | **不**用本产品代替签认 | 人在确认句之后仍要自己签 |

### 关键路径（必须永远能走）

1. 问「什么是 GST」→ `chat`、不写盘、回复含 **9%**。  
2. 「解析招标…」→ 矩阵行有 `exact_text`，`submit_blocked=true`。  
3. 选岗 `construction`，勾选 `confirm_ok`（不是把确认句糊进正文）→ 十一章 md，无「可以开工」。未勾选 0 份稿。  
4. pack-ship 无会话 `packing_summary` → 四字段 `UNSPECIFIED`；有注入/落盘快照则原样抄，`xyz` 永不编。先 delivery 再抄的 HTTP 联测见 T052。  
5. MCP **必须** `--pack bid` 或 `--expert`：list 到 `search_kb`/`tender.parse`，看不见 `pack-ship__plan`。裸起 stdio 会看见 pack-ship。  
6. `kb://<大类>/<兄弟id>/…` 与跨大类 `kb://construction/method-hazard/…`（bid-parse）→ 正文以「拒绝」开头，不是空 404（T023 ✅）。

---

## 3. 现网地图（2026-08-19）

### 3.1 仓库

```
workbench/            Rust 工作台 + civil-mcp stdio
demo/                 Python 工作台 :8765 + demo/kb + mcp_stdio.py
skills/civil-buddy/   Grok SOP（V1 六路由，construction 写满）
packing_assistant/    装箱 harness + runtime（Scheduler/ToolEngine/agent_loop）
gateway/ + frontend/  :8000 主线 C + /workbench
knowledge_base/       装箱引擎检索库（不是岗私库）
docs/civil-buddy/     土木产品文档（本文为总入口）
docs/                 装箱架构、主线 C、研究/归档
```

原则：**tools compute numbers; the model only routes.**

### 3.2 完成度（对人诚实）

| 面 | 约 | 已有 | 缺口 |
|----|----|------|------|
| 运行时 | 80% | Scheduler、ToolEngine、沙箱、`/api/agent`、Run 回放、Memory slot | 岗栏位仍多数骨架 |
| 主线 C | 80% | ingest/矩阵/handoff/再审/delivery；parse 走 ToolEngine；扫描 PDF 默认拒绝 | 资格栏仍人填 |
| 装箱引擎 | 80% | 大 Team A/B、3D、CoG、HITL | 非本规划主战场；禁止第二套 packer |
| MCP | 75% | Python stdio；bid 可见 KB+招标；pack-ship 投影；Host 样例 16 pack 可复制 | 默认仍挂 3 大类；分页/订阅延期 |
| Skill | 65% | SOP 与 66 岗关系写清；施工十一章接 turn；fill_scheme 失败则 `docx_pending` | 其余 5 个 Grok 专家仍提纲 |
| 岗 KB | 目录 100% / 写盘栏位 ~52% | **66/66** 四件套在盘；`test_kb_schema.py` 缺一即红 | outline 指针：construction→`scheme-11.md`，危大→`judge-card.md`。**真写盘 34/66**（+ worker-brief） |
| 工作台 66 岗 | 平台齐、栏位 34/66 | 同一套 chat/run | 其余 ~32 岗 `_draft_markdown` |
| 技术文档 | 80% | GETTING-STARTED/PROTOCOL/MCP/SKILLS/KB；Grok/Cursor 最小 Host；刀后快闸 | 研究笔记不得冒充必读 |
| 评测 | 75% | 离线闸 + `GET /api/eval/live` 五针（company 页）+ 岗 GST/CORENET 扫描 | 行业总判仍部分合格 |

行业评测总判保持 **部分合格**（[industry-agent-eval-2026-08-17.md](industry-agent-eval-2026-08-17.md)）。「合格 · 内部起草搭子」要默认面真装箱可抄 + 循环可回放 + eval/live **同时**成立，且由人改口，脚本不得改总判句。

### 3.3 已落地短刀（不要重做）

P0 ToolEngine/Scheduler/pack-ship 快照 · P1-1 handoff · P1-2 eval/live · P1-3 Memory · P1-4 Run 回放 · P1-5 危大判定书 · Agent 循环+沙箱 · D0 名册 66 · D1 五篇说明书 · M1–M5 Python stdio 与 16-pack Host 样例 · S1–S5 施工十一章 + fill_scheme/`docx_pending` · T001/K1 四件套闸 · T003 五针 · T007/T008 岗口径扫描 · T011 parse 走引擎 · T014 agent_loop handoff · T050 PDF 拒绝句 · T052 同 session 抄 can_fit · T062 刀后快闸。

---

## 4. 目标架构

```
                    用户 / Host
                         │
     Skill(SOP)     MCP(动作)     文档(人)
          \            |            /
           \           |           /
            v          v          v
              Agent 运行时
         understand → Scheduler
         ToolEngine → 沙箱 → audit
         Bus(进程内) → Run 回放
                │
     ┌──────────┼──────────┐
     v          v          v
   岗插件     主线C插件    装箱插件
  66 exclusive  tender.*    run_big_team
  demo/kb      handoff.json solver 快照
```

**现网诚实画法（不是目标已落地）：**

- **内核只在** `POST /api/agent`：`understand → Scheduler → ToolEngine.execute → 写盘沙箱 → audit_log + 进程内 Bus`。生产默认是 **steps 规划器**，不是 LLM 自由 tool-call。  
- **Skill / 文档不进循环。** MCP `tender.parse` 与 `POST /api/tender/parse`（含 `/file` `/files`）走 `ToolEngine.execute`（T011 ✅）。chat 意图拒写。  
- **66 岗 exclusive 已 `register` 进 ToolEngine。** pack-ship×4 仍投影 solver；其余独有名走 `run_named_exclusive`（HITL 仍在写盘前）。chat 调写盘 `permission_denied`。兄弟岗调独有同样拒绝。`write_deliverable` 只作沙箱底盘，agent_loop 默认调岗名工具。  
- **装箱是兄弟路径：** `run_big_team` 在 /workbench 与 delivery；pack-ship **只投影快照**，禁止在 turn 里再算几何。  
- **状态机已用边：** `pending→planning→acting⇄waiting_tool→done`，或 `planning→waiting_hitl`（本环不 resume 到 acting）。`reflecting` 合法但未用。  
- **错误码谁发出：** ToolEngine 发 `ok/permission_denied/invalid_args/timeout/circuit_open`。`max_steps`/`illegal_edge`/`session_busy` 出 Scheduler。字段字面 `UNSPECIFIED` ≠ 崩溃码 `unspecified`。  
- **回放两套：** `GET /api/runs/{id}` = Scheduler 内存身份；SSE `/replay` = 装箱 `trace.jsonl`。

错误码表见 [PROTOCOL.md](PROTOCOL.md)。T011 ✅：parse/file/files 与 MCP `tender.parse` 收进 `ToolEngine.execute`。

---

## 5. 五条产品面规格

### 5.1 技术文档（给人）

必读链：本文 → GETTING-STARTED → PROTOCOL / MCP / SKILLS / KB。  
装箱算法与比赛文案在 `docs/` 与 `docs/research/`，**非**土木必读。  
`docs/archive/` 只归档。

### 5.2 知识库

| 库 | 路径 | 规则 |
|----|------|------|
| 岗库 | `demo/kb/<大类>/<id>/` | 私库 + `_shared` + `company`；兄弟不可见 |
| 引擎库 | `knowledge_base/` | solver/harness；不并进岗库 |

每岗契约：`README.md` `faq.md` `outline.md` `web-knowledge.md`（T001 ✅；construction `outline.md` 指针到 `scheme-11.md`，method-hazard 指针到 `judge-card.md`）。  
门户权威句在 `demo/kb/company/web-portals.md`（GST 9% / Fire Code 2023 / CTU 2014 非强制 / GeBIZ≠评分 / APPBCA-2026-12）。T003 ✅ 五针只读该页。  
规范全文不进仓。缺数不编条款号。

### 5.3 MCP（动作）

stdio：`python demo/mcp_stdio.py --pack <大类>` 或 `--expert <id>`。样例 [mcp-host.example.toml](mcp-host.example.toml)。  
HTTP：工作台 `/api/mcp/*`；网关 pack-ship 子集。  
`kb://` 越权拒绝。chat 调写盘 `permission_denied`。  
xyz 只抄 solver。分页/订阅 = 有真 Host list/call 稳定之后（horizon D），不是现在。

### 5.4 Skill（SOP）

| 名称 | 路径 | 边界 |
|------|------|------|
| Grok 土木 | `skills/civil-buddy/` | 怎么写；V1 六路由；construction 写满；离线可出十一章 |
| 装箱引擎 skill | `docs/skills/` + `skills_registry.py` | 节点契约；**禁止** `bin3d.pack` 暴露成模型可改 MCP |
| MCP | `mcp_stdio.py` / `civil-mcp` | 能调什么，不是 SOP |

66 岗 SOP 的下一刀在 post-horizon，不塞进一份巨无霸 SKILL.md。

### 5.5 运行时与主线 C

- `POST /api/agent` 完整循环；`POST /api/turn` 兼容。  
- 高风险且 `p0_confirmed`/`confirm_ok` 非真 → `waiting_hitl`。UI 确认句原文见上；服务端不抽用户正文。  
- 招标 ingest：**拒绝一切 PDF**（含数字 PDF）。工作台附件可选 MinerU CLI（`CIVIL_PARSE=auto`），未装则 builtin 文字层，失败即拒。GETTING-STARTED 须钉一句（T050）。  
- delivery 可 `save_packing_snapshot`；pack-ship 只抄。  
- 再审不填业绩、不改 `can_fit`。

---

## 6. 16 车道（全量岗规划，不复制 66 遍下一刀）

易标完成度 = parse / outline / qa / kb / write。每岗「下一刀」以 post-horizon 该 id 为准。本文只定 **车道目标与富化顺序**。

| 车道 | 大类 | 岗数 | 产品目标 | 现网富化 |
|------|------|------|----------|----------|
| `lane-bid` | 经营投标 | 3 | 解析→交接→三列废标检查→按评分点排技术标目录 | **已富** handoff / gaps / expand |
| `lane-design` | 勘察设计 | **20** | 各专业说明/计算提纲；条款 UNSPECIFIED；DUAL 分栏 | **0/20** 骨架 |
| `lane-bim` | BIM | 3 | 协同/算量/交付目录；不假装 IFC 全量抽量 | **0/3** |
| `lane-planning` | 计划 | 3 | 总控/近看/资源栏位；无进度数据不编工期 | **3/3** plan-master + lookahead + resource |
| `lane-construction` | 施工生产 | 4 | 十一章提纲；危大判定卡；测量/调度作业单 | **1/4**：十一章 md；危大/测量/调度仍骨架 |
| `lane-hse` | 安质环 | 4 | 交底/质量/环保/应急草稿；SG 走 WSH 标题 | **4/4** |
| `lane-commercial` | 商务造价 | 5 | 造价 takeoff 栏、变更/索赔/分包/报量；无单价不编 | **0/5** |
| `lane-procurement` | 采购 | 3 | 计划/比价/合格名录栏；GeBIZ 只当门户 | **3/3** proc-plan + proc-compare + proc-vendor |
| `lane-plant` | 物机 | 4 | pack-ship 投影 solver；设备/仓/现场料栏 | **4/4** |
| `lane-lab` | 试验室 | 3 | 配比/取样/台账栏；无报告号不编 | **3/3** |
| `lane-finance` | 财务 | 3 | 税务日历抄 9%；记账/资金栏待填 | **3/3** finance-tax + finance-book + finance-fund |
| `lane-docs` | 资料监理 | 1 | 闭合目录；不代替监理指令 | **1/1** supervision |
| `lane-hr` | 人力 | 3 | 招聘/用工/培训草稿；法律口吻 | **0/3** |
| `lane-admin` | 行政 | 2 | 印章/公文目录；不自动盖章 | **0/2** |
| `lane-it` | IT | 3 | 运维/数据/应用草稿；禁止密钥进稿 | **0/3** |
| `lane-people` | 项目与工人 | 2 | 工人白话交底 / 日报；与技术稿分开 | **1/2** worker-brief |

**富化总序（全量）：** 保持 chat/run → 投标三岗（已做）→ pack-ship（已做）→ construction（十一章 + fill_scheme/`docx_pending` 已做）→ method-hazard 判定书（已做）→ cost takeoff（已做）→ finance-tax 日历栏（已做）→ survey/dispatch（T030 ✅）→ commercial 四岗（T031 ✅）→ 计划（T032 ✅）→ 试验/监理（T033+）→ 其余设计专业按 post-horizon。

每岗完成定义：

1. MCP `tools/list`（该 expert）能看见独有工具；  
2. 成稿栏位来自 outline/KB，缺数 `[A001]`/`UNSPECIFIED`；  
3. 测试能断言至少一栏 **不是** 通用 `_draft_markdown` 骨架句。

---

## 7. 全量 backlog（一张表，改状态只改这里和切片勾选）

### 7.1 平台 / 文档 / 协议

| ID | 内容 | 状态 | 验收 |
|----|------|------|------|
| D0 | 名册 66、入口收口 | ✅ | README / 索引 |
| D1 | 五篇说明书 + Host toml | ✅ | `test_docs_completion.py` |
| D2 | 本文全量规划书 | ✅（本文件） | 存在且为总入口 |
| RT-P0-1/2/3 | pack-ship 快照 · ToolEngine · Scheduler | ✅ | `test_runtime_p0.py` |
| RT-P1-1 | `tender.handoff.json` + 三列 + 评分点目录 | ✅ | `test_tender_handoff.py` |
| RT-P1-2 | `GET /api/eval/live` | ✅ | 五针离线，只读 company/web-portals.md（T003） |
| K1 | 66 岗目录四件套闸 | ✅ | 66/66；`scripts/test_kb_schema.py` |
| K2 | 门户标题只从 company 页 | ✅ | 五针 company（T003）+ 岗 GST/CORENET 扫描（T007/T008） |
| K3 | kb 隔离 + 文件名检索当闸 | 部分 | 跨大类拒绝 T023 ✅；文件名检索仍 `test_kb_search_filename.py` |
| K4 | 按车道每次 1 岗富 faq/outline | 进行中 | 岗 README 字段表 |
| M1–M4 | stdio、工具表、Host、prompts | ✅ | `test_mcp_stdio.py` |
| M5 | 其余大类 Host 样例 | ✅ | 现挂 3 pack；样例 16 行可复制（T020） |
| M6 | kb:// 分页订阅 | 延期 | 真 Host 先 list/call |
| S1–S4 | skill 拆分、十一章、对账 | ✅ | `test_construction_skill_path.py` |
| S5 | construction 填 docx 模板 | ✅ | 无 docx 则 `docx_pending`；有则扫描 0（T005） |
| RT-P1-3 | Memory：辖区/项目/P0 slot | ✅ | 压缩可见、不装读过（T010） |
| RT-P1-4 | Run 回放 | ✅ | `GET /api/runs/{id}` 两次同 identity（messages/tools/artifacts）。装箱 SSE `/replay` 是另一套 |
| RT-P1-5 | 危大判定书 + 确认句 | ✅ | 默认 SG WSH/PTW；37 号令只在 CN 栏；未确认 0 稿（T002） |
| RT-P2 | MinerU 可选、Go 热路径、多用户 ACL | 延期 | 见 handbook P2 |

### 7.2 岗写盘（指向 horizon，不展开）

| 优先 | 岗 | 状态 |
|------|----|------|
| 1 | bid-parse / compliance / tech | ✅ handoff 三列 + 评分点目录 |
| 2 | pack-ship | ✅ 投影 |
| 3 | construction | ✅ 十一章 md；fill_scheme 失败则 `docx_pending` |
| 4 | method-hazard | ✅ 判定书栏；默认 SG；HITL |
| 5 | cost | ✅ takeoff 栏；无单价 UNSPECIFIED |
| 6 | finance-tax | ✅ 日历栏页述 9%、申报期空栏 |
| 7 | survey / dispatch | ✅ 点号只抄；敏感作业交危大岗（T030） |
| 8 | variation | ✅ 文种判定 + 事实/依据/签认空栏 |
| 9 | claim | ✅ 意向栏+证据行+条款原文待贴 |
| 10 | subcontract | ✅ 按行抄细目，金额 TBD |
| 11 | interim | ✅ 开累/本期/监理审/业主核空表（T031 ✅） |
| 12 | plan-master | ✅ WBS｜紧前｜里程碑待填｜关键线路=待计算 |
| 13 | plan-lookahead | ✅ 四周表；制约未清不得写入本周承诺 |
| 14 | plan-resource | ✅ 劳动力｜机具｜材料三表，数量待填（T032 ✅） |
| 15 | lab-mix | ✅ 四层目录；无试验数据则施工配比整节待填 |
| 16 | lab-sample | ✅ 类别｜部位｜见证人空｜升级路径；组数 [A001] |
| 17 | lab-record | ✅ 报告编号待核｜仪器检定｜结论待填（T033 ✅） |
| 18 | supervision | ✅ 来文复述｜拟办｜证据目录；暂停/复工只出目录（T034 ✅） |
| 19 | safety-brief | ✅ 11 栏；毫米/电话 [A001] |
| 20 | quality | ✅ 主控｜一般｜隐蔽三表，结果=未检 |
| 21 | env | ✅ 扬尘/弃土/污水/夜间/市容五行，限值 UNSPECIFIED |
| 22 | emergency | ✅ 综合目录+点名专项+演练表头；电话医院待填（T035 ✅） |
| 23 | equip | ✅ 只抄设备名与已给证件；无证件不编进场结论 |
| 24 | warehouse | ✅ 按行抄收发；无数 TBD；无盘点不编盈亏 |
| 25 | material-site | ✅ 抄应耗/领料/盘点；算不出节超则 TBD（T036 ✅） |
| 26 | proc-plan | ✅ 先分甲供/甲指/自采再列表；提前期 UNSPECIFIED |
| 27 | proc-compare | ✅ 一行一家多列；定商标待制度定；写盘后 scan_forbidden |
| 28 | proc-vendor | ✅ 准入｜考察｜短名单；分数/结论待核；禁止成交结论（T037 ✅） |
| 29 | finance-book | ✅ 报销勾选｜科目对照｜对账缺口；金额 [A001] |
| 30 | finance-fund | ✅ 收入/支出窗口；金额 TBD；不当付款指令（T038 ✅） |
| 31 | worker-brief | ✅ 三段口播；无尺寸不报毫米 |
| 32+ | 其余 ~32 岗 | 骨架；下一刀在 post-horizon（已富岗勿再当缺口） |

---

## 8. 评测与合格

日常（刀后必跑，离线，不抓 IRAS；评测不是工作本身）：

```
python scripts/test_understand.py
python scripts/test_sandbox.py
python scripts/test_runtime_p0.py
python scripts/test_agent_loop.py          # 含 GET /api/eval/live 四针
python scripts/test_tender_handoff.py
python scripts/test_tender_review.py
python scripts/test_mcp_surface.py
python scripts/test_mcp_stdio.py
python scripts/test_docs_completion.py
python scripts/test_kb_schema.py
python scripts/test_official_title_scan.py
python scripts/test_industry_agent_eval.py # 断言总判仍「部分合格」
```

刀相关：`test_construction_skill_path.py`（施工）· `test_expert_turn.py`（改 66 岗协议）· `test_tender_ingest.py`（招标进矩阵）· `test_memory_slot.py`（Memory）· `test_tender_parse_engine.py`（parse 走引擎）· `test_kb_search_filename.py`（检索）。

联网：只在改 GST / Fire Code / CTU / GeBIZ / APPBCA 口径后。失败保留 KB 9%。禁止 `fetch_failed` ⇒「官方没写 9%」。结果追加 §13，**不改** `industry-agent-eval-2026-08-17.md` 总判句。脚本只报 `offline_gate_pass/fail`，不得把行业总判改成合格。

| 总判 | 条件 |
|------|------|
| 部分合格（现在） | 护栏在；多数岗骨架；不做签认 |
| 合格 · 内部起草搭子 | 默认面 chat/run + 真装箱可抄 + 回放 + eval/live + 施工/投标/装箱三条路径名实相符 |
| 不合格 · 签认/递交 | **永远不要追求** |

---

## 9. 每刀工作流

同一时刻只做 **一个 T 号**。评测是刀后证明，不是工作。

```
1. 取号：只取 §15 主链上第一个状态≠✅/延期 的 T 号。
   当前指针见 §11（此刻 = T039）。
   禁止 OR §7、切片勾选表、next-steps、post-horizon 原文、handbook「下一刀」。
   岗栏位细节可读 post-horizon 该 id；已做/未做以 §7/§15 为准。
2. 改最少文件。绿之前必须指出新路径（代码 / KB / MCP / SKILL / 测试之一）。指不出 = 没做。
3. 先跑该刀验收脚本，再跑 §8 日常闸。联网只在改官方口径之后。
4. 绿：只改状态，不新开「下一步」文。
   - 必改本文 §15 该行（及 §7 对应行）
   - 切片刀：completion-plan 同一 ID
   - 岗写盘：horizon 该 id「下一刀」改为已做
   - next-steps：只追加一行日志「T0xx ✅」，禁止新增队列
   - commit message 含 T 号
5. 红：修好或回滚到本刀起点。禁止带着红测试停手、睡眠再测、跳号。
```

K4「进行中」不是可抢的下一号。P 车道（T039+）不得在主链头指针未走到 T039 时开工。T001 / T030–T038 已 ✅。

---

## 10. 明确不做（全量有效）

**身份（与 §1.3 同口径）**  
GeBIZ 代交 / 自动中标；法定专项方案 / PE·QP·RTO 签认件；十万字写标、标书查重、fork OpenBidKit AGPL；模型发明 xyz / N0 / 条款号 / GST 税率（官方句只许抄门户）；中标率 +N%；把「可以开工 / 可交差 / 可报审 / 报审通过 / 请监理审核后开工」当能力或成稿断言（封面否定句里的「专家论证」「开工」合法）；66 人格塞进 SKILL.md。

**作业根与成稿**  
禁止把 `D:\layout` 当缺省作业根或验收落盘。断言禁语 = `scan_forbidden_inventions.py` 九句。

**平台与过程**  
16 类 KB 全量 embedding 季更；托管 200+ 柜型替换 solver；第二套装箱几何（pack-ship 只投影）；内核 Landlock/Seatbelt；Grafana/Jaeger 必选；过夜 sleep 环；研究笔记当必读。

---

## 11. 下一刀（立刻）

**T039 · people 进行中：下一岗 pm-daily__log。**

T038 ✅：finance-book / finance-fund 均已做（tax 见 T004）。chat 仍不写盘。T039 其余岗不得一行勾完。

T039 已做：worker-brief 三段口播；无尺寸不报毫米。

T039 下一岗：pm-daily 出天气待填|部位|形象（禁编百分比）|出勤待填。

---

## 12. 文档治理

**总入口只有本文。** 开工只取 §11 / §15 头指针。装箱 ARCHITECTURE / 主线 C 管计算器与投标×交付插件，不得另开产品下一步。`docs/README.md` 只做索引。

冲突序：本文 §1/§7/§10/§11/§15 → seed.json / yibiao-map.json → 切片勾选 → 操作手册 → 历史页。

T 号是开工 ID：K1=T001，P1-5=T002，K2=T003，P1-3=T010。handbook 不得再写「下一刀 P1-4」（已 ✅）。next-steps 只追加已做日志，不新开队列。主线 C 文「路线图以本文为准」服从本规划书。

| 角色 | 文件 | 禁止 |
|------|------|------|
| 规范 | **本文** | — |
| 勾选切片 | completion-plan | 自写「立刻做」若与 §11 不同 |
| 运行时 how-to | handbook | 自设 P1-n 下一刀；不得指向 overnight |
| 岗栏位 | post-horizon | 把过时下一刀当缺口 |
| 主线 C 规格 | product-mainline-tender-delivery | 另当产品总路线 |
| 操作 | GETTING-STARTED PROTOCOL MCP SKILLS KB | 规划句 |
| 已做流水 | next-steps.md | 编号「下一刀」队列 |
| 废止 | overnight-eval-iterate-2026-08-19.md | 再启 sleep 环 |
| 历史 | industry/live-eval、design.md（08-13） | 当现网能力 |

新建「规划」前先改本文 §7 与 §15。

---

## 13. 联网评测（2026-08-19 现场检索，不是只读旧笔记）

规则：官方页有 9% 就抄 9%。抓失败或 JS 壳 **不得** 写「官方没写 9%」。博客与旧通告不得覆盖联合通告。竞品星标不是合格线。

| 门户 | 本日检索到的口径 | 本仓 | 判定 |
|------|------------------|------|------|
| [IRAS Current GST rates](https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates) | *The current GST rate in Singapore is 9%.* 检索页 2026-08-16 仍爬到该句 | `company/web-portals.md` 与 finance-tax 抄同句 | **抄对** |
| [IRAS When to Charge GST](https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/charging-gst-(output-tax)/when-to-charge-goods-and-services-tax-(gst)) | *prevailing rate of 9%*。少写 `and` 的 URL 是 **404**，不要用 | 写稿标「页述 9%」；此页 KB 未收、非五针 | 官方句对 |
| [IRAS GST rate change](https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/gst-rate-change/gst-rate-change-for-business/overview-of-gst-rate-change) | 2023-01-01：7%→8%；**2024-01-01：8%→9%** | 不把 7%/8% 写成现行税率 | **须在规划与 KB 标明「现行 9%，历史升档仅作背景」** |
| [SCDF Fire Code 2023](https://www.scdf.gov.sg/fire-safety-services-listing/fire-code-2023) | 页题 *Fire Code 2023* / *Code of Practice for Fire Precautions in Buildings 2023* | 只列官方标题，条款 UNSPECIFIED | **抄对**。营销文「2026 Fire Code」或「仍是 2018」**不是**本仓口径 |
| [IMO CTU Code](https://www.imo.org/en/OurWork/Safety/Pages/CTU-Code.aspx) | *IMO/ILO/UNECE CTU Code*，**2014**，**non-mandatory** | company 页与 pack-ship 同句（T003） | 标题抄对 |
| [GeBIZ](https://www.gebiz.gov.sg/) | 新加坡政府一站式电子采购门户；GTP 注册后投标 | 「门户不是评分办法」 | **抄对**。第三方指南里的 ITT 金额门槛 **不**当本仓默认数字 |
| [MOF procurement processes](https://www.mof.gov.sg/policies/government-procurement/procurement-processes/) | Sourcing → Evaluation（按标书已公布标准）→ Approval of Award（授标公示上 GeBIZ） | 分值/PQM 只抄 ITT | **抄对** |
| [URA DC26-08](https://www.ura.gov.sg/guidelines/circulars/dc26-08/) · 通告 PDF | **2026-07-23** APPBCA-2026-12：2026-10-01 起 **新项目 GFA≥5,000 m²** 强制 Gateway | company 有收窄句、挂 PDF | **抄对**。反例是旧 **DC25-07**（不是 DC25-01）「不论 GFA」 |

旁证（不是合格线）：OpenBidKit 易标仍为 **AGPL-3.0** 写标桌面。本仓不并许可、不做十万字生成。星标数字随第三方页面漂，规划书不把它当 KPI。

行业总判：**部分合格**。本日联网 **未发现** 本仓把 9% 写错或把 GeBIZ 当评分公式。缺口仍是：多数岗骨架、扫描 PDF 拒绝、无代交。

---

## 14. 规划书审阅发现（必须改口的内部错误）

| 原表述 | 实测 | 处理 |
|--------|------|------|
| 设计车道 18 岗 | `seed.json` **design=20**（66=3+20+3+3+4+4+5+3+4+3+3+1+3+2+3+2） | §6 已改正 |
| 「其余 57 岗」 | 已富约 5 岗（bid×3 + pack-ship + construction 十一章），其余 **61** | §7.2 已改正 |
| K1「目录齐但无闸」 | 当时 64/66；只缺 construction 与 method-hazard 的 `outline.md` | 已做 T001 ✅；§11 现为 T039 |
| post-horizon bid 三岗「下一刀=handoff/gaps/评分点」 | P1-1 **已做** | 以本文 §7 为准；horizon 文当历史下一刀 |
| post-horizon construction「下一刀=十一章接 turn」 | S2 **已做** md；fill_scheme / `docx_pending` 已接（T005 ✅） | 岗栏下一刀 = T039 pm-daily（worker-brief ✅） |
| 行业评测「缺 Python eval/live、MCP 几乎只有 pack-ship」 | 2026-08-19 已有 `GET /api/eval/live` 与 `mcp_stdio --pack bid` | 不改 08-17 历史总判日期；现网能力以本文 §3 为准 |
| 营销博客「CORENET X 2026-10-01 全部新项目」 | 已被 APPBCA-2026-12 收窄为 GFA≥5,000 m² | §13 列为反例 |
| §15「T030–T047 = 61 岗」 | 展开约 **56**（已扣 bid×3、pack-ship、construction、method-hazard、finance-tax、cost、survey、dispatch） | 下表已改 |
| handbook §12「下一刀 P1-4」 | RT-P1-4 **已 ✅** | 以本文 §11 为准 |
| completion-plan P 段仍写「下一优先 construction 十一章」 | S2 **已 ✅** | 以本文 §7 为准 |
| T012 OTEL 同 run_id | `agent_loop` span + `test_otel_dashboard.py` 已有 | §15 标 ✅，不占主链 |

---

## 15. 加长任务总表（不定时限，按号做）

每条必须有产物路径 + 测试。不做睡眠环。勾选时改本表「状态」。

### A. 库与官方口径（先把事实源钉死）

| ID | 任务 | 产物 | 验收 | 状态 |
|----|------|------|------|------|
| T001 | K1：补 2 个 outline + `test_kb_schema.py` | 两路径 outline.md + 脚本 | 66 岗四件套全在 | ✅ |
| T002 | method-hazard 判定书：默认 SG WSH/PTW；37 号令只在 CN 栏；信息不足不编 | `judge-card` 栏位写盘 | 未确认 0 稿；无「可以开工」 | ✅ |
| T003 | K2：eval/live 针改读 `company/web-portals.md` | `eval_live.py` | GST/Fire/CTU/GeBIZ/APPBCA 五针 | ✅ |
| T004 | finance-tax 日历栏：申报期空栏 + 页述 9% + 税额待填 | `finance-tax__calendar` 非骨架句 | 测试断言含 9% 且无自编税率 | ✅ |
| T005 | construction `fill_scheme_docx`；失败则 `docx_pending` | skill 模板管道 | 扫描 0 才报成功 | ✅ |
| T006 | cost takeoff 栏：工程量来自用户表；无清单不编单价 | `cost` 独有写盘 | 无单价则 TBD/UNSPECIFIED | ✅ |
| T007 | 岗若写 GST 必须含 9%；禁止 7%/8% 当现行 | 扫描脚本或评测针 | 历史升档只可出现在「背景」句 | ✅ |
| T008 | CORENET 反例测试：草稿不得写「全部新项目不论 GFA 强制」 | `scan` 或评测 | 只允许 APPBCA-2026-12 句 | ✅ |

### B. 运行时（平台可复用）

| ID | 任务 | 产物 | 验收 | 状态 |
|----|------|------|------|------|
| T010 | Memory slot：辖区 / 项目名 / P0；压缩打标 | `session.summary` | 压缩后不得假装读过被丢细节 | ✅ |
| T011 | `/api/tender/parse` 走同一 ToolEngine 鉴权 | gateway 调 engine | chat 意图拒写 | ✅ |
| T012 | OTEL span 带同一 `run_id` 与 agent_loop | `otel_hooks` | dashboard 能按 run_id 过滤 | ✅ |
| T013 | 高风险 HITL 确认句硬校验（方法-危大+施工已有，扩到 scheme deliver） | allow() | 未打原句 0 份稿 | 部分 |
| T014 | agent_loop 对 bid-compliance/tech 走与 expert_turn 同一 handoff | `agent_loop.py` | 同 session 读到 tender.handoff.json | ✅ |

### C. MCP / Host

| ID | 任务 | 产物 | 验收 | 状态 |
|----|------|------|------|------|
| T020 | Host 样例补齐 16 pack（可复制，不要求用户全挂） | `mcp-host.example.toml` | 每 pack 一行注释 | ✅ |
| T021 | `--pack construction` stdio：有 scheme_draft/scan；无 tender.parse、bid-parse__extract、pack-ship__plan、method-hazard__judge_hazard；prompt 不含危大 judge | `test_mcp_stdio.py` | 现仅测 bid pack | ✅ |
| T022 | `write_deliverable` MCP `intent=chat` 拒绝 | 并进 T021 | engine 已拒；Host 面补测 | 并入 T021 |
| T023 | kb:// 读 method-hazard 从 bid-parse 拒绝（已有 bid-tech 例，补跨大类） | `test_mcp_surface.py` | 拒绝句 | ✅ |
| T024 | 真 Host 手册：Grok/Cursor 各贴一份最小配置 | MCP.md | 命令本机跑过 | ✅ |
| T025 | kb 分页/订阅 | 延期 | 有 Host 稳定 list/call 后再开 | 延期 |

### D. 车道批次（每岗一任务，栏位非骨架）

**纪律：** 一次只做一岗。测：该岗 run 产物含 outline 栏位名；chat 仍不写盘。

| ID | 车道 | 岗（按序） |
|----|------|------------|
| T030 | construction 收尾 | survey__record（只抄已给点号）→ dispatch__daily（敏感作业交危大岗）✅ |
| T031 | commercial | variation ✅ → claim ✅ → subcontract ✅ → interim ✅（cost 见 T006） |
| T032 | planning | plan-master ✅ → plan-lookahead ✅ → plan-resource ✅ |
| T033 | lab | lab-mix ✅ → lab-sample ✅ → lab-record ✅ |
| T034 | docs | supervision 闭合目录（不代替监理指令） ✅ |
| T035 | hse | safety-brief ✅ → quality ✅ → env ✅ → emergency ✅ |
| T036 | plant 非装箱 | equip ✅ → warehouse ✅ → material-site ✅（pack-ship 已富，跳过） |
| T037 | procurement | proc-plan ✅ → proc-compare ✅ → proc-vendor ✅（金额门槛不默写） |
| T038 | finance 其余 | finance-book ✅ → finance-fund ✅（tax 见 T004） |
| T039 | people | worker-brief ✅ → pm-daily |
| T040 | hr | hr-recruit → hr-labor → hr-train |
| T041 | admin | admin-doc → admin-office（不自动盖章） |
| T042 | it | it-ops → it-data → it-app（禁止密钥进稿） |
| T043 | bim | bim-coord → bim-qto → bim-deliver（不假装 IFC 全量） |
| T044 | design 批次 1 | architecture（10 章面积[A001]）→ structure → geotech → facade |
| T045 | design 批次 2 | plumbing → hvac → electrical → fire-protect → steel |
| T046 | design 批次 3 | landscape → interior → intel-weak → civil-defense → hydraulic |
| T047 | design 批次 4 | port → municipal → bridge → tunnel → traffic → design-coord |

T030–T047 是**批次合同**（T030–T038 ✅、T039 worker-brief ✅ 后约 **32** 岗）。**一行不得一次勾完**；每岗一 commit。细节读 post-horizon 该 id。

### E. 主线 C 与装箱（插件，不另起炉灶）

| ID | 任务 | 验收 | 状态 |
|----|------|------|------|
| T050 | 扫描 PDF：产品默认拒绝；文档写清 MinerU 可选失败即拒 | GETTING-STARTED 一句 + 上传 PDF 返回拒绝 | ✅ |
| T051 | 资格/★ P0 必须人确认才许「覆盖」态 | 矩阵 human_confirm | 已有窄实现 |
| T052 | pack-ship 与 /workbench 同 session 必能抄 can_fit | 先 delivery 再 expert pack-ship | ✅ `test_tender_delivery_api.py` |
| T053 | 禁止第二套 3D packer 出现在 agent_loop | 代码检索 `run_big_team` 不在 pack-ship turn | 纪律 |

### F. 文档与评测

| ID | 任务 | 验收 | 状态 |
|----|------|------|------|
| T060 | 本文 D2 | 本文件 | ✅ |
| T061 | post-horizon 文首加「已做刀以 product-plan §7 为准」 | 避免双下一刀 | ✅ 2026-08-19 |
| T062 | 刀后快闸清单写入 GETTING-STARTED | 命令本机跑过 | ✅ |
| T063 | 改官方口径时才联网；结果追加 §13 表，不改 08-17 历史总判句 | 部分合格保持 | 纪律 |
| T064 | 作业根 Office：有表的岗另存 `.xlsx`，可 Excel 打开 | `CIVIL_JOB_ROOT`（禁 `D:\layout`）+ sibling xlsx | ✅ |
| T065 | 作业根直接读本机 xlsx/docx/csv/txt，不必再上传 | `GET /api/job` + run 时注入 | ✅ |
| T066 | 点名已有 xlsx 时写入 `CB草稿-*` 表，保留业主表 | 授权夹内原地改草稿表 | ✅ |
| T067 | 本机桌面窗口：启动器打开 127.0.0.1 应用窗 | `scripts/civil-buddy-desktop.ps1` | ✅ |
| T068 | 可下载试用：LICENSE + 自带 API Key + 工作台 Release + 给试用的人.md | MIT · OpenAI 兼容 Key · `cargo build --release` 上 Releases | ✅ |

**主链（不定时限；头指针 = 第一个非 ✅/延期）：**

T001 → T021 → T023 → T003 → T007 → T008 → T002 → T004 → T006 → T005 → T014 → T011 → T010 → T020+T024 → T030 → T031 → T032 ✅ → T033 ✅ → T034 ✅ → T035 ✅ → T036 ✅ → T037 ✅ → T038 ✅ → **T039**（下一岗 pm-daily）→ T040…T047（T050 / T052 / T062 / T064–T068 文档与平台已 ✅，不占岗栏）。

T012/T060/T061/T051/T053 不占刀。中途红则停在该号，不准跳号。
