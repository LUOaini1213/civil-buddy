---
category: tools
subcategory: feasibility
priority: high
type: tool_doc
tags: [feasibility, payload, over_payload, split]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：cargo_feasibility

## 功能

检查单件/单箱是否超柜 payload；建议拆箱；**超限禁止只加柜空转**。

## 代码

- `packing_assistant.tools.cargo_feasibility`
- 工具 ID：`cargo.feasibility`

## 参数

```json
{ "boxes": "$state.boxes", "container_payload_kg": null }
```

## 返回要点

- `ok: bool`
- `reason` / 建议 `mass_split` / `max_box_net_kg`

## errors

| 情况 | 行为 |
|------|------|
| over_payload | ok=false，触发 critic→box_scheme |
| 工具异常 | failure_class=tool_error |

## never

- never 在 ok=false 时 silent 出运
- never 用加柜代替拆箱作为唯一手段

## 轨迹

- T3 · T8
