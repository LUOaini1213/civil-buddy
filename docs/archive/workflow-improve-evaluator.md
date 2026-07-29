# Workflow：improve-evaluator

## 脚本

- 项目：`.grok/workflows/improve-evaluator.rhai`
- 会话 run 显示名：`improve-evaluator`

## 阶段

1. **Audit** — 对照 `evaluator-web-review.md` 查是否已实现  
2. **Implement** — 补缺口（已齐则只确认）  
3. **Verify** — Python 冒烟权重 / metrics_table  

## 验收项（plan）

| 项 | 代码落点 |
|----|----------|
| metrics_table | `evaluation.metrics_table` |
| space_subscore 废弃别名 | `space_subscore_deprecated` |
| 自适应权重 | `_resolve_weights` + binding |
| 可配置权重 | `evaluation_weights` |
| used>N0 惩罚 | `penalize_extra_containers` |
| outer 不进主分 | `in_score: false` |

## 本地一键验收

```bash
python -c "from packing_assistant.agents.evaluator import agent_evaluator,_resolve_weights; assert _resolve_weights({},'weight')[2]>0.5; print('OK')"
```

在 `/workflows` 查看 run 进度。
