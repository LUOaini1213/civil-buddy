# 代码评审 · 总分总分总架构

**基线修复后**：visualizer tools / HITL steps / k 统一 / loader fallback 递增  
**门禁**：`check_volume_gates` 绿  
**轨迹冒烟**：auto 含 `user_confirm`；非 auto 含 `hitl_wait`；visualizer 有 `tools_used`

---

## ① 总 · orchestrator（主控开头）

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 声明 goal | OK | `goal` / `goal_desc` / 多目标字典 |
| 选柜工具 | OK | `container_select.recommend_container` |
| 调度名册 | OK | 9 智能体 roster |
| tools_used | OK | agent_meta |

**段评**：PASS — 第一段「总」职责清楚，不直接算 N0。

---

## ② 分 · 团队 A（成箱）

| 节点 | 结果 | 备注 |
|------|------|------|
| material_parser | OK | 感知摘要 + tools |
| structure | OK | tools_used 已补 |
| box_scheme | OK | packing / passthrough；**k 与 volume_estimate 统一** |

**段评**：PASS — 成箱分工完整；订柜字段 content/outer/booking_volume 主路径齐。

---

## ③ 总 · HITL 闸门

| 检查项 | 结果 | 证据 |
|--------|------|------|
| present_team_a | OK | `hitl.confirm_gate` |
| auto 确认步 | OK | `agent_steps` 含 **`user_confirm`** |
| 非 auto 等待 | OK | present 后写 **`hitl_wait` 再 break**（死代码已修） |
| apply_user_confirmation | OK | 注入 user_confirm step + message |

**段评**：PASS — 第三段「总」可观察，A/B 分界清晰。

---

## ④ 分 · 团队 B（拼柜）

| 节点 | 结果 | 备注 |
|------|------|------|
| planner | OK | N0 + planning_reasons；pack_effective |
| loader | OK | skjolber 优先；**fallback 自 N0..n_max 递增** |
| evaluator | OK | 双指标；**booking_known 认 is not None** |
| risk_compliance | OK | suggested_actions |
| visualizer | OK | **tools_used 已补**；图注双口径 |

**段评**：PASS — 拼柜分工 + replan；无「只试一柜」兜底坑。

---

## ⑤ 总 · finalize（裁决）

| 检查项 | 结果 | 备注 |
|--------|------|------|
| goal_status | OK | achieved / verdict |
| N0 vs 3D | OK | 双口径文案 |
| ship_ok / REJECT | OK | 装得下≠可出运 |
| tools | OK | container_select.compare_after_load |

**段评**：PASS — 收口总闸对齐业务裁决。

---

## 横切（体积 / API / 前端）

| 项 | 结果 |
|----|------|
| 订柜分子 ≠ 满 outer | PASS（门禁 + 代码） |
| k 选档 | PASS（`pack_k_for_fill` 统一） |
| volume_summary API | PASS（public + pipeline 顶层） |
| 页底 Agent 筛选 | PASS（前端既有） |
| architecture 字段 | PASS（pipeline `总分总分总`） |

---

## 总分总收口（本轮评审）

**总**：架构五段齐全，主链体积与轨迹缺口已按上次评审修掉。  

**分**：①主控 ②成箱 ③HITL ④拼柜 ⑤裁决 分段均为 PASS；门禁与 auto/HITL 冒烟通过。  

**总**：**可按总分总分总答辩与演示**。遗留仅为体验向 P2（graph vs steps 字段完全同构、消息兜底 tools 为空），不阻塞提交。

### 演示指认

```text
① 总  orchestrator message / goal
② 分  boxes[] + packing tools
③ 总  user_confirm 或 hitl_wait in agent_steps
④ 分  N0 / loader / risk / visualizer tools
⑤ 总  finalize goal_status 建议订舱或不可出运
```

### 自检命令

```bash
python scripts/check_volume_gates.py
python -c "from packing_assistant.harness import run_agent_pipeline; s=run_agent_pipeline('d',enable_auto_confirm=True,save_artifacts=False); print([x['node'] for x in s['agent_steps']])"
```
