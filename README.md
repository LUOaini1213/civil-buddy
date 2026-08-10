# 智能装箱与拼柜 · packing-agent

> **Agent Harness / workbench**：NL → 白名单 tools → HITL → 影子评测 · 推理侧可接 **DeepSeek API**  
> 原则：编排可换模型，**硬数值只走工具**（与 Agentic Coding 产线同一边界）。

**Harness v0.6.4**（2026-07-30）  
架构：**大 Team ⊃ 小 Team A（成箱）+ 小 Team B（拼柜）** · 多节点名册  
NL 通用 Agent · 多工具求解 · 有界 critic · HITL · shadow eval  

Repo: https://github.com/LUOaini1213/packing-agent  

> **First principle:** tools compute numbers; the model (if any) only routes.  
> Geometry / counts are **never** free-written by the LLM.

---

## Demo one-shot（最先跑这个）

```bash
pip install -r requirements.txt
python scripts/demo_one_shot.py              # 冒烟，无需 API Key
python scripts/demo_one_shot.py --all        # smoke + 闭环 + tiny 影子评测
```

成功后再开 UI：

```bash
uvicorn gateway.app:app --reload --host 127.0.0.1 --port 8000
# http://127.0.0.1:8000
```

贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)

---

## Architecture as Harness

把本仓库当成 **Agent Harness**，而不是「只会装箱的脚本」：

| Layer | 本仓库对应 | 作用 |
|-------|------------|------|
| **Runtime** | Big Team 编排 · A/B subagents · `harness.py` · HITL · `steps` / `llm_toolcall` | 谁在何时跑、如何停 |
| **Tools** | `tool_registry` 白名单 · 确定性求解器 | 算体积/装载/重心；禁止模型写 xyz |
| **Memory** | session · artifacts · knowledge/skills · graph checkpoint | 有界状态，不是无限闲聊记忆 |
| **Eval** | `eval_workteams` · KPI（agree_core / illegal tools） | steps vs llm 影子对比 |
| **Trace** | `agent_steps` · trace events · SSE · `output/runs/` | 可演示、可回归 |

```text
NL (+ materials)
  → IntentSpec
  → Runtime scheduler (steps | llm_toolcall | auto)
       → Subagent A → Tools → HITL
       → Subagent B → Tools (3D / CoG / risk)
       → Finalize (+ optional TMS)
  → Trace + Artifacts
  → Eval / KPI (CI or shadow)
```

**长文（投递 / 面试前读）：**  
- [docs/harness-design.md](docs/harness-design.md) — **设计决策表（tool / HITL / Subagent / eval）· 面试优先**  
- [docs/architecture-as-harness.md](docs/architecture-as-harness.md) — 层映射 Runtime·Tools·Memory·Eval·Trace  

域内架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · 文档索引：[docs/README.md](docs/README.md)

---

## 它做什么（业务皮肤）

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
柜级：`N0* → 试装 → 末柜可并回`；柜内：`multi_start` 优化摆法。

**主路径（对外只讲这一条）**

| 路径 | 用途 |
|------|------|
| **`agent_mode=steps`（默认）** | 生产 / 答辩 / 基线：大 Team 固定专业节点调度 |
| `llm_toolcall` | 实验 / 影子评测（有 Key 时 LLM 选工具） |
| `graph` / team-a→confirm | HITL 分段 resume，不是第二条产品 |

业务场景名（如某次「1 柜 / 2 柜」）仅为示例，不是固定线路。

---

## 仓库结构

```text
packing_assistant/   # harness 核心（teams / agents / tools / IntentSpec）
gateway/             # FastAPI runtime 网关
frontend/            # 单页工作台
test/sim_materials/  # 评测物料
scripts/             # demo_one_shot / smoke / eval（见 scripts/README.md）
docs/                # architecture-as-harness + 产品文档
.github/             # Issue / PR 模板
data/samples/        # 可选公开样例
output/              # 本地产物（gitignore）
```

---

## 快速开始（分项）

```bash
python scripts/demo_one_shot.py
python scripts/smoke_agent_product.py
python scripts/demo_agent_closed_loop.py --tiny
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

## Contributing & community

- [CONTRIBUTING.md](CONTRIBUTING.md)
- Issues: Bug · Feature · **Harness design** · Phase1/2 域任务
- PRs welcome if they respect the **tools-compute / model-routes** boundary

---

## 许可与项目说明

开源作品集 / 研究向 **Agent Harness** 原型（装箱域）。  
业务数据请勿提交密钥与客户原始大文件；样例放 `data/samples/` 或 `test/sim_materials/`。
