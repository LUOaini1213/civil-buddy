---
category: multi_agent
subcategory: protocol
priority: high
type: protocol
tags: [summary, supervisor, failure_class]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 子 Team 回传摘要协议

子 Team **禁止**把完整 3D layout 全量灌回 supervisor 上下文；回传：

```json
{
  "team": "A|B",
  "n_boxes": 0,
  "can_fit": null,
  "containers_used": null,
  "n0": null,
  "standard_box_hit_rate": null,
  "feas_ok": null,
  "risk_decision": null,
  "need_replan": false,
  "failure_class": null,
  "message": "≤200字"
}
```

## failure_class 枚举

| 值 | 含义 |
|----|------|
| null | 无失败 |
| over_payload | 超货载 |
| structure_fail | 结构不通过 |
| cannot_fit | 装不下（非仅货载） |
| budget_lock | 锁柜装不下 |
| tool_error | 工具异常 |
| need_more_info | 缺尺寸重量 |
| replan_exhausted | 重排达上限 |

完整 state 仍在 session/磁盘；LLM 调度只看摘要。  
坐标与 placements **只存在于** loader 输出工件，不进 supervisor prompt。
