# 多柜：为何不是「纯 FFD」，Agent 插在哪

## 两层不要混

| 层 | 现状 | 像什么 |
|----|------|--------|
| **柜内**（固定 N 柜） | `bin3d` **multi_start**：多种排序/叠高/重底候选，再 CoG 修理 | 固定 bin 数的 3D 多启启发 |
| **柜级**（开几柜） | `N0*` 下界 → 试装 N、N+1… → 可选 **末柜并回 N−1** | 下界 + 递增，**不是**论文级跨柜 FFD 全局最优 |

经典 **FFD（First Fit Decreasing）**：物品按体积/长降序，逐个放进**第一个能装下的柜**，装不下再开新柜。  
我们柜级是：**先估最少柜 N0\***，再在 **恰好 N 个柜**里做 3D 装载；失败才 N+1。  
更接近「**lower bound + open bin search**」，而不是边扫物品边开柜的在线 FFD。

## 为何不全改成 FFD

1. 3D 可行性 ≠ 1D 体积 FFD；逐件开柜对 **不可叠/两排/重心** 难控。  
2. 已有 **N0 订舱语义**（业务要先报柜数再装）。  
3. 柜内 multi_start + CoG 管道已重；柜级再套全局 FFD 成本高。  
4. 业界 multi-container 也常是 **两阶段：下界 → 分配/装箱**（与 N0*+试装同构）。

## Agent 结合点（有用，不是摆设）

| 角色 | 多柜职责 |
|------|----------|
| **Intent / Planner** | 锁柜预算、N0* 文案、优先序（重货/超长） |
| **Box scheme** | **防假多柜**（模块当量直通，避免空心 6m 架炸柜数） |
| **Loader** | 执行 N0*→试装→并回；写 `multi_container_explain` |
| **HITL** | 人确认柜型/是否接受 +1 柜 |
| **Critic** | 结构/装不下 → 回调成箱 options，而非傻加柜 |
| **UI** | 展示 N0* 分量与末柜偏空 → 可审计 |

**人算粗估** ≈ 只看重量柜；**Agent** = 重量+体积+几何下界 + 3D 试装轨迹 + 拒装/锁柜 + 说明。

## 本轮代码补齐

- `geom_n0_components` + N0*  
- 末柜并回  
- 模块级直通防假多柜  
- 前端「多柜规划」卡片  
- **成箱页 + HITL 同屏「建议柜数 N0\*」**（`hitl_summary` 现算 booking）  
- 诊断：`python scripts/diag_multi_container.py`  

## 利用率提升（446t util raise）

| 改动 | 作用 |
|------|------|
| 收紧 crate 尺寸启发式直通 | 混料不再整票 passthrough 误触发 |
| slot 软封顶 + 紧搜索起点 | 避免 N0\*=46 虚高 |
| weight_balance 严守 max_c | 修 group 无条件开柜 → used 可压到预算内 |
| 大票 light density 下界 | 柜数参考下界（**不可单独 ship**） |
| UI 大票 tips | 分票/低重量利用率提示 |

## 策略环（Agent 参与 · 2026-08）

```text
Tool: min_bins_light（参考） + balance_cog / tight_budget_cog
Agent: select_packing_strategy → mid50≥0.55 可出运中最少柜
Critic: mid50 差 → strategy_request=raise_bins_for_cog
UI/API: strategy_decision + 候选表
```

**硬规则**：`light_lb_fallback` / `min_bins_light` 不得作为出运策略（CoG 未保证）。  
对照：`scripts/compare_446t_agent_vs_tool.py` · `output/cases_446t/REPORT_agent_util_visibility.md` 

## 产品话术（给评委）

> 成箱完成后，工具给出建议订柜 **N0\***（不是模型拍数）。你确认箱方案与建议柜数后，Team B 做 3D 实装 **used**；柜内用 multi_start 优化摆法与重心。
