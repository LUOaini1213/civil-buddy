---
category: competition
subcategory: tasks
priority: high
type: scoring
tags: [tasks, phase0, demo, t80]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 示例任务（镜像 phase0 任务族）

夹具与脚本：`test/phase0/*` · `scripts/run_phase0_baseline.py`  
演示话术：`docs/competition-demo-script.md`

| ID | 意图 | 期望 | 轨迹 | 规则 |
|----|------|------|------|------|
| short_standard | 短票标准箱 | can_fit≈true | T1 | packing_heuristics |
| t80_long_mix_s297883 | 长票锚点 | pass 锚点 | T2 | dual_caliber, safety |
| over_payload_monster | 超货载恢复 | 拆箱恢复非只加柜 | T3 | safety_redlines |
| hitl_resume | A→重启→B | can_fit 有值 | T4 | escalation, summary |
| budget_1c | NL 锁 1 柜 | 不破预算 | T5 | container_budget |
| dual_caliber_talk | 订舱话术 | 双利用率字段 | T6 | dual_caliber |
| structure_fail | 结构失败 | 打回成箱 | T7 | safety structure |
| feas_block | 可行性拦截 | stop/人工 | T8 | feasibility |

## phase0 目录

- `test/phase0/success_criteria.json` — 权重
- `test/phase0/over_payload_monster.json` — 超货载
- 其余物料夹具由 baseline 脚本聚合（含 t80 锚点）

## 评委双证据

1. 本表 + 轨迹 md  
2. 可跑脚本与 `output/phase0` 报告  
