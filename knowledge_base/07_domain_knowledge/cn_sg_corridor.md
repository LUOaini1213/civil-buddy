---
category: domain
subcategory: corridor
priority: medium
type: reference
tags: [China, Singapore, VGM, CTU, SOLAS, ISPM15, corridor, MPA]
source: internal_summary_not_legal_advice
updated: "2026-07-30"
harness: ">=0.6.4"
status: active
---
# 中新走廊实务卡（中国出运 / 新加坡中转或到港）

> **声明**：本页为 Agent **可检索摘要**，便于解释与演示引用，**不是** GB / 海事局 / MPA 法规全文，**不能**替代船东、货代、当地主管与正式申报。  
> 国际底盘仍以 **IMO/ILO/UNECE CTU** 实务 + **SOLAS VGM** 为准（见 `01_rules/ctu_loading/*`、`01_rules/compliance/vgm_and_ship.md`）。

## 1. 层级关系（Agent 怎么用）

| 层 | 内容 | 在本系统中 |
|----|------|------------|
| **国际硬底** | CTU 装载/重心/绑扎实务；SOLAS 集装箱重量验证（VGM） | mid50、红线、结构过+进柜、`vgm.draft` |
| **中国侧操作** | 出口订舱、VGM 申报习惯、木包装出境 | 草稿 + 人签；不伪造称重 |
| **新加坡侧操作** | 港区/码头文件与操作习惯（中转极常见） | 交付物齐全；不替代港务系统 |
| **本库不做** | 危化全套、劳工安全全书、两国标准 PDF 全文 | — |

## 2. 中国侧（出口装柜）— 引用级要点

1. **VGM（SOLAS）**  
   - 整柜总重验证：方法 1（装货后称重）/ 方法 2（累加，需程序认可）。  
   - Agent 只产 **VGM 草稿**（`vgm.draft`），**必须人签**后才算正式。  
   - 皮重取箱门铭牌/船东数据，禁止模型编造。

2. **装载与绑扎**  
   - 与 CTU 一致：重心中段、横向勿过度偏心、重货底层、空隙塞实。  
   - 本系统：`mid50`、叠装限制、结构不通过不得进柜。

3. **包装**  
   - **木包装**出境：IPPC/ISPM15 标识（中新均认这套，比堆砌国标号更有用）。  
   - **铁架/钢结构件**：以本库标准箱 + `structure_calc` 为准，不硬绑建筑钢结构 GB。

4. **订舱/柜型**  
   - 20GP/40GP/40HQ/45HQ 内尺寸以知识库 containers 为准。  
   - 锁柜/`max_containers` 由 IntentSpec + 硬锁执行，禁止 LLM 擅自加柜。

## 3. 新加坡侧 — 引用级要点

1. **角色**  
   - 常见为 **中转枢纽** 或最终到港；文件链（提单/舱单/VGM）须与订舱一致。  
2. **港务/码头**  
   - 具体截止时间、EDI、码头操作以 **船东/码头指南** 为准（本库不写会死数字）。  
3. **与 Agent 的关系**  
   - 提供：可解释装载方案、双口径体积、重心、拒装红线、VGM/POR **草稿**。  
   - 不提供：MPA 系统代填、海关申报代办。

## 4. 与 tools 的绑定（可执行）

| 规则 | 工具/节点 |
|------|-----------|
| 结构过 + 外廓进柜 | `structure` · `box_scheme` · `packing` |
| 重心 mid50 | `cog.*` · risk · loader |
| 缺尺寸/超货载拒装 | material_parser · cargo_feasibility · replan |
| VGM 草稿须人签 | `vgm.draft` · finalize · HITL |
| 双口径防虚高利用率 | booking / dual_caliber · evaluator |
| 禁止 LLM 写 xyz | `illegal_tools` · tool 白名单 |

## 5. 检索话术（评委/用户问合规时）

- 「国际底是 CTU + SOLAS VGM；中新差异主要在 **申报与港区操作**，装载物理规则同一套。」  
- 「我们输出的是可审计草稿与红线，不是替代海事/港务批文。」  
- 「木箱出境看 ISPM15；铁架看结构计算与进柜几何。」

## 6. 明确不做 / 过期风险

- 不嵌入可过期的码头截止时刻表、费率、EDI 报文格式。  
- 不把 GB/JT/T/SS **全文**塞进检索（噪声大、法律风险）。  
- 货类若为危化，本走廊卡 **不适用**，需专项规则。

## 相关路径

- `01_rules/compliance/vgm_and_ship.md`  
- `01_rules/ctu_loading/safety_redlines.md`  
- `07_domain_knowledge/container_types.md`  
- `06_competition/scoring_criteria.md`
