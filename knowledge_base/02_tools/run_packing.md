---
category: tools
subcategory: packing
priority: high
type: tool_doc
tags: [standard_box, box_scheme, mass_split, run_packing]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：run_packing / box.scheme（成箱）

## 功能

材料 → 标准箱库合箱 / dense / 当量直通；按 `max_box_net_kg` 拆行与质量拆分。

## 代码入口

- `packing_assistant.tools.packing` · `agents.box_scheme`
- 工具 ID：`box.scheme`

## 参数（示意）

```json
{
  "standard_boxes": true,
  "max_box_net_kg": 3200,
  "mass_split": true,
  "dense": false
}
```

## 何时调用

- Team A 成箱；replan 打回 box_scheme

## 默认

- 正常混料：`standard_boxes=True`（标准铁架系列）
- 仅 note 标明 crate 当量时直通

## 校验

- `knowledge.validate_boxes_against_kb`：标准箱命中率

## errors

| 错误 | 处理 |
|------|------|
| 缺尺寸重量 | need_more_info，不编造 |
| 超 cap | mass_split |

## never

- never LLM 手写箱 xyz
- never 二次撑大已 crate 当量外廓
