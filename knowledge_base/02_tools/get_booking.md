---
category: tools
subcategory: booking
priority: high
type: tool_doc
tags: [booking, N0, volume]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：get_booking / compute_booking

## 功能

根据 materials 或 boxes 计算订舱当量：N0、重量柜、体积柜、binding。

## 代码入口

`packing_assistant.tools.booking.compute_booking`

## 参数

| 参数 | 说明 |
|------|------|
| materials | 物料行列表（可选） |
| boxes | 成箱列表（优先） |
| container_type | 20GP/40GP/40HQ… |
| fill_ratio | 默认约 0.82 |

## 输出要点

- `n0` / `containers_needed`
- `containers_by_weight` / `containers_by_volume`
- `binding_constraint`: weight | volume | both
- `volume_m3`：订舱有效体积（非盲目 outer）

## 何时调用

- 规划 Agent（planner）定 N0  
- what-if / 锁柜前估算  

## 常见错误

| 现象 | 处理 |
|------|------|
| 体积柜异常大 | 检查是否误用 crate outer 当分子 |
| 超重单件 | 先 `cargo_feasibility`，再拆箱 |
