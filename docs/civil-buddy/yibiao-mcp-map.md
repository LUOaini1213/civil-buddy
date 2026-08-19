# 易标模块 × 三级 MCP

对照易标流水线：`解析 parse → 提纲/扩写 outline → 质检/废标 qa → 知识库 kb → 落盘 write`。

可执行名册：`workbench/yibiao-map.json`（每个专家一行：`yibiao` + 独有工具名 + `aligned`）。

## 三级

| 层 | 谁能看见 | 现网工具 |
|----|----------|----------|
| 通用 | 每一位被召唤专家 | `search_kb` `read_kb` `list_kb` `write_deliverable` |
| 大类共享 | 同一大类 | 见 json `category_shared`。16 个大类各有 `*__scan_forbidden`（施工/设计/BIM/计划/安质环/商务/投标/采购/物机/试验/财务/资料/人力/行政/IT/现场人员） |
| 专家独有 | 仅该 `expert_id` | 66 岗均有独有写入器；同大类兄弟看不见。施工另有 `construction__scheme_draft` + `construction__fill_scheme_docx` |

`--pack construction` = 施工大类共享 + **施工方案**独有（不含危大独有）。`--expert method-hazard` 才带判定书。

MCP 2026-07-28 三原语：`tools/*` 之外还有 `resources/list|read`（`kb://` 私库/大类/公司，越权拒绝）和 `prompts/list|get`（`civil.bid.parse` / `civil.bid.compliance` / `civil.pack-ship.plan`）。`initialize.capabilities` 须同时宣告三者。长程见 `kb-mcp-horizon.md`。

## 本轮对齐

已对齐：66 / 66（`yibiao-map.json` 全部 `aligned: true`）。默认 **新加坡工地 / SG**：不编 SS/CP/BCA/WSH 条款号，缺数写 `[A001]` / `UNSPECIFIED`，禁止静默混入 GB/JGJ，高风险仍须「我明白，将由持证人员签认」。兄弟专家调用独有工具一律拒绝。`write_md` 在落盘前扫描法定断言与 SG 混用，命中则拒绝写盘。`zone_banner` 写出辖区；`DUAL` 必须分栏；`sg_only` / CN 规则过滤避免把 PSSCOC、GeBIZ、PUB 静默写进 CN 成稿。

66 岗 `web-knowledge.md` + 16 份大类 `_shared` + `company/web-portals.md` 已在 **2026-08-14 联网过两遍**。现场抽出：APPBCA-2026-12（2026-10-01 CORENET X 仅 GFA≥5,000 m²）、SCDF Fire Code 2023、PUB COP（排水 Add.3 / 污水 2025-09-01 / 海岸 2028）、CONQUAS 2022 + Private Residential、IRAS GST 页述 9%、SAC CE 001、SOP Act 页更 2026-08-05。
