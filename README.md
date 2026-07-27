# 智能装箱与拼柜 · 多智能体 Harness

面向 **远东新加坡陆路交通局办公楼项目** 钢结构件：

**材料清单 → 铁箱/木箱（结构计算）→ 集装箱拼柜装载 → 风险合规 → 三视图**

仓库：https://github.com/LUOaini1213/packing-agent

---

## 整体架构（9 智能体 + 用户确认）

```text
用户输入（材料清单 / PDF / Excel）
              │
              ▼
┌─────────────────────────────────────────────────┐
│  1 主控智能体（开头）                              │
│  · 意图与 9 智能体调度                             │
│  · 柜型推荐 20GP / 40GP / 40HQ                    │
│  · 空间/重量双利用率目标                           │
│  · 二层堆码策略                                    │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  团队 A · 装箱方案                                 │
│  2 材料解析 → 3 结构约束 → 4 装箱方案（合箱+结构）  │
└──────────────────────┬──────────────────────────┘
                       ▼
              输出装箱方案（箱号/箱型/外廓/结构结论）
                       ▼
┌─────────────────────────────────────────────────┐
│  ★ 用户确认闸门（必须）                            │
│  确认柜型 / 调整 / 取消                             │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  团队 B · 拼柜方案                                 │
│  5 规划 → 6 装载(3D) → 7 评估 → 8 风险 → 9 可视化 │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  主控收口（结尾）                                  │
│  · 复核柜型（可建议换柜）                           │
│  · 汇总：容积(实心外廓)/重量/风险/三视图            │
└─────────────────────────────────────────────────┘
```

### 智能体职责

| # | 名称 | 职责 |
|---|------|------|
| 1 | **主控** | 开头选柜 + 目标下达；结尾复核柜型与汇总 |
| 2 | 材料解析 | 解析/标准化材料（mm/kg） |
| 3 | 结构计算 | 推荐箱型约束与加固建议（成箱后半严格校核） |
| 4 | 装箱方案 | **标准箱库**合箱（可跨长度档混装）+ 结构计算 |
| ★ | 用户确认 | **必选**柜型后方可进入拼柜 |
| 5 | 规划 | 装载策略：重货底层、并排、二层堆码 |
| 6 | 装载执行 | 3D 摆位（`python-laff-3d` 或可选 skjolber） |
| 7 | 评估优化 | 空间/底面积/重量打分，是否 replan |
| 8 | 风险合规 | 偏心、超重、双低利用率、合规分 |
| 9 | 可视化 | 俯视 / 侧视 / 正视三视图 |

> 详细架构见 [docs/overall-architecture.md](docs/overall-architecture.md)

### 数据流（简）

```text
materials[] ──► boxes[]（外廓实心长方体）──► container_plan + layout
                      │                            │
                      │                            ├─ space_utilization
                      │                            ├─ weight_utilization
                      │                            └─ views.top/side/front
                      └─ structure_calc / content
```

**容积定义**：Σ(铁箱/木箱 **外廓** L×W×H) ÷ 柜内几何容积（`solid_outer_aabb`），不是零件镂空体积。

### 装箱模式（`packing_options`）

| 选项 | 默认 | 含义 |
|------|------|------|
| `standard_boxes` | **true** | 外廓锁定知识库标准箱（1.1/2/3/4/6 米铁架等）；仅最长件超标时「标准加长」 |
| `mix_mode` | **true** | **跨长度档混装**：短件可塞进更长档标准箱填空（如垫片/短支撑并入 4 米铁架） |
| `dense_mode` | false | 贴货定制外廓（与 standard 互斥；standard 优先） |
| `max_box_net_kg` | 3200 | 单箱净重上限（超则拆分；标准箱对长件会再收紧） |

```python
state["packing_options"] = {
    "standard_boxes": True,   # 箱子标准化
    "mix_mode": True,         # 允许混装
    "max_box_net_kg": 1500,
}
```

自测其它例子：`python scripts/test_standard_mix_examples.py`

---

## 设计原则

- **计算用代码**：结构、合箱、3D 装载、规则评分
- **LLM 可选**：意图、解析辅助、风险解释、文案润色（DeepSeek 等）
- **接口**：snake_case，单位 mm / kg，Agent 间只传标准 JSON

---

## 目录结构

```text
packing_assistant/     # 核心：agents / tools / harness / graph
  agents/              # 9 智能体 + present 闸门
  tools/               # packing / bin3d / structure / container_select
gateway/               # FastAPI 网关
frontend/              # Vue2 CDN 演示页
knowledge/             # 装箱知识库 JSON
scripts/               # 批跑、基准、Excel、选柜对比
docs/                  # 架构与 API 文档
test/                  # PDF 装箱单、Excel 业务集、BPP 基准
eval/                  # 黄金回归用例
skjolber-service/      # 可选 Java skjolber 服务
data/external/         # 公开 3D-BPP 样例
```

---

## 快速开始

### 比赛演示主路径（优先 · 10 分钟）

主案例：**VMU1 送工地** — 订柜用有效体积（N0），外廓只做 3D；**不写死柜数**。

```bash
pip install -r requirements.txt

# ① 一键演示：工地 Excel → N0 / 3D / 结论包
python scripts/demo_vmu1_site.py --with-shipped

# ② 提交前必跑（booking 回归 + P2 门禁 + 工地案例）
python scripts/run_precommit_tests.py

# 仅算法、不跑 Excel
python scripts/run_precommit_tests.py --quick
```

| 产物 | 路径 |
|------|------|
| 标准产物包 | `output/demo_package/latest/` |
| 结论 MD | `…/VMU1_送工地_剩余装柜估算.md` |
| 数字 JSON | `…/vmu1_site_only_pack.json` |
| 周清单 | [docs/week1-demo-checklist.md](docs/week1-demo-checklist.md) |

**创新点一句：** 多智能体成箱+拼柜；订柜用有效体积、外廓只做 3D；避免空心包装虚高柜数。

### 演示 A + B（提交准必须）

| 演示 | 命令 | 评委问题 |
|------|------|----------|
| **A 数字** | `python scripts/demo_vmu1_site.py` | 订舱准吗？N0≈2，不虚高 |
| **B Agent+API** | `powershell -File scripts/start_gateway.ps1` 另开终端：`python scripts/demo_nine_agents_trace.py --via-api` | 智能体闭环？确认闸门 / 风险 REJECT / steps |

- 柜数由 **tools** 算；API 把 9 Agent **产品化**，不另算一套柜。  
- 详解：[docs/agents-vs-tools.md](docs/agents-vs-tools.md) · 提交粘贴稿：[docs/submission-demo-A-B.md](docs/submission-demo-A-B.md)

### 安全（必读）

- **不要提交** `deepseek api.txt`、`.env`、任何 `*apiKey*`（已在 `.gitignore`）
- 复制 `.env.example` → `.env`，填入自己的 LLM Key

```bash
# 全流程演示（主控自动选柜 + 自动确认）
python main.py --demo --trace

# 只跑团队 A → phase=await_user_confirm
python main.py --team-a

# 交互：团队 A → 输入柜型 → 团队 B
python main.py --interactive

# 回归
python main.py --eval
```

### 网关 + 前端（无需 Java）

本机若用不上 JDK，默认 **纯 Python 3D 装载**（`python-laff-3d`），接口与 skjolber 对齐，Vue2 可画三视角。

```bash
python -m uvicorn gateway.app:app --reload --port 8000
# 浏览器 http://127.0.0.1:8000
```

### 常用脚本

```bash
# test/ 装箱单 PDF · 同一项目拼柜
python scripts/run_test_shipments.py

# 远东 Excel → test/excel 业务集
python scripts/build_steel_test_set.py
python scripts/run_excel_tests.py

# 公开 BPP 基准
python scripts/fetch_external_datasets.py
python scripts/convert_bpp_to_cases.py
python scripts/run_benchmark_cases.py

# 20GP / 40GP / 40HQ 对比
python scripts/compare_container_types.py

# 9 智能体逐步输出
python scripts/dump_nine_agents.py
```

---

## 代码映射

| 路径 | 对应 |
|------|------|
| `agents/orchestrator` | 主控开头 |
| `agents/material_parser` | 材料解析 |
| `agents/structure_agent` | 结构约束 |
| `agents/box_scheme` | 装箱方案 |
| `agents/present_team_a` | 用户确认闸门 |
| `agents/planner` | 规划 |
| `agents/loader` | 装载（主路径 python-laff-3d） |
| `agents/evaluator` | 评估 |
| `agents/risk_compliance` | 风险合规 |
| `agents/visualizer` | 三视图 |
| `agents/finalize` | 主控结尾汇总 + 选柜复核 |
| `tools/container_select.py` | 柜型选型 |
| `tools/bin3d.py` | 3D 装载与实心容积 |
| `tools/packing.py` | 合箱与外廓模块化 |
| `harness.run_team_a / run_team_b` | 主控门面 |

### 技术栈

- 编排：Python / LangGraph + **FastAPI**
- 装载：默认 **python-laff-3d**；可选 **Java Spring Boot + skjolber**（`skjolber-service/`）
- 前端：`views` → **Vue2**（`frontend/index.html`，CDN 无 npm）

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/overall-architecture.md](docs/overall-architecture.md) | **完整架构（最终版）** |
| [docs/team-a-user-output-template.md](docs/team-a-user-output-template.md) | 团队 A 用户输出模板 |
| [docs/api-spec.md](docs/api-spec.md) | JSON 接口定稿 |
| [docs/phase2-agent2-packer-api.md](docs/phase2-agent2-packer-api.md) | skjolber 封装参考 |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | 打包与目录速览 |
| [knowledge/README.md](knowledge/README.md) | 知识库说明 |
| [test/excel/README.md](test/excel/README.md) | 钢结构 Excel 测试集 |
| [test/benchmarks/README.md](test/benchmarks/README.md) | 公开 3D-BPP 基准 |

---

## 环境变量（摘要）

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | LLM（可选） |
| `LLM_MODEL` | 默认 deepseek-v4-flash |
| `SKJOLBER_URL` | 有 Java 服务时指向 skjolber |
| `PACKING_KB_PATH` | 自定义知识库路径 |

详见 `.env.example`。

---

## License

项目代码按仓库声明使用；业务样例数据仅用于演示与测试。
