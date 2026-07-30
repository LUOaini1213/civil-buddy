---
category: multi_agent
subcategory: protocol
priority: high
type: protocol
tags: [sequence, HITL, happy_path]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 主路径序列（Happy Path）

```text
NL / 文件
  → [大 Team] intent.interpret
  → [Team A] material.parse → structure.calc → box.scheme → cargo.feasibility
  → [大 Team] hitl.confirm  (可 auto)
  → [Team B] N0/plan → bin3d loader → evaluator → risk → visualize
  → (optional) replan.critic 有界环
  → [大 Team] finalize + export + (optional) tms.booking
```

## HITL 分支

```text
Team A done → phase=await_user_confirm → session.save
  → (进程可死)
  → session.load → hitl.confirm → Team B → finalize
```

## 失败环（有界）

```text
can_fit=false 或 structure_fail 或 over_payload
  → replan.critic (route / options)
  → 回到 A 或 B 局部
  → 达 max_replan → stop + 人工
```

## 与代码

- `teams/big_team.py` · `team_a.py` · `team_b.py`
- `graph_resume.py` · `session_store.py`
