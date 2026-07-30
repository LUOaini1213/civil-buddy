#!/usr/bin/env python3
"""为 TOOL_CATALOG 每个 id 生成/补齐 knowledge_base/02_tools 文档。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tool_registry import TOOL_CATALOG  # noqa: E402

KB = ROOT / "knowledge_base" / "02_tools"


def main() -> int:
    KB.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    created = 0
    for t in TOOL_CATALOG:
        p = KB / f"{t.id.replace('.', '_')}.md"
        if p.exists() and t.id in p.read_text(encoding="utf-8"):
            continue
        rule = t.rule or "遵循 team 边界与红线"
        body = f"""---
category: tools
subcategory: {t.team}
priority: high
type: tool_doc
tags: [{t.id}, {t.team}, catalog]
source: internal
updated: "{today}"
harness: ">=0.6.3"
status: active
---

# 工具：{t.name} (`{t.id}`)

## 功能

{t.description}

## 代码入口

- module: `{t.module}`
- team: **{t.team}**
- tool id: `{t.id}`

## 参数（示意）

```json
{{"state_ref": true}}
```

实际参数以模块实现为准；Agent 只选工具，数值由 tools 计算。

## 何时调用

- Team 簇 **{t.team}** 流水线中需要「{t.name}」时
- 规则提示：{rule}

## errors

| 情况 | 处理 |
|------|------|
| 输入 state 不完整 | 返回 ok=false / need_more_info |
| 计算失败 | 记 failure_class=tool_error，有界重试 |

## never

- never 由 LLM 代替本工具编造数值结果
- never 输出伪造 xyz（装载类工具仅返回引擎结果）
- {rule}

## 相关

- 注册表：`packing_assistant.tool_registry.TOOL_CATALOG`
- 非法行为：`05_multi_agent/illegal_tools.md`
"""
        p.write_text(body, encoding="utf-8")
        created += 1
        print("wrote", p.name)
    print("created", created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
