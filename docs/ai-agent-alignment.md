# 与 AI Agent 定义对齐（工程型多智能体）

## 一句话（答辩）

> **感知**清单与状态 → **规划**订柜策略 → **调用**成箱/3D/风险工具 → **生成**方案与图 → **推进**至可裁决结论（可 HITL）。  
> 关键数值由 **tools** 计算；智能体负责分工、确认与合规拦截——**可验证而非只给建议**。

---

## 五条能力对照（演示时指哪里）

| 定义 | 演示时指哪里 | 代码/API 落点 |
|------|----------------|---------------|
| **感知** | 解析后的材料摘要 | `perception.json` / 材料 Agent message【感知】 |
| **规划** | N0 与策略说明（3～5 条理由） | `plan.json` → `planning_reasons` |
| **工具** | trace 里的 packing / bin3d / risk | `agent_trace.json` / `steps[].tools_used` |
| **行动** | 生成的文件与图，不是只聊天 | `output/runs/<run_id>/` + 三视图 |
| **目标** | finalize「建议订舱 / 不可出运及原因」 | `goal.json` / `goal_status` |

---

## 单一闭环入口

| 入口 | 作用 |
|------|------|
| `POST /api/pipeline` | **主入口**：自动跑到 finalize；`enable_auto_confirm` 可关；返回 `artifact_paths` + `steps` |
| `POST /api/demo` | 兼容 demo，默认 auto + 落盘 |
| `POST /api/pipeline/trace` | 同 pipeline steps 模式（逐步 tool 轨迹） |
| `run_agent_pipeline()` | Python 同路径 |
| `run_pipeline()` | LangGraph 全图 + 可选落盘 |

### 请求示例

```json
POST /api/pipeline
{
  "user_input": "演示",
  "materials": [...],
  "enable_auto_confirm": true,
  "goal": "deliver_valid_pack_plan",
  "mode": "steps"
}
```

`goal` 可选：`deliver_valid_pack_plan` | `minimize_containers` | `safe_to_ship`。

### 落盘结构

```text
output/runs/<run_id>/
  perception.json   # 件数、总重、过滤规则、柜型假设
  plan.json         # N0 + planning_reasons
  container_plan.json
  risk.md / risk.json  # decision + suggested_actions
  goal.json / finalize.md
  agent_trace.json  # 逐步 tools_used
  views/            # 三视图
  index.json / README.md
```

---

## 和「经典单体 Agent」差在哪

```text
经典：一个 Agent 自己循环感知→规划→工具→行动直到成功
你们：多智能体流水线 + tools 算数 + 可选人工确认（HITL 工具节点）
```

| 点 | 说明 |
|----|------|
| 形态 | **Agentic Workflow / Multi-Agent System** |
| 自主 | demo 可自动确认；正式可 HITL（`hitl.confirm_gate`） |
| 目标域 | 成箱/订柜/拼柜/合规，非通用助理 |
| 失败推进 | can_fit 失败 → N+1 写进 loader `retry_steps` |
| REJECT | 规则建议：减载/换柜/加固/加柜（不 LLM 瞎改数字） |

**不算减分**：工程可控、可验证，比「只会聊天不会执行」更强。

---

## 不必为了「像 Agent」而做的

| 项目 | 原因 |
|------|------|
| 让 LLM 直接算柜数 | 破坏业务口径 |
| 无限自治改 ERP/真订舱 | 超出比赛与安全范围 |
| 换成单体 ReAct 聊天 | 弱化 tools 优势 |
| 摄像头/IoT 感知 | 与赛题无关 |

**对齐定义 ≠ 去掉规则；** 好的 Agent 正是 **规划 + 工具 + 约束**。

---

## 自检清单（五条都要能指着演示）

```text
□ POST /api/pipeline 或 run_agent_pipeline 一键到 finalize
□ output/runs/<id>/ 有 perception / plan / risk / views / agent_trace
□ steps 里可见 volume/booking/bin3d/risk 等 tool 名
□ planning_reasons 可陈述「为何 N0、绑重量还是体积、是否加柜」
□ finalize / goal_status 写明 建议订舱 或 不可出运及原因
□ 不声称「单一全能 Agent」或「LLM 算出柜数」
```

---

## 双路径

| 路径 | Agent 浓度 | 用途 |
|------|------------|------|
| booking/site 脚本 | 低（tools 直调） | 答辩**数字**准 |
| 9 Agent + `/api/pipeline` | 高 | **Agent 叙事**主路径 |
| 当量直通 9 Agent | 高且数字准 | 两者兼顾 |
