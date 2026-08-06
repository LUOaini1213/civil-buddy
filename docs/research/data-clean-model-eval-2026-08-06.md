# 数据清洗 + 模型评测 · 2026-08-06

**HEAD**：见本提交 · **Harness** 0.6.4  
**性质**：材料表清洗可回归 + Agent 影子模型评测（**非** ML 训练 loss/BLEU）

---

## 1. 数据清洗

### 覆盖（真实 `parse_table_file`）

| 夹具 | 脏点 | 观测 |
|------|------|------|
| G6_messy_headers | 乱表头 / m·cm·mm 混列 | n_rows=4 · L 归一 mm |
| G8_noise_rows | 注释/空行/零行 | n_rows=3 · n_skipped≥1 |
| G9_weight_tons | 吨→kg | weights 含 1250/850 kg |
| G15_mixed_units_stress | cm/m/mm 混用 | sample L/W=450/300 mm |
| 合成 | 合计/小计/备注 | 过滤；真货保留 |

### 加固点

- `table_mapper.rows_to_ir`：汇总行（合计/小计/total…）、备注整行、全角空白
- `stats` 带清洗计数：`n_input_rows` / `n_skipped_total` / `n_skip_*` / `clean`
- 回归：`scripts/test_data_clean_dirty_tables.py`

证据：`{SCRATCH}/data_clean_eval.log`

---

## 2. 模型评测（Agent 影子）

| 项 | 结果 |
|----|------|
| 入口 | `eval_workteams_cli --tiny-only` + `test_model_eval_shadow.py` |
| agree | **1.0** |
| illegal | **0** |
| path_honesty | reference_only=**true** · booking_authority=**steps_tools** |
| 本地 SCORECARD | ~**9.75** · **禁止对外领衔** |
| 对外联网分 | 另报 **~9.10**（full-team network eval） |

证据：`{SCRATCH}/model_eval_shadow.log` · `model_eval_honesty.log`  
产物：`output/eval_workteams_model_eval.json` · `output/eval_workteams_model_eval_summary.json`

---

## 3. 诚实声明

| 分数 | 用途 |
|------|------|
| 本地 SCORECARD ~9.75 | 硬门/phase0 归档 · **勿对外开场** |
| 联网校准 ~9.10 | Agent 应用 / Team 对外口径 |
| workteams agree=1.0 | 影子路径一致性 KPI · **不是**装柜 SaaS 满分 |

模型评测在本仓 = **steps vs llm_toolcall 影子 + 工具非法调用门**，不是微调指标。

---

## 4. 一句话

> 脏表经真实 parse 可清洗可数；模型影子 agree=1.0 illegal=0 且 reference_only 可见；对外报联网分，不报本地 9.75。
