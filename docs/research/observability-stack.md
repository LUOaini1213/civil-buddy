# 可观测 / Checkpoint / WebSocket 栈

## 1. LangGraph Sqlite Checkpoint

```bash
# 默认开启
set PACKING_LG_CHECKPOINT=1
# 可选路径
set PACKING_LG_CHECKPOINT_PATH=output/langgraph_checkpoints.db
```

- Team A / B 调用 `create_*_app_durable()` + `thread_id=session_id`
- 与文件 `session_state.json` **双写**（API resume 不丢）
- 查询：`GET /api/lg/threads/{thread_id}`

## 2. OTEL 导出

```bash
set PACKING_OTEL=1
# 可选 collector
set OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
# 默认同时写文件，无 Jaeger 也能验收
set PACKING_OTEL_FILE=1
```

依赖：`pip install -r requirements-observability.txt`

产物：`output/otel/spans.jsonl`

## 3. WebSocket 多 tab

```
ws://127.0.0.1:8000/ws/session/<session_id>
ws://127.0.0.1:8000/ws/runs/<run_id>
```

- Tab A 点「一键演示」走 SSE  
- Tab B 连同一 `session_id` 的 WS → 同步看 roster  

## 测试

```bash
pip install -r requirements-observability.txt
python scripts/test_observability_stack.py
```
