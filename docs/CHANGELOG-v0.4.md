# CHANGELOG · v0.4.0

**Harness**：0.3.0 → **0.4.0**  
**架构口号**：总分总分总  

## 亮点

1. **详设结构事实** `design_facts`：无详设→待详设阻断；有截面/γ/图纸→detailed_design  
2. **自然语言改方案** `/api/revise-nl` + 网页输入框  
3. **评估器升级**：binding 自适应权重、metrics_table、柜数惩罚、space_subscore 废弃别名  
4. **Agent 可观测**：HITL user_confirm/hitl_wait、visualizer tools_used、volume_summary  
5. **多轮测试** `scripts/run_multi_round_tests.py` + workflow multi-round-test（full×2 全绿）  
6. **k 统一** pack_k_for_fill；loader fallback N0..n_max  

## 测试

```text
multi-round full × 2 → ALL_GREEN（8 项 STABLE）
```

## 主要路径

| 模块 | 变更 |
|------|------|
| structure_calc / design_facts / packing | 详设注入 |
| nl_revision / gateway / frontend | 自然语言改方案 |
| evaluator / orchestrator | 评估 plan 落地 |
| harness / trace | agent_steps、confirm 闸门 |
| scripts/run_multi_round_tests.py | 多轮回归 |
| docs/* | 评审与使用说明 |

## 升级注意

- 正式结构出运需 `knowledge/structure_design_facts.json` 或 API/NL 注入截面  
- 型钢表补充 **槽钢16#**；正式项目请用国标值覆盖  

## 后续补齐（对标后 · 同大版本）

7. **COG 工具** `tools/cog.py`：毛重优先；risk + visualizer 共用；分柜 primary  
8. **前端**：三视角 COG 红点/中心线 + **等轴测 3D**（拖拽旋转/滚轮缩放）  
9. **引擎 A/B** `scripts/compare_pack_engines.py` → `output/engine_ab_report.json`  
10. **同类对照** `docs/research/competitive-landscape.md`  

