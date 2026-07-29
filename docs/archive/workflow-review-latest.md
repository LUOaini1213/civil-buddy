# Workflow 评审报告（最新）

**日期**：P1 缺口已修后复评  
**结构**：架构用 **总分总分总**；本报告收口用 **总分总**  
**详评**：见 [`code-review-总分总分总.md`](code-review-总分总分总.md)

---

## 一、总

| 维度 | 判定 | 一句话 |
|------|------|--------|
| **架构骨架** | 正确 | 主控总 → 成箱分 → 闸门总 → 拼柜分 → 裁决总 |
| **体积/订柜** | **PASS** | 主链 V_eff；k 统一；门禁绿 |
| **Agent/API/页** | **PASS**（演示主路径） | visualizer tools + user_confirm/hitl_wait 已齐 |
| **改进 workflow 文件** | 可用 | 3 个 rhai；真跑需项目 folder trust |

**综合**：**五段架构均可指着代码演示**；无 P0；仅余 P2 体验对齐。

---

## 二、分

### 2.1 架构评审（总分总分总）

| 段 | 节点 | 评审 |
|----|------|------|
| ① 总 | orchestrator | 有 goal / 选柜 / tools |
| ② 分 | material→structure→box | 成箱分工清晰 |
| ③ 总 | present_team_a HITL | 闸门存在；**缺显式 user_confirm step**（P2） |
| ④ 分 | plan→load→eval→risk→viz | replan 合理；**visualizer 无 tools_used**（P1） |
| ⑤ 总 | finalize | goal_status / 双口径文案齐 |

### 2.2 体积线（explore 审计）→ PASS

**已过关：**

- `min(outer, content×k)` / 无 content → `outer×0.45`
- `crate_outer` 默认禁用并重定向
- 双指标：booking vs outer 在 loader/evaluator 拆开
- `check_volume_gates` 本地绿

**残留 P1/P2：**

| P | 问题 | 建议 |
|---|------|------|
| P1 | packing 与 `box_pack_effective_m3` 的 **k 选档**（outer 填充 vs inner 填充）可能分叉 | 统一 content/outer 选 k |
| P1 | loader fallback `pack_boxes_api` **只试 N0** 不加柜 | fallback 也 N0..n_max |
| P2 | 直通箱固定 k=1.50 | 共用 `box_pack_effective_m3` |
| P2 | evaluator `booking_known = util>0` 把真 0 当未知 | 用 is not None |

### 2.3 Agent / API / 前端 → PARTIAL

**已过关：**

- 页底 agent-console + 筛选
- 双体积 UI + `volume_summary`
- `/api/demo`、`/api/pipeline`
- 多数节点有 `tools_used`

**残留：**

| P | 问题 | 建议 |
|---|------|------|
| P1 | **visualizer** 无 `agent_meta.tools_used` | 补 visualize 工具名 |
| P1 | `enable_auto_confirm=False` 时 **hitl_wait 死代码** | present 后写 wait step |
| P2 | confirm 路径缺 **user_confirm** 显式 step | confirm API 注入一步 |
| P2 | graph vs steps 模式 step 字段不齐 | 统一 schema |
| P3 | pipeline 顶层可再挂 `volume_summary` | 与 public 同构 |

### 2.4 Workflow 脚本资产

| 文件 | 用途 | 评审 |
|------|------|------|
| `audit-booking-volume.rhai` | Q1/Q2/Q3 体积审计 | 设计正确；历史有 SYNTH 失败需重跑 |
| `full-stack-improve.rhai` | 审计→实现→验证 | 形状对；trust 后可真跑 |
| `plan-improve-总分总.rhai` | 改进节奏 | 名是总分总；**架构叙事应改称总分总分总** |

---

## 三、总（结论与下一轮）

### 结论（答辩可用）

1. **架构**：总分总分总正确，不要压成三段抹掉 HITL。  
2. **数字**：订柜体积主链 **PASS**，门禁可指。  
3. **Agent 演示**：**PARTIAL 可用**——auto/pipeline 强；人工确认轨迹弱一点。  
4. **无 P0 阻塞**；P1 两周内收口更稳。

### 下一轮只做 3 件（P1）

1. visualizer 补 `tools_used`  
2. HITL：`user_confirm` / `hitl_wait` 写入 `agent_steps`  
3. 统一 k 选档 + loader fallback 递增  

### 30 秒口述

> **总**：骨架是主控—成箱—确认—拼柜—裁决；数字 tools 算。  
> **分**：体积审计 PASS；页与 API 可看 Agent，确认步与出图 tools 还差半步。  
> **总**：版本 f780469 可交；下一轮只补轨迹与 k 口径，不扩模型。

---

*审计来源：并行 explore 子代理 volume + agent/api/frontend；门禁 `check_volume_gates` 绿。*
