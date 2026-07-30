---
category: competition
subcategory: scoring
priority: high
type: scoring
tags: [phase0, weights, success_criteria]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 评分标准（内部代理 · 无官方表时）

**同源配置**：`test/phase0/success_criteria.json`（有赛方官方权重时 **只改 JSON**）。

| 维度 | 权重 | 要点 |
|------|------|------|
| 任务成功 | 0.30 | can_fit + 锁柜/柜数 + 无硬崩溃 |
| 长程完成 | 0.15 | bootstrap→装载→收口 |
| 工具质量 | 0.20 | 工具轨迹 + illegal=0 + 体积自洽 |
| 多 Agent 协作 | 0.15 | A 与 B 节点均出现（大Team⊃A/B） |
| 效率 | 0.10 | 步数与耗时相对上限 |
| 解释性 | 0.10 | agent_steps / intent_spec / messages / **可引用 KB path** |

## 赢线

- 总分 ≥ **0.75** 且 task_success ≥ **0.80**

## 基线命令

```bash
python scripts/run_phase0_baseline.py
```

## 与知识库

- 解释性可调用 `knowledge.search` 引用 rules path
- 非法行为见 `05_multi_agent/illegal_tools.md`
