---
category: tools
subcategory: B
priority: high
type: tool_doc
tags: [secure.work_order, B, catalog]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：绑扎工单 (`secure.work_order`)

## 功能

绑扎要点

## 代码入口

- module: `packing_assistant.tools.secure_work_order`
- team: **B**
- tool id: `secure.work_order`

## 参数（示意）

```json
{"state_ref": true}
```

实际参数以模块实现为准；Agent 只选工具，数值由 tools 计算。

## 何时调用

- Team 簇 **B** 流水线中需要「绑扎工单」时
- 规则提示：遵循 team 边界与红线

## errors

| 情况 | 处理 |
|------|------|
| 输入 state 不完整 | 返回 ok=false / need_more_info |
| 计算失败 | 记 failure_class=tool_error，有界重试 |

## never

- never 由 LLM 代替本工具编造数值结果
- never 输出伪造 xyz（装载类工具仅返回引擎结果）
- 遵循 team 边界与红线

## 相关

- 注册表：`packing_assistant.tool_registry.TOOL_CATALOG`
- 非法行为：`05_multi_agent/illegal_tools.md`
