# 招标解析 · 联网知识（2026-08-14 现场；2026-08-17 续）

岗位对应：把招标/ITT 拆成摘录表。无正文写「招标未写」。不组价、不写施组、不报「可以投标」。CN 对应读公告、投标人须知、评标办法前附表、清单封面。SG 对应 GeBIZ 下 ITT、evaluation criteria；施工公共标再对 BCA PQM。网上是入口，表里的天数、等级、分值只抄本项目文件。易标 parse → 本岗摘录表；评分点交 bid-tech；★项、签章、保证金交 bid-compliance。

## 2026-08-17 产品接线（主线 C 同一套 parse）

工作台 Python `extract_tender` 与装箱 `/api/tender/parse` 共用 `tender.handoff.v1`：评分点 / ★ / 专项 / 工期日历天 / 信封 / 评标办法名称只抄原文。P0 资格废标须人确认，**系统不判定可投标**。BCA PQM Framework（页述 2026-01-26）只当门户标题，禁止把框架价格质量**区间**当成本标分数。MCP：`civil.bid.parse` prompt + `kb://bid/...` resources。Rust `bid-parse__extract` 仍是本岗正则表，与 Python handoff 尚未并表（见 `docs/civil-buddy/kb-mcp-horizon.md` 阶段 B）。

辖区：用户 pack；未给则新加坡工地默认 SG。工程招标路径与政府采购货物服务路径不混用。本页不是规范全文库。

## CN
- 《标准施工招标资格预审文件》和《标准施工招标文件》暂行规定（发改委等 56 号令，2008-05-01 施行；2013-03-11 第 23 号令修订）：https://zfxxgk.ndrc.gov.cn/web/iteminfo.jsp?id=18459
- 《工程建设项目施工招标投标办法》（七部委 30 号令）：https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/200506/t20050613_960618.html
- 《招标投标法实施条例》（2011 公布、2019 修订）：https://scjgj.beijing.gov.cn/cxfw/flfgcxfw/qyjgl/202006/t20200620_1929418.html
- 《必须招标的工程项目规定》（发改委 16 号令，2018-03-27 公布、2018-06-01 施行）：https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/201803/t20180330_960858.html
- 《电子招标投标办法》（20 号令）：https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/201302/t20130220_960752.html
- 全国公共资源交易平台：https://www.ggzy.gov.cn/

公开口径：评标办法前附表须列明全部评审因素，未列明的不得作为评标依据（56 号令页述第八条口径）。招标文件应含评标标准和方法，实质性要求须醒目标明。依法必须招标项目的公告在指定媒介发布，资格预审/招标文件应使用标准文本。工程招标与政府采购货物服务是两套程序，用户未说清采购方式时先问，不把 87 号令评分套进房建施工标。评标办法公开名称是综合评估法或经评审的最低投标价法。保证金若收取，实施条例有估算价比例上限；本项目金额、账户以须知为准，无原文则 TBD。清单疑义走书面澄清，禁止私自改量改名。2026-05-28 地方转载仍称《招标投标法》2017 修正、《实施条例》2019 修订；本轮未见新法替代这两部题名。

## SG
- GeBIZ（Government Electronic Business）：https://www.gebiz.gov.sg/
- MOF Procurement processes（页更 2025-12-01）：评标按已公布的 evaluation criteria，一般含质量与价格。Tender 估算价超过 S$90,000；Quotation 不超过 S$90,000。Selective Tender 先做 pre-qualification。Tender Lite 估算价不超过 S$1 million；施工路径自 2025-05 起。Innovative Procurement Partnership 可覆盖试点并含部署期权。https://www.mof.gov.sg/policies/government-procurement/procurement-processes/
- MOF Government procurement（页更 2025-10-22）：透明、公平竞争、value for money；评标标准事先公布在 GeBIZ。https://www.mof.gov.sg/policies/government-procurement/overview/
- GeBIZ 供应商指南：Open / Selective / Limited Tender；Qualification。施工相关向 BCA 注册。Debarment 材料分 Procurement contracts before Jul 2025 / from Jul 2025。https://www.gebiz.gov.sg/singapore-government-procurement-regime.html
- GeBIZ FAQ（页脚 © 2026）：Two Envelope 为技术方案与报价分投；政府不保证只授最低价；电子标须先注册 Trading Partner。Tender Lite（ICT）页述自 2026-04 月底实施。Tender Lite（Construction）覆盖建筑/永久构筑物的修建改建，不含施工咨询。https://www.gebiz.gov.sg/faq.html
- BCA 官方页标题 **Price Quality Method (PQM) Framework**（页述 Last updated 26 January 2026）：https://www1.bca.gov.sg/growth-and-transformation/procurement/procurement-and-legal-frameworks/price-quality-method-pqm-framework/ 适用 all public sector construction tenders under CW01 General Building & CW02 Civil Engineering，Estimated Construction Cost (without contingency sum) of $3 million and above。现行公开件标题 *PQM Framework (Effective 1 November 2024)*，含 mandatory quality attribute on environmental sustainability。框架公布的是价格/质量**区间**（CW01 Price 40%–60%），不是本项目 ITT 分数；本标权重只抄 ITT。
- BCA QFM（页更 2026-03-13）：仅公共施工相关咨询标（建筑/结构/机电/工料测量/项目管理）。EOI 于 2025-12-01 及之后发出的走 Enhanced QFM。不要把 QFM 权重抄进施工 ITT 摘录表。https://www1.bca.gov.sg/growth-and-transformation/procurement/procurement-and-legal-frameworks/quality-fee-method-qfm-framework/

公开口径：本次检索未在 GeBIZ、MOF、BCA 官方页见到名为「PEQ」的独立评标框架；施工公开评标词是 PQM，资格阶段公开词是 Qualification。天数、权重、workhead 只抄本项目 ITT。Government Supplier Registration（GRA supply head）与 BCA 施工 workhead 不是同一登记。

## 通用
禁令：不贴法条全文与自编条款号；不上个项目工期、资质、控制价；不写胜率、「建议投/弃」、「可以投标」「报审通过」。无附件写「待企业库补」，不编业绩和证号。DUAL 分栏。
