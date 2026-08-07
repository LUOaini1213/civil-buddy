# 架构：大 Team ⊃ 小 Team A + 小 Team B（NL 通用 Agent）

> 版本：harness **0.6.4** · 名册 **13** agents（大 Team ⊃ A/B）
> 龙申 1 柜 / 工厂 2 柜等 **只是例子**，不是固定业务线。

## 组织

| 层级 | 职责 |
|------|------|
| **大 Team** | 编排 · HITL 闸门 · 有界 critic · 收口 |
| **小 Team A** | 成箱：材料解析 → 结构 → 装箱方案 → 展示 |
| **小 Team B** | 拼柜：规划 → 3D/CoG 装载 → 评估 → 风险 → 可视化 |

## Agent 人设

- **主输入**：自然语言（+ 可选物料表）
- **形态**：通用装柜 Agent，按意图调度多工具
- **契约**：`IntentSpec`（`intent_spec.py`）
- **硬边界**：tools 算数；禁止 LLM 写 xyz / 柜数拍脑袋

## 主路径

```
NL → IntentSpec → 大Team.orchestrator
  → 小TeamA（成箱）→ HITL
  → 小TeamB（规划/装载/评估 内环≤3）
  → risk；出运外环≤2（可打回 B 或 A）
  → visualizer → 大Team.finalize
```

入口：`run_agent_pipeline` / `iter_agent_pipeline`

| agent_mode | 路径 | 对外叙事 |
|------------|------|----------|
| **`steps`（默认 · 主路径）** | `teams.big_team` 固定专业节点 | **生产 / 答辩 / Phase0 基线只讲这条** |
| `llm_toolcall` | `agent_loop` LLM 多轮 tool-call（无 Key → policy fallback） | 影子评测 / 加分 demo |
| `auto` | 有 LLM Key 则 tool-call，否则 steps | 可选 |
| `graph` | LangGraph 全图（gateway mode=graph） | HITL 分段，非第二产品 |

### Team B 有界辩论（非 free swarm）

当 `evaluation.need_replan` 时，默认跑 **critic ↔ planner 1～2 轮**（`bounded_debate.py`）：

1. **replan_critic** 提案（改 `packing_options` / route，不写 xyz）  
2. **planner** 确定性反方（如反对无脑加柜 → densify）  
3. 可选 critic 收口  
4. **tools** 重跑 planner/loader 裁决装载  

关闭：`packing_options.bounded_debate=false`。  
`public_response.bounded_debate` 含 transcript；**不是**多 LLM 自由 swarm。

Agency 作战图：[competition-phase-plan.md](./competition-phase-plan.md)

分段 resume（旧 A/B 子图）:

- `POST /api/team-a` → HITL → `POST /api/confirm` 或 `POST /api/resume/{id}/team-b`
- `GET /api/resume/{id}` 查看磁盘 / LangGraph 是否可恢复
- 实现：`graph.py` + `graph_resume.py` + `lg_checkpoint`

## 代码地图

| 模块 | 作用 |
|------|------|
| `intent_spec.py` | NL → IntentSpec |
| `tool_registry.py` | 工具分簇 big/A/B |
| `teams/roster.py` | 名册与架构描述 |
| `teams/team_a.py` | 成箱节点 |
| `teams/team_b.py` | 拼柜节点 |
| `teams/big_team.py` | 大 Team 编排主循环 |
| `harness.py` | 对外 API 门面 |
| `agents/*` | 各角色实现 |
| `tools/*` | 确定性求解 |

## API

- `POST /api/pipeline` — 大 Team 全流程（`agent_mode=steps|llm_toolcall|auto`）
- `GET /api/architecture` — 架构元数据
- `GET /api/tools` — 工具注册表
- `POST /api/team-a` + `POST /api/confirm` — 分段 HITL
- `POST /api/whatif` — NL what-if（同 IntentSpec 族）
- `POST /api/eval/workteams` — steps vs llm 影子评测 + KPI
- `GET /api/kpi/{session_id}` — 单 session 路由/选工具 KPI
- `POST /api/tms/booking/preview|submit` — TMS 订舱（stub/HTTP）
- `GET /api/tms/bookings` — stub 订舱列表

## 评测与 KPI

| 模块 | 作用 |
|------|------|
| `eval_workteams.py` | 同票 steps vs llm_toolcall 影子对比 |
| `workteam_kpi.py` | 覆盖率、非法工具、replan 路由、结果一致性 |
| `scripts/eval_workteams_cli.py` | CI：`--tiny-only` |

目标：`agree_core_rate ≥ 0.90`，`illegal_tool_calls == 0`。

## TMS / 订舱

| 模块 | 作用 |
|------|------|
| `tms_booking.py` | `booking_request.v1` 契约；stub 落盘 `output/tms/`；HTTP 对接 `PACKING_TMS_URL` |

环境：`PACKING_TMS_MODE=stub|http` · `PACKING_TMS_URL` · `PACKING_TMS_API_KEY`
