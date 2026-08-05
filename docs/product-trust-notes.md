# 产品信任笔记（B · mid50 / lateral / 中等票）

**冻结日** 2026-08-05 · 与 A 演示脚本配套

## 1. 双阈值与出运语义

| 符号 | 含义 | 产品用法 |
|------|------|----------|
| mid50 | 中段 50% 长度内的质量占比 | CTU 偏好 ≥**60%**；软出运线 ≥**55%** |
| light used | min-bins / light_lb 试装柜数 | **仅参考**，`reference_only`，`ship_ok_hint=false` |
| strategy.chosen | Agent 选中的出运策略 | 不得为 `min_bins_light` / `light_lb_fallback` |
| ship_ok | 可讨论出运（can_fit + 风险非 hard block） | WARN 仍可为 true |
| verdict.level | 展示标签（含严格 CoG 门槛） | 可能 `block` 而 ship_ok 仍 true |

### 446t 现场诚实读法

- used=**25** · mid50=**59.4%** · strategy=**tight_budget_cog** · phase=**done**  
- risk decision=**WARN** · **ship_ok=true**  
- `verdict.level=block` 因「严格 mid50≥60%」贴线（摘要含「宜≥60%」）  
- **口播**：可出运讨论 + 绑扎复核；不把 59% 说成完美 60%+；绝不把 light 21 柜当结论  

## 2. Lateral（横向偏心）

- 大票多柜且 mid50≥55%：横向 ≥15% 倾向 **WARN**，避免压柜结果被 hard REJECT 一票否决  
- 仍展示偏心数字与建议动作；VGM/绑扎人工签  

## 3. 中等票回归（本轮实测）

| Case | n_mats | used | mid50 | wt | ship_ok | strategy | verdict | wall |
|------|--------|------|-------|-----|---------|----------|---------|------|
| t30 sample | 231 | 2 | 100% | 74% | true | balance_cog | warn | ~85s |
| t80 sample | 333 | 5 | 62% | 65% | true | tight_budget_cog | warn | ~255s |

数据：`output/competition/mid_ticket_regression.json`

## 4. 演示小票 HITL

| Case | HITL | used | mid50 | strategy |
|------|------|------|-------|----------|
| high_util | 关 auto_confirm → 确认后 done | 1 | 67% | balance_cog |
| steel_light | 同上 | 1 | 100% | balance_cog |

数据：`output/competition/demo_hitl_smoke.json`

## 5. 信任边界（对外必说）

- 数值引擎 = **tools**（N0\*、3D、CoG）；LLM = Intent / 解释 / 可选 shadow tool-call  
- TMS/ERP 为 stub；不构成真实订舱  
- 超长件 / 重箱在 risk items 中逐条列出，需工艺复核  
- 本地高分 ≠ 无人工  

## 6. 回归命令

```bash
python scripts/test_mid50_cog.py
python scripts/test_hitl_resume_competition.py
python scripts/compare_446t_agent_vs_tool.py --full-agent
# t30/t80 样例见 output/competition/mid_ticket_regression.json 的生成方式（harness pipeline）
```
