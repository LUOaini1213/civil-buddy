# Civil Buddy

[![ci-smoke](https://github.com/LUOaini1213/civil-buddy/actions/workflows/ci.yml/badge.svg)](https://github.com/LUOaini1213/civil-buddy/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/LUOaini1213/civil-buddy)](https://github.com/LUOaini1213/civil-buddy/releases) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Agentic AI Workspace for Engineering** — 土木版 Codex

Natural Language → Agent Routing → Deterministic Tools → HITL → Evaluation

**CAD → 3D 建模助手（预览）** — 上传 DXF（闭合轮廓、圆弧、圆和受限块引用），确认单位、图层和实体区域，
生成墙/柱/板或带孔截面的参数化网格；旋转查看、选中追溯、修改高度/长度与撤销，
保存项目及版本、重启恢复、项目包交接，并在统一 Agent 对话里改参、撤销与导出。
先运行 `python -m pip install -r requirements-cad.txt`，
再运行 `python -m packing_assistant.civil app`，从首页进入「CAD → 3D 建模助手」（`/cad`）。
同仓还有施工计划（关键路径 / 资源调整，`/engineering/planning`）和箱单台账（来源核对后才改数，`/logistics`）。
附带明确标注的合成样例，真实项目图纸、工期和箱单须另行验收；不支持直接导入 DWG，
不自动识别门窗，不是完整 BIM 或签认模型。操作与边界见 [CAD 建模说明](docs/civil-buddy/cad-to-3d.md)。

![Civil Buddy workbench](docs/assets/workbench.png)

**In one paragraph (EN)** — a civil / construction workbench whose one measured
engine is container packing (`pack-ship`). Coordinates, counts and prices come
only from that tool, and a 128-run evaluation is archived in the repo. CI on
every push runs a 2×1 offline slice of that eval, not the full 128. The other
65 job-post skills are SOPs the model drafts against, at the depth the ladder
states — not 65 engines. High-risk actions (qualification, bids, disk writes)
need a human confirmation. A preview path turns DXF outlines into a mesh
(`/cad`), plus a planning page and a packing-list ledger; those are not extra
engines and are not sign-off models. Rust workbench + MCP entry, Python packing harness,
FastAPI gateway. MIT.

**30 秒，无 Key** — 策略引擎 + 失败恢复的四拍剧本（正常放行 → 越权被拒 → 工具故障重试降级 → 成本超限熔断）：

```bash
pip install -r requirements.txt
python scripts/demo_agent_middleware.py     # 四拍剧本，输出见下
python scripts/test_agent_middleware.py     # 同一剧本的断言版（CI 每次提交都跑）
```

![The four-beat middleware script running in a terminal: ALLOW, DENY with a reason, DEGRADE through the recovery chain, CIRCUIT on cost](docs/assets/demo.gif)

<details>
<summary>四拍剧本的实际输出（2026-09-03 本机，无 API Key）</summary>

```text
==========================================================
Civil Buddy · 策略引擎 + 失败恢复
==========================================================
两层 Runtime 中间件（不是五个平庸包装）
  1. 策略引擎  谁 / 哪个工具 / 花多少 / 能否碰生产数据
  2. 失败恢复  超时重试 → 降级 UNSPECIFIED → 审计链
剧本：正常下单 → 越权被拒 → 工具挂掉自动恢复 → 成本超限熔断

[1/4] 正常下单   ALLOW
  原因  低风险岗 finance-tax 写作业根
  结果  wrote=True  GST 9%=True  files=2  run=run-<id>

[2/4] 越权被拒   DENY
  原因  拒绝：岗 bid-parse 不能调 pack-ship__plan（exclusive 属于 pack-ship）。
  弹窗  拒绝：岗 bid-parse 不能调 pack-ship__plan（exclusive 属于 pack-ship）。
  密钥  拒绝：secret path denied: .env  文件未落地

[3/4] 工具挂掉自动恢复   DEGRADE
  原因  下游失败 timeout，工具 demo__downstream 降级，不编柜数/xyz。
  动作  degrade  审计 ['call', 'retry', 'degrade']
  结果  can_fit=UNSPECIFIED  不编柜数

[4/4] 成本超限熔断   CIRCUIT
  原因  熔断：session 成本超限 steps 1/1 tokens 32/32。
  代码  circuit_open  已执行=False

submit_blocked=true  secret_leak=false  禁止：可以投标 / 可以开工
```

</details>

**是什么** — 装箱引擎 `pack-ship` 已做评测；另外 65 岗是 SOP 技能，深度见下表，不是 65 个引擎。工作台覆盖土木 / 施工 / 投标 16 大类。每岗一份 `SKILL.md` 按 SOP 出稿；**硬数字（坐标、柜数、单价）只由确定性工具算**，模型负责路由和起草；资格、投标、写盘这类高风险动作**须人确认**。产出是内部讨论草稿，不是签认件。CI 每次提交只跑 2 lane × 1 round 离线切片，128 次全量评测是另一次留档复跑。CAD、施工计划和箱单台账是预览工具，不是签认模型。

**给谁用** — 物机 / 物流 / 投标岗的日常起草与装柜计算。装箱引擎 pack-ship 是其中一岗，也是前身独立仓 `packing-agent`（已并入本仓，旧链接自动跳转）。

**凭什么可信** — 每一条都有可复跑的命令：

| 证据 | 数字 | 复跑 |
|---|---|---|
| 66 岗诚实分级 | L1 知识库 66/66 · L2 工具写盘 66/66 · L3 引擎岗 1 | [docs/depth-ladder.md](docs/depth-ladder.md)（每级挂验收命令） |
| 自动化装箱评测 | **128** 次（16 并发 × 8 轮），2026-09-02 复跑 **128/128 PASS**。PASS 只表示流水线跑完并返回了柜数与 `can_fit`，不表示都装得下：其中 `can_fit=True` **71/128**，其余 57 次 `can_fit=False` 交回人改方案 | [留档](docs/eval/fanout16x8-2026-09-02/rollup.md)（128 条逐次记录）· `python scripts/fanout16x8_online_cargo.py`（联网抓公开货样约 4 分钟；`--skip-fetch` 用仓内 `data/external/fanout16x8/` 缓存可离线跑）· 本表数字由 `python scripts/render_eval_table.py --check README.md` 对留档核对（CI）· CI 每次提交跑 2 lane × 1 round 离线切片 |
| steps 主路径 vs LLM 自主调工具 | 影子评测（steps 臂 vs `llm_toolcall` 臂），CI 每次提交都跑 tiny 一例 | `python scripts/eval_workteams_cli.py --tiny-only`。**CI 里没有 Key**：llm 臂的工具选择走 `policy_fallback`（`harness._path_honesty` 会标出），CI 证明的是链路与两臂一致性检查，不是真模型的表现 |
| Agent 中间件四拍剧本 | 正常放行 → 越权被拒 → 工具故障重试降级 → 成本超限熔断 | `python scripts/demo_agent_middleware.py`（无需 Key）· 断言版 `python scripts/test_agent_middleware.py` 与 `npm run check` 在 CI 每次提交都跑 |
| 端到端金线 | 8/8（R13 时点实测，需 playwright，未进 CI） | `python scripts/r13_golden_path_e2e.py` |

**试用（零编译）** — 下载 [Releases](https://github.com/LUOaini1213/civil-buddy/releases) 的 **v0.4.0-workbench** zip → 双击 `start-workbench.bat`（浏览器自动打开 :8765）→「设置 → 模型设置」填自己的 Key（DeepSeek / z.ai / OpenAI 兼容任选，运行时生效）。
试用包**不含装箱引擎**；要看真柜数需源码起装柜台：`pip install -r requirements.txt` → `uvicorn gateway.app:app --port 8000`。边界见 [TRY.md](TRY.md)。

**提交署名说明** — 仓内约 40% 的提交署名为 `Packing Assistant`：agent 起草并落盘的改动独立署名，经人审后合入 `main`。这是 HITL 流程的一部分，不是第二位作者。

> 内部讨论草稿，不是法定专项方案、不是签认件。
> 高风险写盘前确认句：`我明白，将由持证人员签认`。

**竞赛材料（海之子杯 2026 · AI 智能体挑战）** — 评审维度对照、可复跑命令与 23 轮 UX 迭代记录移至 [docs/submission/haizizhi-entry.md](docs/submission/haizizhi-entry.md)；Agent Middleware 赛道对照表（**按赛题 checklist 自评**，非官方评审）见 [docs/civil-buddy/track1-qualified.md](docs/civil-buddy/track1-qualified.md)。同一仓库也是 NUS-ISS「Show Me Your Agents」2026 的参赛项目（提案 2026-09-28）：英文对照表、可复跑命令与边界见 [docs/submission/nus-iss-entry.md](docs/submission/nus-iss-entry.md)；两赛口径互不通用。

---

## 两套入口

| 入口 | 地址 | 用途 |
|------|------|------|
| **零编译试用** | Releases exe → :8765 | 双击即用；不含装箱引擎（边界见[TRY.md](TRY.md)） |
| **Civil Buddy 工作台** | http://127.0.0.1:8765 | 召唤专家、投标/施工草稿、装箱作业单 |
| **主线 C · 投标应答 + 交付** | http://127.0.0.1:8000 | 招标要点 → 响应矩阵 → 装柜证据（草稿） |
| **工程装柜台** | http://127.0.0.1:8000/workbench | 成箱 → HITL → 拼柜 3D / CoG |
| **用户路径 / PRD** | [prd-pack-ship.md](docs/civil-buddy/prd-pack-ship.md)（含 Mermaid 流程图，GitHub 直接渲染） | 流程图 + 验收表 |

### 1) Civil Buddy 工作台

```powershell
cd workbench
# API Key：启动后在界面「设置 → 模型设置」填即可（推荐）；或写 gitignored 的 demo/.env
cargo run --release --bin civil-workbench
```

Python 参考实现：`demo/`（`uvicorn app:app --host 127.0.0.1 --port 8765`）。

**语音输入（可选）**：输入框左边的「语音」按钮，说完只把文字回填到输入框、**不会自动发送**，核对后自己按发送。Python 参考实现装了 `requirements-asr.txt` 后用本机 faster-whisper 识别（带 35 个土木术语的提示，录音不出本机）；否则退回浏览器自带识别，首次使用前说明录音会发给浏览器厂商。设计与边界见 [docs/voice-input.md](docs/voice-input.md)，术语表修好了什么、没修好什么见 [eval/asr](eval/asr/README.md)。

产品 CLI（土木版 Codex）：`python -m packing_assistant.civil`（TUI）· `python -m packing_assistant.civil app` · `python -m packing_assistant.civil mcp --pack construction`。像 Codex 在仓库里工作一样，`civil` 在**工地文件夹**里工作：`civil init` 写一份 `CIVIL.md`（本工程说明，相当于 AGENTS.md，写明的项目 / 辖区 / 业主会进成稿，留空的保持 `UNSPECIFIED`），之后在该文件夹或其子目录里运行，会话与文书落在 `<工地>/.civil-buddy/out`；`civil -C <文件夹>` 等同于先 cd；`civil exec --jsonl` 逐行输出事件流，`civil status` 看当前文件夹、沙箱、审批与模型。一轮任务有两种跑法：默认 `steps`（规则路由 + 确定性流程，不调模型）；`civil --mode model`（或 TUI 里 `/mode model`）换成模型驱动——模型自己列步骤、选岗位、读文件夹里的资料、调 `run_skill` / `pack_plan` / `tender_compare`，高风险岗位当场问确认句。模型写的字进不了成稿（交给流程的只有你的原话和你文件夹里的资料），回复里没有出处的数字会被改写或点名（基准 `test/benchmarks/number_provenance`，37 例 P/R 1.000）。模型用 `CIVIL_API_BASE` / `CIVIL_API_KEY` / `CIVIL_MODEL` 配，本机 Ollama 即可：`CIVIL_API_BASE=http://127.0.0.1:11434/v1 CIVIL_API_KEY=ollama CIVIL_MODEL=qwen2.5:3b`。两种跑法都读你点名的文件：`civil exec "packing.csv 要几个柜"` 由装箱引擎真算并留下 `pack-plan.md`，缺重量或尺寸的行逐条列出、不给柜数；`civil exec "解析招标 招标文件.docx"` 解析的是那份文件。完整走法见 [docs/civil-buddy/civil-cli.md](docs/civil-buddy/civil-cli.md)。系统级沙箱（`--sandbox-backend os`：工具在被内核限制的进程里跑，Linux 用 Landlock + seccomp，Windows 用 Low 完整性级别 + Job 对象；`civil sandbox` 当场自检）见 [docs/civil-buddy/os-sandbox.md](docs/civil-buddy/os-sandbox.md)。自己公司的岗位做成插件装进来（`civil plugin install examples/plugins/site-forms`：SOP + 表单模板 + 知识，纯声明、不含代码；未受信任一律按高风险）见 [docs/civil-buddy/plugins.md](docs/civil-buddy/plugins.md)。不想用终端：`civil desktop` 打开原生桌面窗口（Tk，不用装任何东西；对话、逐步进度、审批对话框、双击打开成稿、复核），见 [docs/civil-buddy/desktop-app.md](docs/civil-buddy/desktop-app.md)。`civil review <文稿>` 不调模型，列出文稿里在工地资料中找不到出处的数字、条款号，以及「已具备报审条件」这类不该由文稿下的结论（退出码 0 干净 / 1 有待核对 / 2 审不了）。技能一岗一份：`.agents/skills/<id>/SKILL.md`。IDE：`ide/README.md`。Grok 总控：`skills/civil-buddy`。  
**全量产品规划书**：[docs/civil-buddy/product-plan.md](docs/civil-buddy/product-plan.md)。切片执行：[product-completion-plan.md](docs/civil-buddy/product-completion-plan.md)。

### 2) 装箱引擎（pack-ship 的计算器）

```powershell
pip install -r requirements.txt
python scripts/demo_agent_middleware.py      # 冒烟（四拍剧本），无需 API Key
python scripts/demo_one_shot.py --all        # 产品冒烟 + tiny 闭环 + 影子评测，无需 API Key
python scripts/test_trace_artifact_export.py # SQLite / JSONL 失败恢复、快照与终止事件回归
python scripts/test_storage_ensure_run.py    # issue #22 回归：run_start 先于会话落盘时不再触发外键回退（CI 覆盖）
uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

工作台默认在同一仓库里找引擎：`PACKING_AGENT_ROOT` = 本仓根。也可另开网关：

```env
PACKING_AGENT_URL=http://127.0.0.1:8000
```

详见 [docs/civil-buddy/packing-agent.md](docs/civil-buddy/packing-agent.md)。

---

## 仓库结构

```
workbench/           # Civil Buddy Rust 工作台 + MCP
demo/                # 专家知识库 kb/ + Python 参考实现
.agents/skills/      # Codex：66 岗各一份 SKILL.md
skills/civil-buddy/  # Grok 总控 SOP
packing_assistant/   # 装箱 harness（Team A 成箱 + Team B 拼柜）
gateway/ + frontend/ # 装箱 HTTP / UI
docs/civil-buddy/    # 工作台设计、专家名册
docs/                # 装箱架构与产品主线
```

**原则（两套入口共用）：** tools compute numbers; the model only routes.

---

## 装箱引擎（原 packing-agent）

架构：**大 Team ⊃ Team A（成箱）+ Team B（拼柜）** · Harness 0.6.4  
NL → IntentSpec → 白名单 tools → HITL → 影子评测。

![Packing HITL graph](docs/diagrams/langgraph-create-app.jpg)

```powershell
python scripts/test_p0_p1_p2_full.py              # P0–P2 全链（CI 覆盖）
python scripts/eval_workteams_cli.py --tiny-only      # steps vs llm 影子评测（CI 覆盖）
```

文档：[docs/harness-design.md](docs/harness-design.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/product-mainline-tender-delivery.md](docs/product-mainline-tender-delivery.md)

---

## 环境变量

复制 `.env.example` / `demo/.env.example`，不要提交密钥。

| 变量 | 说明 |
|------|------|
| `CIVIL_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` | 成稿用的 Chat Completions Key（自选；DeepSeek 可选） |
| `CIVIL_API_BASE` / `OPENAI_BASE_URL` | 兼容网关，例 `https://api.openai.com/v1` |
| `CIVIL_MODEL` / `LLM_MODEL` | 模型名，须与网关一致 |
| `CIVIL_JOB_ROOT` | 授权作业文件夹（禁止 `D:\layout`） |
| `PACKING_AGENT_URL` | 装箱网关（可选） |
| `PACKING_AGENT_ROOT` | 默认本仓根，一般不用设 |
| `CIVIL_PORT` | 工作台端口，默认 8765 |

---

## 明确不做

桌面键鼠、微信/飞书、Rhino/Civil3D 改模、注册工程师签认、编造条款/单价/xyz。规范全文不进仓库。
