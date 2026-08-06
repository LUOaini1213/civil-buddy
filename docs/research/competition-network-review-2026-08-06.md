# 联网 Workteams 评估 · packing-agent（2026-08-06 · ~3h 切片）

**Harness** 0.6.4 · **13 agents** · main@`17bf69e`+ 本轮改进  
**对照**：先前联网 **8.85**（2026-07-30）· 本地分卡 **~9.75**

---

## 总裁决

| 项 | 结果 |
|----|------|
| **联网校准综合** | **8.95 / 10** |
| 相对 8.85 | **improved（+0.10）** |
| 赢线 | **PASS**（≥7.5 且任务成功≥8.0） |
| 比赛 demo | **ship_ready = true** |
| 本地 9.75 | **禁止对外领衔**；仅硬门/归档 |

**一句话**：在 OptiGuide 式「tools 算数 + HITL」底座上，补齐 **通用材料表入口** 与 **非标分型检验**，外对分 **8.95**；仍不是 TMS/运营装柜平台。

---

## 本地硬证据（本轮刷新）

| 套件 | 结果 |
|------|------|
| `test_nonstandard_inspect` | ALL_PASS |
| `run_generic_table_tests` 解析 | **15/15** |
| `test_table_api_parse` | ALL_PASS |
| workteams tiny shadow | ok agree=1.0 illegal=0 |
| 随机 20 轮 steps（历史） | 20/20 |
| 随机 6 轮 shadow（历史） | fit 一致 6/6 · used 一致 4/6 |

---

## 联网外对标（2026 现场）

| 来源 | 映射到本仓 |
|------|------------|
| **Production agents**：HITL 是一等公民，非事后补丁 | 已有 A→confirm/reject→B + durable session |
| **LangGraph / Crew 类**：专岗 + 编排；失败在协调而非单点 LLM | 固定 13 专岗 + steps 主路径；llm_toolcall 影子 |
| **OTEL / 可追溯** | 有 trace.jsonl / agent_steps；深度身份/跨厂商 A2A 非目标 |
| **装柜软件**：计划+CoG/重下轻上/VGM | tools CoG mid50 + 双订舱；VGM 仍草稿/人签 |
| **CTU / 工业文**：重件中段、软件预排 | strategy 环 + mid50 门禁；light 柜禁止当出运 |

---

## 四组投票

| 组 | 分 | 判定 | 一句话 |
|----|-----|------|--------|
| **Alpha 架构** | 9.10 | PASS | HITL + tools 边界清晰；表入口+非标挂 Team A |
| **Beta 领域** | 9.05 | PASS | 通用表+钢结构双轨；mid50 薄缓冲仍在 |
| **Gamma 评测** | 8.45 | PASS | 金标/G 表/API 可回归；llm 柜数影子不一致诚实 |
| **Delta 演示** | 8.95 | PASS | 表上传+非标卡+策略卡；通宵 auto 噪声勿 merge 整支 |

未加权 ≈ **8.89** → Chief **8.95**。

---

## 六维（Chief）

| 维度 | 权重 | 分 | 要点 |
|------|------|-----|------|
| 任务成功 | 0.30 | **8.65** | phase0 task≈0.85 锚；表路径 pack G1–6 绿；+0.10 vs prior |
| 长程完成 | 0.15 | **9.10** | A→HITL→B + 表 inject profile 自动套档 |
| 工具质量 | 0.20 | **9.30** | mapper 单位归一 + table.parse 与 CLI 同核 |
| 多 Agent | 0.15 | **8.90** | 专岗非 deep routing；影子 used 可漂 |
| 效率 | 0.10 | **8.20** | 大票仍秒～分钟级 |
| 解释性 | 0.10 | **9.15** | 非标仪表盘 + health 表入口提示 |

---

## 排名改进 backlog（≤5 · 证据挂钩）

| # | 缺口 | 证据 | 期望 outcome | 本轮 |
|---|------|------|--------------|------|
| 1 | 通用表噪声行进 materials | G8 曾解析「注释/全零」 | 噪声丢弃，n_rows=有效货 | **已做** |
| 2 | 表 inject 未自动 generic 档 | 注入后仍 balanced 风险 | profile_id=generic_table | **已做** |
| 3 | health 未声明 table_parse | 预检不可发现 | features.table_parse=true | **已做** |
| 4 | llm policy_fallback 柜数漂 | workteams shadow 1 vs 3/4 | 演示强调 steps 为准 | 文档/诚实 |
| 5 | high_util mid50 擦 60% | 历史 66.7% | 舒适区抬升 | 未做（>3h 风险） |

---

## 本轮已落地

1. `table_mapper` 跳过 `#`/注释/qty≤0/全零行  
2. `material_parser`：表 meta → `apply_profile(generic_table)`  
3. `/api/health` features：`table_parse` / `nonstandard_inspect` / 路径提示  
4. 回归：`test_table_mapper_unit` G8 n=3；`test_generic_profile_auto`

---

## 诚实边界

- 非 MagicLogic/EasyCargo 运营产品  
- TMS/ERP/VGM 签章仍 stub  
- 联网分 **8.95** ≠ 本地 9.75  
- `auto/12h-merge` 心跳 commit **勿整支合入**
