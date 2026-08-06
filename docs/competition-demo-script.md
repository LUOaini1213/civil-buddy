# 比赛演示脚本（5 分钟 · 评委向）— **已冻结 A+B**

**Harness v0.6.4** · **13 agents** · 主路径 **`agent_mode=steps`**  
**演示：关闭「演示自动确认」**，露出 `phase=await_user_confirm`  
**冻结日**：2026-08-05 · commit 基线 `7a0744d`（前端布局本地可另合）

---

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

---

## 冻结数字（口播只报这些）

### 主证据 · 446t 全 Agent（`compare_446t --full-agent`，2026-08-05）

| 项 | 冻结值 | 勿报 |
|----|--------|------|
| 柜型 | **40HQ** | 勿说默认 40GP |
| used | **25** | 勿报旧 29 / 假 light 21 |
| mid50 | **≈59%**（0.594） | 勿报 light 的 16–17% 当出运 |
| 重量利用率 | **≈64%** | — |
| phase | **done** | — |
| risk | **WARN**（level=high） | 勿说无风险 |
| ship_ok | **true** | — |
| strategy | **tight_budget_cog** | 勿把 light 当 chosen |
| light 参考 | **~21–24 柜** · mid≈**17%** · **reference_only** | **不可单独出运** |

**诚实一句（verdict）**：严格 CTU 偏好 mid50≥60% 时，标签可能仍写 `verdict=block`（mid 59% 贴线）；产品线 **mid≥55% 可讨论出运**（`ship_ok=true` + 风险 WARN），横向偏心大票可降 WARN 不 hard REJECT。

### 演示小票（关自动确认）

| 预设 | HITL | used | mid50 | strategy |
|------|------|------|-------|----------|
| **满载 high_util** | A=`await_user_confirm` → B=`done` | 1 | **67%** | balance_cog |
| **钢件 steel_light** | 同上 | 1 | **100%** | balance_cog |
| pipeline `auto_confirm=false` | 停在 **await_user_confirm** | — | — | — |

### 中等票回归（产品信任）

| 票 | used | mid50 | ship_ok | strategy / verdict |
|----|------|-------|---------|-------------------|
| **t30** 样例（~231 行） | 2 | 100% | true | balance_cog / warn |
| **t80** 样例（333 行） | 5 | **62%** | true | tight_budget_cog / warn |

### 评分话术

- 本地 scorecard 可 **~9.75**（phase0 + hard gates）  
- **对外诚实**：联网/评委口径报 **~8.85**；不报虚高 10.0  
- 已知边界：TMS/ERP stub、VGM 须人签、无 Key 时 LLM 为 policy_fallback

---

## 冻结 5 分钟路径（唯一主戏）

1. **预检** · 打开 `http://127.0.0.1:8000/` · `/api/health` → harness **0.6.4 / 13** · `demo_auto_confirm_default=false`  
2. **满载或钢件** · **确认「演示自动确认」关闭**  
3. **装箱方案页 / HITL**：箱表 + **建议柜数 N0\*** + 分量（重/体/底/槽）  
4. **确认并拼柜** · 看 **N0\* → 实装 used**、双口径、**mid50 / ship_ok**  
5. **策略卡** · 少柜 light=**参考 only**；Agent 选 `balance_cog` / `tight_budget_cog`（mid≥55%）  
6. **agent_steps**：A + B；tools 轨迹（模型不写 xyz）  
7. **备份 30s 多柜**：若评委问大票 → 口播 **25 柜 / mid≈59% / light 不写出运**  
8. **备份失败态**：缺尺寸大红条 或 80t 拒装；多柜票「末柜偏空/并回」

### 30s 多柜话术（背这段）

> Tool 出候选：少柜下界（light，mid 可能只有十几）vs CoG 可出运。  
> **Agent 按 CTU mid50 选**——446t 落在 **25×40HQ、mid≈59%、ship_ok**；  
> **21 柜是参考不是出运**；人确认大票后再拼柜。

### 25s 产品信任（可选 B）

> mid50 软线 55% 可讨论出运；60% 是 CTU 偏好。  
> 横向偏心在大票 + mid≥55% 时记 **WARN** 不硬打死压柜。  
> t30/t80 样例均 ship_ok，策略与 CoG 可审计。

### 20s 非标检验（出彩插段）

> HITL 同屏 **非标仪表盘**：超长 / 重件 / 定制 / 待详设分型。  
> **FAIL** 才硬拦；**WARN** 勾选后可拼柜。  
> 大票几百行非标关注是工艺现实——给 Top 风险而不是埋 log。  
> 模型最多读备注打标签；柜数坐标仍是 tools。  
> 详见 `docs/nonstandard-inspect.md`

---


### 20s 幕墙 SME 叙事（Team Mintang）

> Far East Facade 项目物料：Team A 成箱 + nonstandard.inspect；人确认后 Team B 拼柜；tools 出 N0* 与 xyz。

## 不说的话

- 不说「模型自己摆箱子 / 模型决定几柜」  
- 不默认吹 LLM tool-call 为主路径（主路径是 **steps + tools**）  
- 不报本地虚高 10.0；对外可用联网校准 **~8.85**  
- 诚实：TMS/ERP stub、VGM 须人签  
- **不把 light 少柜当出运结论**（mid50 可能炸）  
- 不回避：mid 59% 贴 60% 线、风险 WARN、大票需绑扎复核

---

## 预检清单（上场前 2 分钟）

```text
[ ] 网关 UP：GET /api/health → harness 0.6.4 · agents 13 · ok
[ ] 浏览器硬刷新 Ctrl+F5 → http://127.0.0.1:8000/
[ ] 「演示自动确认」= 关
[ ] 预设：满载 或 钢件
[ ] 备用：output/cases_446t/result_compare_live.json 数字能对上
[ ] 备用命令见下（不必现场跑 446t）
```

## 命令

```bash
# 演示预检
python scripts/smoke_agent_product.py
python scripts/test_mid50_cog.py

# 证据（上场前一天跑够即可）
python scripts/compare_446t_agent_vs_tool.py --full-agent
python scripts/diag_multi_container.py
python scripts/run_phase0_baseline.py --quick
powershell -File scripts/competition_smoke.ps1
```

## 证据与文档

| 文件 | 用途 |
|------|------|
| [competition-evidence-one-pager.md](./competition-evidence-one-pager.md) | **一页证据**（A+B） |
| [product-trust-notes.md](./product-trust-notes.md) | mid50 / lateral / 中等票 |
| `output/cases_446t/result_compare_live.json` | 446t 对照 JSON |
| `output/competition/demo_hitl_smoke.json` | 满载/钢件 HITL |
| `output/competition/mid_ticket_regression.json` | t30/t80 |
| `output/competition/SCORECARD.md` | 分卡 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 架构 |
| [multi-container-ffd-agent.md](./research/multi-container-ffd-agent.md) | 多柜研究 |

