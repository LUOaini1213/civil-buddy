# 产品主线：项目投标应答 + 交付链路（幕墙窄行业）

> **主线代号**：**C** · Tender × Delivery  
> **行业**：幕墙 / 建筑围护 / 项目物料（REDACTED-VENDOR 类）  
> **基座**：现有 packing-agent（大 Team ⊃ A 成箱 + B 拼柜）  
> **Harness**：≥0.6.4  
> **状态**：M0–M1 完成 · **M2 可演示**（`/api/tender/delivery` + 默认 UI）  

---

## 1. 一句话

> 读招标与工程要求 → 抽出应答要点与红线 → 用物料与装柜 tools 生成**可交付的物流/装箱方案草稿** → 人确认 → 导出应答附件。  
> 新加坡幕墙范围可输出 **英文整本草案**（Harbourline Facade DEMO · `[TO FILL]` 资质/报价）。  
> **不**编造业绩、BCA 等级、检测报告号或 SGD 金额；**不**对接 GeBIZ。

---

## 2. 与旧主线关系

| | 装柜主线（保留为交付引擎） | 新主线（产品叙事） |
|--|---------------------------|-------------------|
| 用户问题 | 这批料怎么装柜 | 这个标怎么应、交付行不行 |
| 输入 | NL + 物料表 | **招标/技术规格** + 物料/工程量 + NL |
| 输出 | 装箱方案、3D、风险、订舱草稿 | **应答清单 + 偏离/风险 + 装柜交付包** |
| 代码 | `teams/*` 主路径 **不变** | 上游加 **Team T（投标）**，下游仍 A/B |

黑客松阶段：对外仍可讲 SME「装柜/运营」；产品路线图以本文为准。

---

## 3. 组织（扩展，不推翻 A/B）

```text
大 Team（Supervisor）
  ├─ 小 Team T · 投标应答（新）
  │     解析招标 → 资格/评分/运输包装红线 → 应答要点 → 审核清单
  ├─ 小 Team A · 成箱（已有）
  └─ 小 Team B · 拼柜交付（已有）
HITL：标书要点确认 · 成箱确认 · 出运确认
```

| 小 Team | 职责 | 复用 |
|---------|------|------|
| **T 投标** | 招标文件要点、废标/响应检查、应答提纲 | 新建 tools + agents |
| **A 成箱** | 材料→标准箱 | 现有 |
| **B 拼柜** | N0* / 3D / CoG / 风险 / 出图 | 现有 |
| **大 Team** | 编排、有界 replan、finalize、导出 | 现有 + 接 T 的 summary |

**硬边界（继承）：** 尺寸/柜数/坐标/金额阈值 → **tools**；LLM 只调度与解释。

---

## 4. 主路径（Happy path）

```text
招标文件 / 技术规格 / NL
  → Team T：parse_tender → extract_requirements → compliance_checklist
  → HITL（确认响应范围与红线）
  → Team A：材料/工程量 → 成箱
  → HITL（成箱方案）
  → Team B：N0* → 3D → CoG → 风险
  → 大 Team：把「运输/包装条款」与装柜结果对齐（响应矩阵）
  → finalize：应答摘要 + packing 附件 + 待人工签字项
```

---

## 5. MVP 范围（先做能演示的）

### 做

1. **招标 PDF/文本** → 结构化：`资格要求` `评分点` `包装运输` `工期` `废标项候选`  
2. **响应矩阵**：条款 → 状态（已覆盖 / 待补 / 不适用）→ 链接到装柜结果或知识库  
3. **交付引擎**：现有 A/B 全链路（物料表可来自项目料单）  
4. **HITL 两闸**：投标要点确认 + 成箱确认  
5. **导出**：一页应答摘要 Markdown/JSON + 现有 packing 出图/订舱草稿  

### 暂不做

- 编造企业业绩、BCA workhead、检测报告号、SGD 报价  
- 盖章式 / GeBIZ 可提交正本  
- 对接交易平台投标接口  
- 串标检测（可后期）  

---

## 6. 工具清单（新增 vs 复用）

| 工具 ID（建议） | 状态 | 说明 |
|-----------------|------|------|
| `tender.parse` | 新建 | 招标文件分块 + 条款抽取 |
| `tender.checklist` | 新建 | 废标/必交/运输包装勾选 |
| `tender.response_matrix` | 新建 | 条款↔证据（装柜/知识库 path） |
| `knowledge.search` | 已有 | 规范/策略 |
| `material.*` / `box.*` / `bin3d.*` / `booking.*` / `cog.*` | 已有 | 交付 |
| `hitl.confirm` | 已有 | 多闸扩展 intent |
| `export.shipment` / packing plan | 已有 | 附件 |

---

## 7. 里程碑

| 阶段 | 目标 | 验收 | 现状 |
|------|------|------|------|
| **M0** 叙事冻结 | 本文 + 对外一句话 | 团队对齐 | ✅ |
| **M1** Team T 骨架 | parse + checklist + matrix | 无装柜也能跑 T | ✅ `tender.*` + 单测 |
| **M2** T→A/B 串联 | facade 样例端到端 | can_fit + 矩阵 + 导出包 | ✅ `run_tender_delivery_pipeline` · `/api/tender/delivery` |
| **M2.1** 条款级交接 | ★/评分点/专项行 + P0 + 技术标目录 | handoff.next_experts · 不编天数 | ✅ `tender.handoff.v1` · UI 经营岗交接 |
| **M3** 演示包 | 3 分钟：招标 → 矩阵 → 交付 → 人工待办 | 黑客松/客户 demo | ✅ UI 经营岗交接 + P0 + 多文件/表格节选 + CSV 导出 |
| **M4** 知识库 | `08_tender_delivery` search 可引用 | search 命中策略/轨迹 | 🚧 目录已有，绑 search 待强 |

### 代码入口（主线 C）

```text
packing_assistant/tender_delivery.py     # run_tender_delivery_pipeline
packing_assistant/tools/tender_parse.py  # parse / checklist / matrix / export
packing_assistant/bidbook/sg_facade.py   # 新加坡幕墙英文整本草案
POST /api/tender/parse                   # 仅矩阵（text / sections）
POST /api/tender/parse/file              # 单文件节选
POST /api/tender/parse/files             # 多文件 + 表格 → 同一矩阵
POST /api/tender/delivery                # 矩阵 + A/B + bidbook
POST /api/tender/review                  # 成稿后再审（禁语 + 缺项）
GET  /api/otel/dashboard                 # OTEL 大盘（真 span）
GET/POST /api/mcp/tools                  # pack-ship list/plan/export
POST /api/tender/bidbook                 # 英文整本（默认可不跑装柜）
frontend/index.html                      # 默认产品面（复制英文标书草案）
frontend/workbench.html                  # 工程装柜台（旧装柜 UI）
```

---

## 8. 样例故事（口播 40 秒）

> 业主招标要求项目物料按规范包装出运、可追溯柜型。  
> Agent 先抽运输/包装与资格红线；人确认范围后，用真实料单成箱拼柜，tools 算出柜数与重心。  
> 最后给出响应矩阵：哪些条款已用装柜方案覆盖，哪些仍需商务/法务签字——**可试点，不是幻觉写标书**。

---

## 9. 代码落点

```text
docs/product-mainline-tender-delivery.md
knowledge_base/08_tender_delivery/
packing_assistant/tender_delivery.py         # M2 产品入口（已落地）
packing_assistant/tools/tender_parse.py      # parse/checklist/matrix/export
packing_assistant/teams/big_team.py          # 交付引擎（不变）
gateway/app.py                               # /api/tender/*
frontend/index.html                          # 主线 C UI
```

**原则：** 不改坏现有 `run_big_team` 装柜主路径；主线 C 走 `run_tender_delivery_pipeline`，装柜仍为 tools 算数。

---

## 10. 成功标准

| 指标 | 目标 |
|------|------|
| 假招标样例 | 运输/包装条款抽取 Recall 可解释 |
| 端到端 | facade 料单 → can_fit 有值 + 响应矩阵 ≥5 行 |
| 非法 | illegal_tool_calls=0；无 LLM xyz |
| 叙事 | 3 分钟讲清「投标应答 + 交付」 |

---

## 相关文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) — 装柜引擎  
- [competition-demo-script.md](./competition-demo-script.md) — 答辩演示（装柜）  
- `knowledge_base/08_tender_delivery/` — 投标交付知识  
