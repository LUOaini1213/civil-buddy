# 与 AI Agent 定义对齐（工程型多智能体）

## 一句话（答辩）

> 系统具备感知（清单与状态）、规划（主控/订柜策略）、工具调用（成箱/体积/3D）、行动（产出方案与图）与目标推进（流水线至 finalize）；**关键数值由工具计算**，智能体负责**分工、确认与合规拦截**，保证可验证而非只给建议。

---

## 五条能力对照

| 定义能力 | 具备？ | 落点 | 待增强（可选） |
|----------|--------|------|----------------|
| **感知环境** | 有（数据感知） | Excel/JSON 材料、知识库、layout/风险状态 | 统一 `state_snapshot` 字段给每步 Agent 只读摘要 |
| **推理与规划** | 有（规则+编排） | 主控选柜；planner→N0；evaluator replan | 规划消息显式列出「调用了哪些 tools」 |
| **使用工具** | **核心强项** | packing / volume_estimate / booking / bin3d / structure / visualize | trace 里带 `tools_used[]` |
| **采取行动** | 有（系统内） | 写 boxes、layout、报告、图、API | 保持；不接真实订舱/ERP |
| **追求目标** | 部分 | 跑完成箱→确认→装载→风险→finalize；可 HITL | 目标写清：`goal=deliver_valid_pack_plan` |

---

## 和「经典单体 Agent」差在哪

```text
经典：一个 Agent 自己循环感知→规划→工具→行动直到成功
你们：多智能体流水线 + tools 算数 + 可选人工确认
```

| 点 | 说明 |
|----|------|
| 形态 | **Agentic Workflow / Multi-Agent System** |
| 自主 | demo 可自动确认；正式可 HITL |
| 目标域 | 成箱/订柜/拼柜/合规，非通用助理 |
| 双路径 | booking 脚本可几乎不「聊天」，仍用同一 tools |

**不算减分**：工程可控、可验证，比「只会聊天不会执行」更强。

---

## 建议增强优先级（对齐 Agent，不换架构）

### P0 · 叙事与可演示（必做，低成本）

1. 答辩固定上表 + 一句话  
2. 演示 **A 数字 + B Agent API**（已有）  
3. 明确说：不是五项全能聊天窗，是**分角色流水线**

### P1 · 让「用了工具」可见（推荐，小改）

1. 每步 Agent 输出带 `tools_used` / `artifacts`（boxes 数、N0、can_fit）  
2. `demo_nine_agents_trace` / `/api/pipeline/trace` 已接近，补全字段即可  
3. finalize 摘要固定出现「工具计算结果，非 LLM 编造」

### P2 · 目标与循环更清楚（有空）

1. state 里显式 `goal` / `goal_status`  
2. replan 循环在消息里写「第 k 次因 xxx 重规划」  
3. 当量直通路径标 `mode=crate_passthrough`（已有）

### 不做（伪对齐）

- 为「像 Agent」硬上无约束 LLM 直接报柜数  
- 为自治去掉确认闸门  
- 上通用 AutoGPT 式无限循环  

---

## 双路径在 Agent 定义里的位置

| 路径 | Agent 浓度 | 仍是「智能系统」吗 |
|------|------------|-------------------|
| `demo_vmu1_site` | 低（tools 直调） | 是工具链；比赛用讲**数字** |
| 9 Agent + API | 高 | **主 Agent 叙事** |
| 当量直通 9 Agent | 高且数字准 | **最佳两者兼顾** |

---

## 完成态（Agent 叙事）

```text
□ 能画出 5 能力→模块映射表
□ 能跑 trace 逐步 message + tools 结果
□ 能举 can_fit 仍 REJECT 的行动/拦截例
□ 能说明 HITL 闸门是可控自主，不是缺能力
□ 不声称「单一全能 Agent」
```
