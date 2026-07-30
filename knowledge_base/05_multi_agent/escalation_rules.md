---
category: multi_agent
subcategory: protocol
priority: high
type: protocol
tags: [escalation, HITL, stop, replan]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 升级规则

| 情况 | 动作 | failure_class |
|------|------|----------------|
| 成箱完成 | HITL 闸（可 auto） | — |
| 结构不通过 | critic → box_scheme | structure_fail |
| 超货载 | critic → box_scheme；禁止只加柜 | over_payload |
| 锁柜装不下 | 密装/叠高/打回成箱；不破预算 | budget_lock |
| can_fit=false 且 feas_ok | multi_start / dense / 有界加柜 | cannot_fit |
| replan 达上限 | stop + 人工 | replan_exhausted |
| 缺尺寸重量 | need_more_info，不编造 | need_more_info |
| 工具异常 | 记日志；可重试 1 次后升级 | tool_error |

## 与轨迹

- T3 over_payload · T7 structure · T8 feasibility · T4 HITL
