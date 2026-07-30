---
category: rules
subcategory: volume_weight
priority: high
type: rule
tags: [volume, weight, calculation, N0, payload]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 体积重量计算规则

## 重量

- 箱净重 / 毛重由物料与包材汇总；**禁止 LLM 估重**。
- 单箱净重 cap 默认参考 `max_box_net_kg`（代码默认量级 3200kg，以 options 为准）。
- 超 cap → mass_split / 拆行。

## 体积（订舱）

- 优先 pack_effective 体积；标准空心架不可用外廓冒充内容积。
- 体积柜数与重量柜数取 max 得 **N0**。

## 体积（3D）

- 装载引擎使用箱外廓与柜内尺寸；结果产出 outer 利用率与 can_fit。

## 与双口径

- 详见 `dual_caliber.md`。体积重量计算规则服务于 N0 与 feasibility，不替代 3D。

## 代码

- `volume_estimate.py` · `booking.py` · `cargo_feasibility.py`
