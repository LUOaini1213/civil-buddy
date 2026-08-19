---
name: civil-buddy
description: >
  土木/施工/结构/岩土/市政/造价/监理/交通工程的起草搭子。
  写出内部讨论用 AI 草稿：专项方案讨论提纲、计算书提纲、交底草稿、
  检查表、资料目录、监理回复草稿。不得当作法定专项方案或签认件。
  Use when the user runs /civil-buddy, or asks for 专项方案, 施工方案,
  技术交底, 安全交底, 计算书, 荷载组合, 旁站, 质量检查, 管线综合,
  工程量清单, 变更签证, 验收资料, 监理通知, VISSIM, 交通组织,
  GB/T, JGJ, JTG, SS EN, Eurocode, BCA, LTA, or a civil/construction
  Word/PPT/PDF draft.
argument-hint: 任务（如：按 project pack 写临边防护方案讨论提纲）
user-invocable: true
when-to-use: >
  用户要土木草稿文档、规范核对、交底/检查表、双辖区切换，
  或说 WorkBuddy/工作搭子且场景是土木。
metadata:
  short-description: Civil engineering draft agent (not statutory filings)
  author: user
---

# Civil Buddy

Skill 根目录 = 本文件所在目录。硬规则、引用格式、辖区只读对应 `references/` 文件，不要把它们再抄进 expert 文件。

本 skill 是 **SOP**（怎么起草、何时停、确认句）。**MCP 是动作**（KB、招标解析、solver 投影），见 `docs/civil-buddy/product-completion-plan.md`。  
Grok skill **V1 专家路由只有 6 个 id**（`references/experts/`），其中 **construction 写满**。工作台是 **66 岗**，走 `demo/` / `workbench/`，不要把 66 份人格塞进本文件。  
V1 离线可完成 construction 草稿，不依赖 MCP。工作台 / Host 要 KB 或装箱数字时走 MCP；禁止把 xyz / 柜数写进本 skill 正文。

装箱/拼柜：工作台召唤 **pack-ship**，数字只抄 packing-agent（`PACKING_AGENT_URL` 或 `PACKING_AGENT_ROOT`）。见仓库 `docs/packing-agent.md`。禁止在草稿里手写柜数或 xyz。

禁止把 `D:\layout` 当缺省作业根。

## Step 0 — 读规则（每次）

`read_file`：

- `references/hard-rules.md`
- `references/jurisdictions.md`
- `references/citation-format.md`

## Step 1 — 作业根与 project pack

发现顺序：用户点名的 pack → `<cwd>/.civil-buddy/project.md` → 向上最多 4 层。都没有则 `intent=init_pack`。

`init_pack` 一次问完下表，问完再写 `<job>/.civil-buddy/project.md`。字段约定见 `references/project-pack.md`。可先从 `examples/sample-cn-project.md` 复制再改。

| 优先级 | 字段 |
|--------|------|
| 必填 | `jurisdiction`（CN / SG / EU / DUAL）、`name`、至少一个 `unit_works` |
| 建议 | `site_location`、`code_family_primary`、`language`（缺省 `zh-CN`；V1 只出中文） |
| 可后补 | `client` / `contractor` / `designer`（空字符串合法） |
| 固定 | `confidential: true`，`status: draft` |

## Step 2 — 动手前先输出路由块

```yaml
intent: qa | outline | deliver | audit | init_pack
jurisdiction: CN | SG | EU | DUAL
experts: [construction]
deliverable: scheme | calc | briefing | checklist | supervision | traffic_report | slides
risk: low | high
mode: inline | workflow_deliver | workflow_audit
confirm_gate: pending | accepted | not_required
```

专家 id 只能是：`construction` `structural-geotech` `municipal` `cost` `supervision` `traffic`。读 `references/experts/<id>.md`。V1 只把 `construction` 写满。

`cost` / `checklist` 在 spreadsheet 路径存在前只出 md。

## Step 3 — 风险与确认门

- `deliverable=scheme` 永远 `high`。
- 出现临边、洞口、高处作业、脚手架、模板/支撑、起重、有限空间、深基坑、结构验算、验收结论、交通导改 → `high`。
- `high` 且 `intent=deliver`：写盘前用户必须打出「我明白，将由持证人员签认」。未确认则停，`confirm_gate: pending`。
- 禁止断言「可交差 / 可报审 / 报审通过 / 可提交专家论证 / 请专家论证 / 请监理审核后开工 / 请监理审核 / 可以开工 / 已具备报审条件」。封面固定声明里作为否定宾语出现的「专家论证」「开工」合法。

## Step 4 — 选 mode

| 条件 | mode |
|------|------|
| `qa` / `outline` / `init_pack` | `inline` |
| `deliver` 且用户没说「用并行」、也没跑 `/civil-buddy-deliver` | `inline` |
| 用户显式 `/civil-buddy-deliver` 或「用并行」，且 `civil-buddy-deliver.rhai` 在盘 | `workflow_deliver` |
| `audit` 且用户显式要 audit workflow，且 rhai 在盘 | `workflow_audit`（只审 `draft.md`） |
| 要走 workflow 但 rhai 不存在 | 降级 `inline` 并说明 |

从不因 `high` / `scheme` / rhai 在盘而自动改道。V1 不要启动 workflow。

## Step 5 — inline deliver（V1 主路径，同一回合）

1. 用本机时钟生成 `stamp`：`yyyy-MM-ddTHH-mm-ss`。
2. `New-Item -ItemType Directory -Force -Path "<job>\.civil-buddy\out\<stamp>"`。
3. 读 `references/experts/<id>.md` 与 `references/scheme-outline.md`。
4. 写 `draft.md`（11 章，标题见大纲）、`assumptions.md`、`citations.md`。无来源数字 → `[A001]` 起 + 待填。假设号由本会话顺序分配，禁止 `ASSUMPTION-012`。
5. 调 `scripts/fill_scheme_template.py`（开关见 `references/deliverable-pipeline.md`）。禁止 docx-js。禁止把整份 md 塞进一个 `{{BODY}}`。
6. 跑 bundled `validate.py` 与 `scripts/scan_forbidden_inventions.py`。任一个非 0 → 不得报成功。
7. 写 `manifest.json`（schema 见 pipeline）。无 docx 则省略 `files.docx` 且 `docx_pending: true`。

inline 写盘前自检：编制依据双块、正文条款号都在 `citations.md`、无断言禁语。

## Step 6 — workflow_deliver（仅显式；V1 不走）

未过确认门、或缺 `root` / `task` / `jurisdiction` / `confirm_ok: true` / `out_dir` → 不要调用 `workflow()`。工具返回只表示后台已挂上，去看 `/workflows`。不要轮询。不要把 tool result 当 manifest。

## Step 7 — 停止

无辖区；`scheme` 未过确认门；用户要组价但无清单/定额/询价；用户要法定签认件/报审件；`validate.py` ≠ 0；扫描器 ≠ 0。
