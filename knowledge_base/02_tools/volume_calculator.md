---
category: tools
subcategory: volume
priority: high
type: tool_doc
tags: [volume, pack_effective, dual_caliber]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：volume_calculator

## 功能

件体积、包装膨胀、订舱体积、与柜可用容积比较。

## 代码入口

`tools.volume_estimate` · `booking_volume_from_boxes`

## 何时调用

- 估柜、双口径展示、审计订舱分子  

## 注意

- 见 `01_rules/volume_weight/dual_caliber.md`  
- 单测：`test_booking_volume_metrics.py`  
