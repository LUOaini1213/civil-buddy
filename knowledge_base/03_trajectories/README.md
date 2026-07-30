---
category: trajectories
subcategory: index
priority: medium
type: trajectory
tags: [index, T1, T2, T3, T4, T5, T6, T7, T8]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 轨迹索引（可 few-shot）

格式：Goal → Step(thought/tool/args/observation) → Final。  
**obs 禁止全量 layout 坐标。**

| ID | 文件 | 场景 |
|----|------|------|
| T1 | success/T1_short_standard_box.md | 短票标准箱 |
| T2 | success/T2_t80_long_mix_anchor.md | t80 锚点 |
| T3 | failure_recovery/T3_over_payload_box_scheme.md | 超货载拆箱 |
| T4 | success/T4_hitl_resume_ab.md | HITL 续跑 |
| T5 | success/T5_container_budget_lock.md | 锁柜 |
| T6 | success/T6_dual_caliber_booking.md | 双口径 |
| T7 | failure_recovery/T7_structure_fail_replan.md | 结构失败 |
| T8 | failure_recovery/T8_feasibility_block.md | 可行性拦截 |

旧大纲文件（long_horizon_booking_01 等）保留作补充，优先用 T1–T8。
