---
category: competition
subcategory: scoring
priority: high
type: scoring
tags: [phase0, weights, success_criteria]
source: internal
updated: "2026-08-28"
harness: ">=0.6.3"
status: active
---
# 评分标准（内部代理 · 无官方表时）

> **口径声明（2026-08-28）**：本文件 = **内部引擎评测口径**（packing phase0 / 代理评分卡，服务 `scripts/eval_competition_scorecard.py`）。
> **海之子杯官方三维度**（场景创意价值 / AI 协同能力 / 技术创新能力）见 [constraints-hzzb.md](./constraints-hzzb.md)；NUS-ISS 新加坡资格条款见 [constraints-nus-iss.md](./constraints-nus-iss.md)。两套口径不互替，申报材料以官方三维度对齐。

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

## 本地快照（2026-08-06 迭代）

| 检查 | 结果 |
|------|------|
| phase0 `--quick` | pass_rate 1.0 · avg ≈ **0.973**（见下「评分口径」） |
| competition_smoke | overall **9.75** · hard gates all PASS |
| workteams tiny | agree=1.0 · illegal=0 |
| KB scorecard | 综合 ≈ **9.86** · tool catalog 34/34 |

### 评分口径（诚实说明 · 非装载质量跃迁）

- **0.948 → 0.973** 主要来自 `_score_task_success` 口径调整，**不是** packing/3D 突然变好：
  - 旧：`can_fit=True` 任务维常停在 **0.85**
  - 新：`can_fit=True` 基线 **0.90**；`ship_ok` / mid50≥0.60 可抬到 **0.93–0.96**
- 同票 pass_rate 在改前后均为 **1.0**；装载成败以 can_fit/ship_ok/mid50/adversarial 为准，勿把加权分上涨当成算法胜出。
- 单元对照：`scripts/test_phase0_task_success.py`（直接调用 shipped `_score_task_success`）。

## 基线命令

```bash
python scripts/run_phase0_baseline.py --quick
powershell -File scripts/competition_smoke.ps1
python scripts/eval_workteams_cli.py --tiny-only
```

## 与知识库

- 解释性可调用 `knowledge.search` 引用 rules path
- 非法行为见 `05_multi_agent/illegal_tools.md`
