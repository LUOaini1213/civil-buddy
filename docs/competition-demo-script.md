# 比赛演示脚本（5 分钟 · 评委向）

**Harness v0.6.4** · **13 agents** · 主路径 **`agent_mode=steps`**  
演示：**关闭「演示自动确认」**，露出 `phase=await_user_confirm`

## 一句话

> 这是 **NL 驱动的装柜多智能体**：大 Team 编排 / HITL / critic；小 Team A **成箱**；小 Team B **N0\* 定柜 + 3D 装载 + CoG**。  
> **柜数与坐标由 tools 算**，模型不拍 N 柜、不写 xyz；人确认成箱 + 建议柜数后再拼柜。

## 组织

```text
大 Team：intent → 编排 → HITL → critic → 收口
  ├─ 小 Team A 成箱：材料 → 结构 → 箱方案（+ 建议柜数 N0* 同屏）
  └─ 小 Team B 拼柜：N0* → 3D（柜内 multi_start）→ CoG → 评估 → 风险 → 出图
```

## 柜数怎么来的（口播 20 秒）

| 概念 | 含义 |
|------|------|
| **成箱** | 物料 → 多少只箱 |
| **N0\*** | 建议订几柜 = max(重量, 有效体积, 底面几何, 槽位) |
| **used** | 3D 实装几柜（可能 = N0\* 或 +1；末柜可并回） |

- **不是** LLM 说「就 3 柜」  
- **不是** 纯 FFD 跨柜最优  
- **是** 工具下界 + 试装 + 人确认；柜内 multi_start 管摆法  

## 冻结 5 分钟路径（唯一主戏）

1. **预检** · 网关 UP · harness **0.6.4 / 13**  
2. **满载或钢件** · **关自动确认**  
3. **装箱方案页 / HITL**：箱表 + **建议柜数 N0\*** + 分量（重/体/底/槽）  
4. **确认并拼柜** · 看 **N0\* → 实装 used**、双口径、**mid50 / verdict**  
5. **策略卡** · 少柜 light=参考；Agent 选 `balance_cog`/`tight_budget_cog`（mid50≥55%）  
6. **agent_steps**：A + B；tools 轨迹  
7. **备份**：缺尺寸大红条 或 80t 拒装；多柜票看「末柜偏空/并回」  

### 30s 多柜话术

> Tool 出候选：少柜下界 vs CoG 可出运；**Agent 按 CTU mid50 选**；21 柜是参考不是出运；人确认大票。

## 不说的话

- 不说「模型自己摆箱子 / 模型决定几柜」  
- 不默认吹 LLM tool-call 为主路径  
- 不报本地虚高 10.0；对外可用联网校准 **~8.85**  
- 诚实：TMS/ERP stub、VGM 须人签  
- **不把 light 少柜当出运结论**（mid50 可能炸）

## 命令

```bash
python scripts/diag_multi_container.py
python scripts/compare_446t_agent_vs_tool.py --tool-only
python scripts/run_phase0_baseline.py --quick
powershell -File scripts/competition_smoke.ps1
```

## 文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)  
- [multi-container-ffd-agent.md](./research/multi-container-ffd-agent.md)  
- 联网 review：`docs/research/competition-network-review-latest.md`  
- 分卡：`output/competition/SCORECARD.md`  
