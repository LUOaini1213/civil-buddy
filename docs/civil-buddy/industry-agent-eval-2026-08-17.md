# 行业 agent 产品联网评测 · 2026-08-17

问：Civil Buddy **是否合格的行业 agent 产品**。

**总判：部分合格。**

它已经是带纪律的土木/投标/装柜 **application harness**（工具独占数字、P0 HITL、成稿标草稿、矩阵抄原文、断线写 `UNSPECIFIED`）。它还不是可以坐在人对面替代持证人员、也不是可以递交 GeBIZ / 当法定专项方案的行业 agent。官方门户标题与 GST **9%** 抄对；缺的是默认面上的「先理解再聊或跑」、真 MCP 宿主、扫描 PDF。竞品只作旁证，不以易标 AGPL 或营销字数为合格线。

禁止把下列句子写成产品能力：中标率 +N%、可以投标、可以开工。

---

## 1. 官方页对照（本日联网）

抓取见会话 scratch `official-pages.md`。现场打开，不是只读本仓旧笔记。

| 门户 | 现场原文 | 本仓口径 | 判定 |
|------|----------|----------|------|
| [IRAS Current GST rates](https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates) | *The current GST rate in Singapore is 9%.* 另页 *When to Charge GST* 写 prevailing **9%**。 | `demo/kb/finance/*/web-knowledge.md` 抄同句，写稿标「页述 9%」 | **抄对** |
| [SCDF Fire Code 2023](https://www.scdf.gov.sg/fire-safety-services-listing/fire-code-2023) | *Fire Code 2023* / *Code of Practice for Fire Precautions in Buildings 2023* | 只列官方标题，条款 UNSPECIFIED | **抄对** |
| [IMO CTU Code](https://www.imo.org/en/ourwork/safety/pages/ctu-code.aspx) | *IMO/ILO/UNECE Code of Practice for Packing of Cargo Transport Units (CTU Code)*，2014，**non-mandatory** | 同标题、2014、非强制、不编条款号 | **抄对** |
| [MOF procurement processes](https://www.mof.gov.sg/policies/government-procurement/procurement-processes/) · [GeBIZ](https://www.gebiz.gov.sg/) | MOF：sourcing → evaluation（标书已公布标准）→ GeBIZ 公示授标。GeBIZ 首页是电子采购门户，无评分公式。页更 2025-12-01。 | GeBIZ 是门户不是评分办法；分值/PQM 只抄 ITT | **抄对** |

无「编造」项。IRAS 渲染页出现现行 **9%**；不得因旧 scrape 壳写成「官方没写」。GeBIZ **不是**评分办法。

---

## 2. 行业 agent 产品条（2026 常轴）

不得用「演示过」代替。本日驱动的是已上线 Python 主线 C：`run_tender_pipeline`、`POST /api/tender/parse`、`pack-ship__plan/export`（见 `product-eval.log`）。Rust `GET /api/eval/live` 本轮未起（无 `link.exe`）。

| 轴 | 判定 | 证据 / 缺口 |
|----|------|-------------|
| 工具独占数字（柜数 / xyz / `can_fit` / mid50） | **通过** | 断线四字段字面 `UNSPECIFIED`；有 solver 快照则原样投影，不重算。`pack-ship__export` HTTP 同口径。 |
| 高风险 HITL | **通过（窄）** | P0 `human_confirm_required=true`；危大写盘要确认句。默认经营岗仍是按钮，不是每句先问。 |
| 成稿仍标草稿 | **通过** | `submit_blocked=true`；bidbook DRAFT / NOT FOR SUBMIT；再审不填业绩、不改 `can_fit`。 |
| 可回放 trace / eval | **部分** | 管线有 `run_id`、矩阵/`exact_text`、OTEL 文件大盘、脚本评测。缺常驻 `GET /api/eval/live` 宿主；OTEL SDK 未装，只走 jsonl。 |
| 先理解再聊或跑 | **缺口** | `understand → chat/run/both` 在工作台 Rust；默认 `/` 是解析按钮，不是 Grok Build 式会话。 |
| 官方事实不编条款 | **通过** | 上表四门户抄对。 |
| 可发现工具 / MCP 宿主 | **部分** | list/plan/export 已露出；没有 Claude/Cursor 真宿主去调。 |
| 扫描招标 PDF | **缺口** | 产品拒绝扫描 PDF；MinerU 可选且本机未当作默认。 |
| 法定签认 / 递交 | **不做（正确）** | 无 PE/QP/RTO、无 GeBIZ 代交。这不是缺口，是边界。 |

---

## 3. 旁证（不是合格线）

| 仓 | API 现场 | 差在哪 |
|----|----------|--------|
| [OpenBidKit 易标](https://github.com/FB208/OpenBidKit_Yibiao) | ★2368 · AGPL-3.0 · 2026-08-17 仍推 | 写标 / 查重 / 桌面解析。本仓不并 AGPL，也不做十万字生成。 |
| [loadingmcp-mcp](https://github.com/lxxmng/loadingmcp-mcp) | ★0 · MIT · 2026-07-13 | 有宿主的 list/plan/export + 200+ 柜型。本仓不替换 solver。 |

README 营销字数、星标、「中标率」一律不当合格标准。

---

## 4. 仍不合格的具体缺口

1. 默认产品面不是「每个专家都是可聊天可跑的 harness」。
2. 没有接上的 MCP 客户端；`kb://` 分页未做。
3. 扫描件招标进不了矩阵。
4. 联网评测入口绑在 Rust 工作台，本机无链接器时不能当日常闸。
5. 沙箱是应用层路径策略，不是行业常说的内核隔离。

有纪律的内部起草搭子：**部分合格**。当「可投标 / 可开工 / 可代签」的行业 agent：**不合格**（且产品禁止这么宣传）。
