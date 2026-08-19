# Civil Buddy 全量产品规划书

| 项 | 值 |
|----|----|
| 产品 | Civil Buddy |
| 版本 | 2026-08-19 |
| 仓库 | https://github.com/LUOaini1213/civil-buddy |
| 岗 / 大类 | **66 / 16**（`workbench/seed.json`） |
| 总判 | **部分合格**的内部起草搭子，不是签认/递交机器人 |
| 纪律 | **不定时限 · 不准空转**。墙钟和睡眠评测环不是交付 |
| 本文地位 | **产品规划唯一总入口**。切片文档只执行、不另开第三套「下一步」 |

**怎么用：** 改产品前先读 §1 边界与 §12 不做。开工只取 §11 下一刀。66 岗独有栏位不在本文复制，见 [post-horizon-2026-08-17.md](post-horizon-2026-08-17.md)。

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

### 1.2 三条产品线（一个仓库，三个用户问题）

| 线 | 用户问题 | 入口 | 数字从哪来 |
|----|----------|------|------------|
| **工作台** | 这个岗怎么起草 | :8765 · `/civil-buddy` · MCP `--pack/--expert` | 岗 KB 官方标题；缺数 `[A001]` / `UNSPECIFIED` |
| **主线 C** | 这个标怎么应、货怎么交 | :8000 默认页 · `/api/tender/*` · `/api/agent` | 招标 `exact_text`；装柜 solver |
| **装箱引擎** | 这批料怎么装进柜 | :8000/workbench · `run_big_team` | 仅 tools：xyz / N0 / can_fit / mid50 |

pack-ship 岗 **不是第二套装箱**。它只投影本仓 solver 快照。断线四字段字面 `UNSPECIFIED`。

### 1.3 我们不是

| 禁止写成产品能力 | 原因 |
|------------------|------|
| GeBIZ 代交 / 自动中标 | 门户不是评分办法；无签章 |
| 法定专项方案 / PE·QP·RTO 签认件 | 须持证人员 |
| 十万字写标、标书查重产品化 | 易标 AGPL；会编业绩 |
| 模型手写 xyz / N0 / 条款号 / GST 税率 | 不可追责 |
| 中标率 +N% | 没有、也不许编 |
| 65 份人格戏服 | 岗是工具栏位，不是角色扮演 |

### 1.4 锁死的数字与句子

- 岗 **66**，大类 **16**。  
- 确认句：`我明白，将由持证人员签认`。  
- GST：IRAS 页述 **9%**。抓门户失败不得改口「官方没写 9%」。  
- GeBIZ **不是**评分办法。Fire Code **2023**。CTU Code **2014** 非强制。  
- CORENET X 2026-10-01 强制范围以 APPBCA-2026-12 为准（GFA≥5,000 m²），不把营销句当全量。  
- 易标五段：parse → outline → qa → kb → write。本产品对齐动作，不 fork AGPL。

---

## 2. 给谁用、怎么用

| 角色 | 典型任务 | 走哪条线 |
|------|----------|----------|
| 经营岗 / 投标助理 | 粘招标节选进矩阵、出交接、再审禁语 | 主线 C |
| 施工员 / 方案讨论 | 临边十一章提纲 | 工作台 construction · Grok skill |
| 物机 / 物流 | 铁架装柜证据 | pack-ship 投影；要真算去 /workbench |
| 财务 | 问 GST、出税务日历栏 | finance-tax；税率只抄 IRAS 句 |
| 宿主（Grok/Cursor/Claude） | `tools/list` + `kb://` | `demo/mcp_stdio.py --pack …` |
| 持证人员 | **不**用本产品代替签认 | 人在确认句之后仍要自己签 |

### 关键路径（必须永远能走）

1. 问「什么是 GST」→ `chat`、不写盘、回复含 **9%**。  
2. 「解析招标…」→ 矩阵行有 `exact_text`，`submit_blocked=true`。  
3. 施工岗未确认句 → 0 份稿。确认后十一章标题齐，无「可以开工」。  
4. pack-ship 无快照 → 四字段 `UNSPECIFIED`；有 delivery 快照 → 原样抄，不重算 xyz。  
5. MCP `--pack bid` → 能 list 到 `search_kb`/`tender.parse`，看不见 `pack-ship__plan`。  
6. `kb://` 读兄弟私库 → 拒绝句，不是空 404。

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
| 运行时 | 70% | Scheduler、ToolEngine、沙箱、`/api/agent`、Run 回放 | Memory slot；session 压缩可见 |
| 主线 C | 75% | ingest/矩阵/handoff/再审/delivery | 扫描 PDF 默认拒绝；资格栏仍人填 |
| 装箱引擎 | 80% | 大 Team A/B、3D、CoG、HITL | 非本规划主战场；禁止第二套 packer |
| 工作台 66 岗 | 40% | 同一套 chat/run；bid 三岗+pack-ship+construction 有真栏位 | 其余岗骨架 md |
| MCP | 65% | Python stdio；bid 可见 KB+招标；pack-ship 投影；Host 样例 | 12 大类未挂 Host；kb 分页/订阅延期 |
| Skill | 55% | SOP 与 66 岗关系写清；施工十一章接 turn | 其余 5 个 Grok 专家仍提纲；docx 填充未接 turn |
| 岗 KB | 45% | 目录齐、08-14 门户摘录、隔离可测 | schema 闸未做；多数 faq/outline 骨架 |
| 技术文档 | 70% | GETTING-STARTED/PROTOCOL/MCP/SKILLS/KB | 本文收口后，研究笔记不得再冒充必读 |
| 评测 | 60% | 离线闸 + eval/live 针 | 联网只在改官方口径后做 |

行业评测总判保持 **部分合格**（[industry-agent-eval-2026-08-17.md](industry-agent-eval-2026-08-17.md)）。「合格 · 内部起草搭子」要默认面真装箱可抄 + 循环可回放 + eval/live **同时**成立，且由人改口，脚本不得改总判句。

### 3.3 已落地短刀（不要重做）

P0 ToolEngine/Scheduler/pack-ship 快照 · P1-1 handoff · P1-2 eval/live · P1-4 Run 回放 · Agent 循环+沙箱 · D0 名册 66 · D1 五篇说明书 · M1–M4 Python stdio 与工具表 · S1–S4 skill 拆分与施工十一章。

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

业务是插件。运行时有状态机、错误码、回放。禁止再把招标解析焊死在 UI 按钮里绕过 ToolEngine（现网 `/api/tender/parse` 可保留为快捷入口，但写盘/鉴权口径必须与引擎一致）。

错误码：`ok` `permission_denied` `invalid_args` `timeout` `circuit_open` `unspecified` `max_steps`。见 [PROTOCOL.md](PROTOCOL.md)。

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

每岗契约：`README.md` `faq.md` `outline.md` `web-knowledge.md`。  
门户权威句只在 `demo/kb/company/web-portals.md`（GST 9% / Fire Code 2023 / CTU 2014 / GeBIZ≠评分 / APPBCA-2026-12）。岗文件链或抄同一句。  
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
- 高风险无确认句 → `waiting_hitl`。  
- 招标：文字/表格节选进矩阵；扫描 PDF 产品拒绝（MinerU 可选 CLI，失败即拒）。  
- delivery 可 `save_packing_snapshot`；pack-ship 只抄。  
- 再审不填业绩、不改 `can_fit`。

---

## 6. 16 车道（全量岗规划，不复制 66 遍下一刀）

易标完成度 = parse / outline / qa / kb / write。每岗「下一刀」以 post-horizon 该 id 为准。本文只定 **车道目标与富化顺序**。

| 车道 | 大类 | 岗数 | 产品目标 | 现网富化 |
|------|------|------|----------|----------|
| `lane-bid` | 经营投标 | 3 | 解析→交接→三列废标检查→按评分点排技术标目录 | **已富** handoff / gaps / expand |
| `lane-design` | 设计 | 18 | 各专业说明/计算提纲；条款 UNSPECIFIED；DUAL 分栏 | 骨架 md |
| `lane-bim` | BIM | 3 | 协同/算量/交付目录；不假装 IFC 全量抽量 | 骨架 |
| `lane-planning` | 计划 | 3 | 总控/近看/资源栏位；无进度数据不编工期 | 骨架 |
| `lane-construction` | 施工生产 | 4 | 十一章提纲；危大判定卡；测量/调度作业单 | **construction 十一章已接 turn**；危大仍骨架 |
| `lane-hse` | 安质环 | 4 | 交底/质量/环保/应急草稿；SG 走 WSH 标题 | 骨架 |
| `lane-commercial` | 商务 | 5 | 造价 takeoff 栏、变更/索赔/分包/报量；无单价不编 | 骨架 |
| `lane-procurement` | 采购 | 3 | 计划/比价/合格名录栏；GeBIZ 只当门户 | 骨架 |
| `lane-plant` | 物机 | 4 | **pack-ship 投影 solver**；设备/仓/现场料栏 | pack-ship **已富** |
| `lane-lab` | 试验 | 3 | 配比/取样/台账栏；无报告号不编 | 骨架 |
| `lane-finance` | 财务 | 3 | 税务日历抄 9%；记账/资金栏待填 | 日历仍偏骨架栏，KB 有 9% |
| `lane-docs` | 资料监理 | 1 | 闭合目录；不代替监理指令 | 骨架 |
| `lane-hr` | 人力 | 3 | 招聘/用工/培训草稿；法律口吻 | 骨架 |
| `lane-admin` | 行政 | 2 | 印章/公文目录；不自动盖章 | 骨架 |
| `lane-it` | 信息化 | 3 | 运维/数据/应用草稿；禁止密钥进稿 | 骨架 |
| `lane-people` | 现场人员 | 2 | 工人白话交底 / 日报；与技术稿分开 | 骨架 |

**富化总序（全量）：** 保持 chat/run → 投标三岗（已做）→ pack-ship（已做）→ construction（十一章已做，docx 未做）→ method-hazard 判定书 → cost takeoff → finance-tax 日历栏 → 计划/试验/监理 → 其余设计专业按 post-horizon。

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
| K1 | 66 岗目录四件套闸 | 未做 | `test_kb_schema.py` |
| K2 | 门户标题只从 company 页 | 未做 | eval/live 读 company |
| K3 | kb 隔离 + 文件名检索当闸 | 部分 | `test_mcp_surface.py` / `test_kb_search_filename.py` |
| K4 | 按车道每次 1 岗富 faq/outline | 进行中 | 岗 README 字段表 |
| M1–M4 | stdio、工具表、Host、prompts | ✅ | `test_mcp_stdio.py` |
| M5 | 其余大类 Host 样例（12 pack） | 未做 | toml 可复制；不要求一次全挂 |
| M6 | kb:// 分页订阅 | 延期 | 真 Host 先 list/call |
| S1–S4 | skill 拆分、十一章、对账 | ✅ | `test_construction_skill_path.py` |
| S5 | construction 填 docx 模板 | 未做 | 无 docx 则 `docx_pending`；有则扫描 0 |
| RT-P1-3 | Memory：辖区/项目/P0 slot | 未做 | 压缩可见、不装读过 |
| RT-P1-4 | Run 回放 | ✅ | `GET /api/runs/{id}` |
| RT-P1-5 | 危大判定书 + 确认句 | 未做 | 未确认 0 稿；无开工断言 |
| RT-P2 | MinerU 可选、Go 热路径、多用户 ACL | 延期 | 见 handbook P2 |

### 7.2 岗写盘（指向 horizon，不展开）

| 优先 | 岗 | 状态 |
|------|----|------|
| 1 | bid-parse / compliance / tech | ✅ handoff 三列 + 评分点目录 |
| 2 | pack-ship | ✅ 投影 |
| 3 | construction | ✅ 十一章 md；❌ docx |
| 4 | method-hazard | 未做判定书栏 |
| 5 | cost | 未做 takeoff 栏 |
| 6 | finance-tax | KB 有 9%；日历栏未富 |
| 7+ | 其余 57 岗 | 骨架；下一刀在 post-horizon |

---

## 8. 评测与合格

日常（刀后必跑，不是工作本身）：

```
python scripts/test_understand.py
python scripts/test_sandbox.py
python scripts/test_agent_loop.py
python scripts/test_mcp_surface.py
python scripts/test_mcp_stdio.py
python scripts/test_docs_completion.py
```

刀相关再加：`test_tender_handoff.py` `test_construction_skill_path.py` `test_expert_turn.py`（改 66 岗协议时）。

联网：只在改官方标题/GST/Fire Code/CTU/GeBIZ 口径之后。失败保留 KB 9%。

| 总判 | 条件 |
|------|------|
| 部分合格（现在） | 护栏在；多数岗骨架；不做签认 |
| 合格 · 内部起草搭子 | 默认面 chat/run + 真装箱可抄 + 回放 + eval/live + 施工/投标/装箱三条路径名实相符 |
| 不合格 · 签认/递交 | **永远不要追求** |

---

## 9. 每刀工作流

```
1. 只取 §11 或 §7 下一未勾选 ID
2. 改最少文件
3. 跑该刀脚本 + §8 快闸
4. 绿：勾本表 + 切片表 + next-steps 一行 + commit
5. 红：修好或回滚。禁止带着红测试过夜
```

空转定义同完善规划：睡眠再测、用截止钟点当完成、只改总判句、再写一份重复的「下一步」。

---

## 10. 明确不做（全量有效）

GeBIZ 代交、法定签认、十万字写标、标书查重产品化、模型写 xyz/条款号/税率、中标率、fork OpenBidKit AGPL、16 类知识库全量 embedding 季更、托管 200+ 柜型替换 solver、内核 Landlock、Grafana 必选、第二套装箱几何、66 人格 prompt、过夜 sleep 环、把研究笔记当必读。

---

## 11. 下一刀

**K1 · 66 岗知识库目录契约。**

`python scripts/test_kb_schema.py`：每个 `demo/kb/<cat>/<id>/` 必须有 README / faq / outline / web-knowledge。允许内容短，不允许缺文件。缺的补空文件头（标题+本岗产出+「缺数 UNSPECIFIED」），不假装富化。

做完 K1 → **RT-P1-5 method-hazard 判定书**（与 construction 同车道）→ **K2 门户单一来源** → 按 §6 总序富 cost / finance-tax。

---

## 12. 文档治理

| 类型 | 文件 | 冲突时 |
|------|------|--------|
| 规范（产品） | **本文** | 以本文为准 |
| 规范（刀级） | completion-plan / handbook / post-horizon / 主线 C | 补细节；不得改 §1 边界 |
| 操作 | GETTING-STARTED PROTOCOL MCP SKILLS KB | 命令必须本机刚跑过 |
| 名册 | seed.json + yibiao-map.json | 文档服从 JSON |
| 历史 | industry-eval、live-eval、github-wheels、overnight 废止页 | 不改已发布总判日期；现网名册仍 66 |

新建「规划」前先改本文 §7。禁止第三份总路线。
