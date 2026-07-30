# 比赛演示脚本（3 分钟 · 评委向）

**Harness v0.6.2** · 主路径 **`agent_mode=steps`**

## 一句话

> 这是 **NL 驱动的装柜多智能体**：大 Team 编排/闸门/有界 replan；小 Team A 用 **标准铁架箱库** 成箱；小 Team B 做 3D/CoG/风险；**tools 算数，LLM 不写坐标**。

## 组织（指前端三层图）

```text
大 Team：intent → 编排 → HITL → critic → 收口
  ├─ 小 Team A 成箱：材料 → 结构 → 标准箱合箱
  └─ 小 Team B 拼柜：N0 → 3D → 评估 → 风险 → 出图
```

## 演示步骤

1. **打开前端** · 指左侧「大 Team ⊃ A/B」组织图  
2. **跑小票**（或 demo）：`python scripts/competition_smoke.ps1` 或网关 pipeline  
3. **HITL 卡片**：看「标准箱架」命中率与箱型分布（1.1m/2m/4m…）  
4. **确认拼柜**：看 can_fit、N0 vs 3D 柜数、重心  
5. **打开 agent_steps**：每步有 **plan / act / observe / reflect**  
6. **（可选）超货载故事**：单件 80t → 可行性 Tool 检出 → critic **拆箱** 而非傻加柜  

## 不说的话

- 不说「模型自己摆箱子」  
- 不说龙申/工厂是唯一业务  
- 不默认吹 LLM tool-call 为主路径  

## 关键命令

```bash
python scripts/test_anchor_t80_long_mix.py
python scripts/run_phase0_baseline.py --quick
powershell -File scripts/competition_smoke.ps1
```

## 关键文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)  
- [competition-phase-plan.md](./competition-phase-plan.md)  
- 基线报告：`output/phase0/BASELINE_REPORT.md`  
