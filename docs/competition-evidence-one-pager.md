# 一页证据 · A+B 冻结（2026-08-05）

**Repo** `https://github.com/LUOaini1213/packing-agent` · 代码基线 **`7a0744d`**  
**Harness** 0.6.4 · **13 agents** · 架构 `big_team_wraps_a_b` · 主路径 `agent_mode=steps`

---

## A · 演示就绪

| 检查项 | 结果 |
|--------|------|
| Gateway `/api/health` | UP · demo_auto_confirm_default=**false** · agents=13 |
| HITL 满载 high_util | A=`await_user_confirm` → B=`done` · used=1 · mid50=**67%** · ship path OK |
| HITL 钢件 steel_light | 同上 · used=1 · mid50=**100%** |
| pipeline `auto_confirm=false` | 停在 `await_user_confirm`（露出确认点） |
| smoke_agent_product | ALL_PASS |
| mid50 CTU 回归 | high_util 67% · steel 100% · PASS |
| HITL resume suite | 5/5 PASS |

**话术锚点**：柜数/坐标 = tools；人确认成箱后再拼柜；LLM 不做 N 柜/xyz。

---

## A · 大票对照 446t（现场可只口播表）

命令：`python scripts/compare_446t_agent_vs_tool.py --full-agent`  
产物：`output/cases_446t/result_compare_live.json`

| 路径 | used | mid50 | wt | strategy | light 参考 | 说明 |
|------|------|-------|-----|----------|------------|------|
| **Tool 捷径** | **25** | **0.594** | 0.643 | soft_budget_cog_soft | 21 · mid 0.176 · ref only | 不出运 light |
| **全 Agent** | **25** | **0.594** | 0.643 | **tight_budget_cog** | 24 · mid 0.168 · ref only | phase=**done** · risk=**WARN** · **ship_ok=true** |
| 旧基线 | 29 | ~0.57 | 0.59 | — | — | 已废弃口播 |
| 假 light | 21 | **0.16** | 0.77 | light | — | **禁止当出运** |

- N0\*=35（wt/vol/floor/slot 取 max）；3D 实装 25（相对 N0\* −10）  
- verdict 标签可能为 `block`（mid 59% &lt; 严格 60% 偏好），与 **ship_ok=true** 并存——口播用 ship_ok + WARN，见 trust notes  

---

## B · 产品信任

| 票 | used | mid50 | ship_ok | strategy | verdict |
|----|------|-------|---------|----------|---------|
| t30 样例 | 2 | 1.00 | true | balance_cog | warn |
| t80 样例 | 5 | **0.619** | true | tight_budget_cog | warn |

**规则摘要**

1. light / min_bins_light = **reference_only**，不可单独 ship  
2. 出运候选要求 mid50 **≥55%**（软线）；CTU 偏好 **≥60%**  
3. 大票多柜 + mid≥55%：横向偏心 ≥15% → **WARN**（不 hard REJECT 打死压柜）  
4. Critic：mid 55–60% 不抬柜；&lt;55% 才 raise  

产物：`output/competition/mid_ticket_regression.json` · `demo_hitl_smoke.json`

---

## 评分（诚实）

| 口径 | 分数 |
|------|------|
| 本地 scorecard（phase0+gates） | **~9.75** · 赢线/冲刺 PASS（见 `output/competition/SCORECARD.md`） |
| 对外/联网校准 | **~8.85** · 不报 10.0 |
| 边界 | TMS/ERP stub · VGM 人签 · LLM 无 Key → policy_fallback |

---

## 5 分钟路径（唯一主戏）

1. 硬刷新 UI → 关自动确认  
2. 满载或钢件 → HITL 箱表 + N0\*  
3. 确认拼柜 → used / mid50 / 策略卡  
4. agent_steps 点 tools 轨迹  
5. 若问大票：25 柜 · mid≈59% · light 不是出运  

详稿：`docs/competition-demo-script.md`
