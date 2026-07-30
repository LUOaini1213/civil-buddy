---
category: tools
subcategory: retrieval
priority: high
type: tool_doc
tags: [RAG, knowledge_base, search, knowledge.search]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：search_knowledge（已实现）

## 功能

在 `knowledge_base/` 中按关键词 + frontmatter（category / priority / tags）检索规则、工具说明与范例轨迹。  
**不返回 3D 坐标 / layout**；数值箱型仍优先 `knowledge/packing_knowledge_base.json`。

## 代码入口

- 模块：`packing_assistant.tools.search_knowledge`
- 函数：`search_knowledge(q, category=..., priority=..., tags=..., limit=...)`
- 工具 ID：`knowledge.search`（见 `tool_registry.TOOL_CATALOG`）

## 参数（示意）

```json
{
  "q": "重心 mid50 红线",
  "agent_id": "risk_compliance",
  "category": "rules",
  "priority": "high",
  "tags": "CTU,CoG",
  "limit": 5
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| q | string | 查询文本（中英关键词） |
| **agent_id** | string | **推荐**：按 `agent_kb_bindings.yaml` 窄接（orchestrator / box_scheme / …） |
| category | string | 可选：rules / tools / trajectories / …（无 agent_id 时） |
| priority | string | 可选：high / medium / low |
| tags | string | 逗号分隔 |
| limit | int | 默认 5，最大 20 |

## Agent 窄接

- 配置：`knowledge_base/05_multi_agent/agent_kb_bindings.yaml`
- 代码：`packing_assistant.kb_bindings.search_for_agent`
- API：`GET /api/kb/bindings` · `POST /api/kb/search` `{"agent_id","q"}`
- **loader** 默认 `allow_search=false`（坐标只来自 tools）
- **replan_critic / finalize** 自动注入 `kb_evidence` 短引用

## 返回

```json
{
  "ok": true,
  "n_hits": 1,
  "hits": [
    {
      "path": "01_rules/ctu_loading/safety_redlines.md",
      "title": "安全红线",
      "score": 12.3,
      "snippet": "…",
      "frontmatter": {"category": "rules", "priority": "high"}
    }
  ],
  "note": "rules/tools/trajectories only; coordinates must come from packing tools"
}
```

## 何时调用

- NL 含「规范 / 重心 / 空隙 / VGM / 双口径」
- replan critic 需要**规则依据文案**
- 评委解释性：引用 path 作为 evidence
- **不必**在纯 steps 模式每步调用（规则已在代码路径）

## 错误 / 边界

| 情况 | 行为 |
|------|------|
| 知识库目录缺失 | `n_docs_indexed=0`，hits=[]，ok 仍 true |
| 无匹配 | hits=[] |
| deprecated 文档 | 不入索引 |

## never

- never 用本工具返回 xyz / 柜位坐标
- never 用检索结果替代 `run_packing` / loader 计算
- never 把 session checkpoint 全文塞进知识库

## 回归

- 金标：`test/kb/rag_golden.json`
- 脚本：`python scripts/test_search_knowledge.py`（Recall@3 ≥ 0.90）
