---
category: rules
subcategory: volume_weight
priority: high
type: rule
tags: [dual_caliber, booking_volume, outer_util, N0]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 双口径说明

## 订舱口径（booking）

- **指标**：`booking_volume_utilization`、N0、binding=weight|volume|both
- **体积来源**：pack_effective / min(outer, content×k)，**不是**盲目空心架外廓累加
- **用途**：订舱、对客话术、评测 task_success 的柜数软约束

## 3D/展示口径（outer）

- **指标**：`outer_space_utilization` / `space_utilization`、底面积、摆柜外廓
- **用途**：现场装载、空隙、叠装、可视化

## 禁止混淆

| 错误 | 正确 |
|------|------|
| 用空心 4m/6m 架外廓当订舱体积 | 订舱用 pack_effective / min(outer, content×k) |
| 把 outer% 当「订满了」 | 同时报 booking% 与 outer% |
| 3D 用柜 > N0 就说体积算错 | 说明成箱上界 vs 订舱 N0 |

## 条件 / 动作 / 后果

- **条件**：方案同时服务订舱与现场
- **动作**：finalize / 报告双字段
- **后果**：混用导致评测与客户预期双杀

## 代码与测试

- `tools/booking.py` · `volume_estimate.py`
- 单测：`scripts/test_booking_volume_metrics.py`
- 轨迹：T6
