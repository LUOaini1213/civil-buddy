# HITL Durable Checkpoint

## 语义（对照 LangGraph）

| LangGraph | packing-agent |
|-----------|----------------|
| `thread_id` | `session_id` / `thread_id` |
| `interrupt` before tool/node | `phase=await_user_confirm` 后图结束 / stream `type=hitl` |
| checkpointer blob | `session_state.json` + `checkpoint.json` |
| resume with Command | `POST /api/confirm` 或 `/api/checkpoints/{id}/resume` |

## 何时写入

1. `run_team_a` 结束且 phase=await_user_confirm（gateway `_store_session`）
2. `iter_agent_pipeline` 在 `enable_auto_confirm=False` 命中 HITL 时 `save_session`
3. stream `done` / 任意 confirm 后更新状态

## 重启后如何 resume

```bash
# 1) 列出未确认
curl "http://127.0.0.1:8000/api/checkpoints?pending_hitl=true"

# 2) 预览
curl "http://127.0.0.1:8000/api/checkpoints/<thread_id>?include_state=true"

# 3) 确认并拼柜
curl -X POST "http://127.0.0.1:8000/api/checkpoints/<thread_id>/resume" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<thread_id>","action":"confirm","container_type":"40HQ","max_containers":0}'
```

## 测试

```bash
python scripts/test_hitl_checkpoint.py
python scripts/test_hitl_checkpoint.py --http
```
