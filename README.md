# 智能装箱与拼柜 · packing-agent

**Harness v0.6.4**（2026-07-30 · 比赛收尾）  
架构：**大 Team ⊃ 小 Team A（成箱）+ 小 Team B（拼柜）** · **13 节点**名册  
NL 通用 Agent · 多工具求解 · 有界 critic · HITL  

仓库：https://github.com/LUOaini1213/packing-agent  

---

## 它做什么

面向钢结构/项目物料的 **成箱 → 建议柜数 → 人确认 → 拼柜 → 风险/重心 → 出图 → 订舱草稿**：

```text
NL / 物料表
    → IntentSpec
    → 小 Team A：材料解析 · 结构 · 成箱
    → 工具算 N0*（重量/体积/几何下界）与成箱同屏
    → HITL 确认（演示默认不 auto）
    → 小 Team B：3D 实装 used · 柜内 multi_start · CoG · 评估 · 风险 · 可视化
    → 大 Team：有界 replan · finalize · 可选 TMS 订舱
```

数值由 **tools** 计算（含 **几柜**）；LLM 只解释意图 / 调度，**不写 xyz、不拍柜数**。  
柜级：`N0* → 试装 → 末柜可并回`；柜内：`multi_start` 优化摆法（见 `docs/research/multi-container-ffd-agent.md`）。

**主路径（对外只讲这一条）**

| 路径 | 用途 |
|------|------|
| **`agent_mode=steps`（默认）** | 生产 / 答辩 / 基线：大 Team 固定专业节点调度 |
| `llm_toolcall` | 实验 / 影子评测（有 Key 时 LLM 选工具） |
| `graph` / team-a→confirm | HITL 分段 resume，不是第二条产品 |

作战图与基线：[docs/competition-phase-plan.md](docs/competition-phase-plan.md) ·  
`python scripts/run_phase0_baseline.py --quick`

详设：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · 变更：[docs/CHANGELOG-v0.5.md](docs/CHANGELOG-v0.5.md) · 文档索引：[docs/README.md](docs/README.md)

---

## 仓库结构

```text
packing_assistant/   # 核心引擎（teams / agents / tools / IntentSpec）
gateway/             # FastAPI 网关
frontend/            # 单页工作台（三层组织图）
test/sim_materials/  # 评测物料
scripts/             # CI 与正式入口（见 scripts/README.md）
docs/                # 产品文档 + research/ + archive/
data/samples/        # 可选公开样例
output/              # 本地运行产物（gitignore，不提交）
```

---

## 快速开始

```bash
# 依赖
pip install -r requirements.txt

# 网关 + 前端（见 docker-compose 或本地 uvicorn）
uvicorn gateway.app:app --reload --host 0.0.0.0 --port 8000
# 浏览器打开 http://127.0.0.1:8000

# 冒烟
python scripts/smoke_agent_product.py

# Workteams 影子评测（steps vs llm）
python scripts/eval_workteams_cli.py --tiny-only
```

环境变量（可选）：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | LLM tool-call 路径 |
| `PACKING_LLM_AGENT=1` | 强制 LLM 调度 |
| `PACKING_TMS_MODE` | `stub`（默认）/ `http` |
| `PACKING_TMS_URL` | 外部 TMS |

---

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/pipeline` | 大 Team 全流程（`agent_mode=steps\|llm_toolcall\|auto`） |
| POST | `/api/pipeline/stream` | SSE |
| POST | `/api/team-a` · `/api/confirm` | 分段 HITL → Team B |
| POST | `/api/whatif` | NL what-if |
| POST | `/api/eval/workteams` | 影子评测 |
| GET | `/api/kpi/{session}` | 路由/选工具 KPI |
| POST | `/api/tms/booking/submit` | 订舱（stub/HTTP） |
| GET | `/api/architecture` | 架构元数据 |

---

## 版本要点（v0.6）

| 能力 | 说明 |
|------|------|
| 大 Team ⊃ A/B | 编排/闸门/critic/收口 + 成箱 + 拼柜 |
| IntentSpec | NL → 约束与 packing_options |
| LLM tool-call | 白名单工具；无 Key 时 policy fallback |
| 影子评测 + KPI | `eval_workteams` · `workteam_kpi` |
| TMS 订舱 | `tms_booking` 契约 v1 |
| CoG | R0–R4 / LNS / lateral |
| 双利用率 | 订舱 N0 vs 3D 外廓 |

历史：v0.4 详设/NL 改方案 · v0.5 SSE/HITL/Docker — 见 changelog。

---

## 许可与项目说明

内部/比赛向装柜 Agent 原型。业务数据请勿提交密钥与客户原始大文件；样例放 `data/samples/` 或 `test/sim_materials/`。
