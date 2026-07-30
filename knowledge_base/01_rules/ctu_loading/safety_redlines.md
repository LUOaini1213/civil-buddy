---
category: rules
subcategory: ctu_loading
priority: high
type: rule
tags: [redline, CoG, CTU, mid50, xyz, payload]
source: CTU_code_practice_summary
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 安全红线

> **声明**：以下为内部 Agent **实务摘要**，便于检索与评测，**非** CTU Code / 法律全文替代。正式出运以船东/船级与当地法规为准。

## 红线：超货载

- **条件**：单柜或单箱超过 payload 安全裕度（或 `cargo.feasibility` ok=False）。
- **动作**：拆箱 / 减载 / mass_split；**禁止**只把 `max_containers` 拉高空转。
- **后果**：不可出运；`ship_ok=False`。
- **代码**：`tools/cargo_feasibility.py` · replan route=`box_scheme`
- **轨迹**：T3、T8

## 红线：重心

- **纵向**：尽量靠近柜长中部；实务目标 **≥60% 货重落在柜长中段 50%（mid50）**。
- **横向**：偏心过大（如 ≥5%–10% 量级）→ 再平衡或配重（cog 工具族）。
- **垂向**：重心偏低优先。
- **代码**：`tools/cog*.py` · risk 规则

## 红线：结构不通过

- **条件**：箱结构结论「不通过」。
- **动作**：不得当作可装单元进柜；打回成箱。
- **代码**：`structure.calc` · critic → box_scheme
- **轨迹**：T7

## 红线：未 can_fit 当出运

- `can_fit=False` 或 `ship_ok=False` → 禁止当作正式订舱/出运方案。

## 红线：LLM 写坐标

- 3D 坐标、柜数结论必须由 **tools** 计算，禁止语言模型编造。
- 检索 `knowledge.search` 也不得返回 xyz 字段。
- 见：`05_multi_agent/illegal_tools.md`

## 例外

- 演示/what-if 可展示失败方案，但必须标记 `not_for_ship=true`。
