# Agent 有没有用？和订柜脚本差在哪

## 先说清楚：你现在的感觉从哪来

| 路径 | 是否过 9 Agent | 用途 |
|------|:--------------:|------|
| `demo_vmu1_site.py` / `run_vmu1_site_only.py` | **否** | 比赛主案例数字：**当量成箱 + booking 订柜 + 3D** |
| `main.py --demo` / `gateway /api/demo` | **是** | 多智能体闭环演示 |
| `dump_nine_agents.py` / `demo_nine_agents_trace.py` | **是** | 逐步打印每个 Agent 输出 |

**订舱数字**主要来自 **tools**（`volume_estimate` / `booking` / `bin3d` / `packing`）。  
**Agent 不是第二个算柜公式**，而是：分工、闸门、结构、风险、出图、可讲的过程。

所以：若只用 `demo_vmu1_site.py` 看 N0，**确实会感觉「有没有 Agent 都一样」**——因为那条路径故意不绕 9 Agent，保证 10 分钟稳定出数。

---

## 每个 Agent 干什么（工具在底下）

```text
用户/API
  → 1 主控 orchestrator     意图、推荐柜型、利用率目标
  → 2 材料 material_parser  文本/表 → materials[]（可 inject 跳过解析）
  → 3 结构 structure        箱型/加固建议（半严格）
  → 4 装箱 box_scheme       调 packing → boxes[] + 结构结论
  → 闸门 present_team_a     **必须确认**才拼柜（HITL）
  → 5 规划 planner          调 booking → **N0**，装载策略
  → 6 装载 loader           调 bin3d/booking → layout + 双率
  → 7 评估 evaluator        评分、是否 replan（不加柜硬凑）
  → 8 风险 risk_compliance  超重/结构/可疑体积 → PASS/WARN/REJECT
  → 9 可视化 visualizer     三视 + 双率文案
  → 主控收口 finalize       可出运裁决 + 摘要（LLM 不改数字）
```

| Agent | 没有它会怎样 | 关键 tools |
|-------|--------------|------------|
| 主控 | 无统一选柜/目标 | `container_select` |
| 材料 | 无法从自然语言进流水线 | 解析/注入 |
| 结构 | 无半严格箱型建议 | `structure_calc` |
| 装箱 | **没有 boxes[]** | `packing` |
| 确认闸门 | 自动乱拼柜，无人工点 | harness |
| 规划 | 无 N0/优先序说明 | `booking.compute_booking` |
| 装载 | 无 layout / can_fit | `booking` + `bin3d` |
| 评估 | 无 score / replan | 规则评分 |
| 风险 | 装得下≠可出运 | `risk_rules` |
| 可视化 | 无三视图 | `visualize` |
| finalize | 无对外裁决文案 | 可选 LLM 润色 |

**数字铁律：** 柜数/重量/体积由 tools 算；LLM 只润色，不改 N0/can_fit。

---

## 两条路径怎么讲（答辩用）

1. **业务订舱路径（当前主案例）**  
   工地当量箱 → `compute_booking` → N0；3D 校验。  
   **快、稳、数字与领导 2 柜对齐。**

2. **多智能体工程路径（架构分）**  
   材料→结构→成箱→**确认**→规划→装载→评估→风险→出图。  
   **可解释、可拦截、可 API 编排**；二次标准箱合箱可能与当量路径数字不同（要诚实讲）。

---

## API 怎么测 Agent

```bash
# 终端 1
uvicorn gateway.app:app --reload --port 8000

# 终端 2：逐步 trace（推荐，能看见每个 agent）
python scripts/demo_nine_agents_trace.py

# 或 curl 全流程（自动确认）
curl -s -X POST http://127.0.0.1:8000/api/demo -H "Content-Type: application/json" -d "{\"user_input\":\"演示材料清单\",\"container_type\":\"40HQ\"}"

# 团队 A → 确认 → 团队 B（显式闸门）
curl -s -X POST http://127.0.0.1:8000/api/team-a -H "Content-Type: application/json" -d "{\"session_id\":\"s1\",\"user_input\":\"演示材料清单\"}"
curl -s -X POST http://127.0.0.1:8000/api/confirm -H "Content-Type: application/json" -d "{\"session_id\":\"s1\",\"action\":\"confirm\",\"container_type\":\"40HQ\",\"max_containers\":0}"
```

`max_containers=0`：自主定柜（N0 起试），**不要传 2 当业务目标**。

---

## 和「纯 tools 脚本」对照怎么测

```bash
# 仅 tools（无 Agent 编排）
python scripts/demo_vmu1_site.py

# 完整 Agent 链（有过程消息）
python scripts/demo_nine_agents_trace.py
python scripts/dump_nine_agents.py
```

看差别时盯：

- 有没有 **确认闸门**  
- 有没有 **结构结论 / REJECT**  
- 有没有 **逐步 messages**  
- N0 是否仍来自 booking（应一致逻辑，输入 boxes 不同则数字可不同）
