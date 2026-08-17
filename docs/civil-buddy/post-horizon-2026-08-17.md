# 66 岗对照易标 / pack-agent 的长程规划（2026-08-17）

每岗一条。车道 = `lane-<大类>`（子代理分批，不是 16 份大类摘要冒充）。
易标完成度 = parse → outline → qa → kb → write。pack-agent = 数字只抄 solver + list/plan/export + 断线 UNSPECIFIED。
内部讨论草稿。不以可以投标、可以开工、中标率 +N% 为完成目标。本轮只规划，不实现缺口。

## 长程总序

- 1. 保持 66 岗同一套 chat/run，不回退成一召唤就写盘。
- 2. bid-parse / bid-compliance / bid-tech 与经营岗矩阵、再审共用同一 handoff。
- 3. pack-ship 把真实 packing_summary 抄进 list/plan/export，断线 UNSPECIFIED。
- 4. construction / method-hazard 高风险确认句后出讨论提纲，不写法定专项。
- 5. 其余岗按大类补独有工具栏位（造价/计划/试验/财务/监理…），缺数不编。
- 6. 有宿主后再做 kb:// 分页；扫描 PDF 仅可选 CLI，失败拒绝。

## 覆盖

- 岗位数：66


## 大类 `bid` · 车道 `lane-bid`

### bid-parse

- 名称：招标解析
- 子代理/车道：`lane-bid`
- 对照：yibiao
- 独有：bid-parse__extract
- parse：已有 · bid-parse__extract / run_tender_pipeline（exact_text）
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · bid__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bid-parse__extract；chat 不写盘
- 下一刀：经营岗 turn 与 bid-parse 共用同一 extract 表；可选接通本机 MinerU，失败仍拒绝，不默认 OCR。

### bid-compliance

- 名称：废标检查
- 子代理/车道：`lane-bid`
- 对照：yibiao
- 独有：bid-compliance__gaps
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · bid__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bid-compliance__gaps；chat 不写盘
- 下一刀：把 tender.review.v1 禁语/缺项接到本岗 exclusive gaps，仍不判定废标。

### bid-tech

- 名称：技术标
- 子代理/车道：`lane-bid`
- 对照：yibiao
- 独有：bid-tech__expand
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · bid-tech__expand 提纲/说明
- qa：已有 · bid__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bid-tech__expand；chat 不写盘
- 下一刀：技术标目录只按抽出评分点扩章，无评分点则待对照，不套上个项目。


## 大类 `design` · 车道 `lane-design`

### architecture

- 名称：建筑
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：architecture__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · architecture__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 architecture__memo；chat 不写盘
- 下一刀：在 chat/run 上把 architecture__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### structure

- 名称：结构
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：structure__calc_outline
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · structure__calc_outline 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 structure__calc_outline；chat 不写盘
- 下一刀：在 chat/run 上把 structure__calc_outline 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### geotech

- 名称：岩土勘察
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：geotech__brief
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · geotech__brief 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 geotech__brief；chat 不写盘
- 下一刀：在 chat/run 上把 geotech__brief 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### plumbing

- 名称：给排水
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：plumbing__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · plumbing__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 plumbing__memo；chat 不写盘
- 下一刀：在 chat/run 上把 plumbing__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### hvac

- 名称：暖通
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：hvac__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · hvac__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 hvac__memo；chat 不写盘
- 下一刀：在 chat/run 上把 hvac__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### electrical

- 名称：电气
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：electrical__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · electrical__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 electrical__memo；chat 不写盘
- 下一刀：在 chat/run 上把 electrical__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### fire-protect

- 名称：消防
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：fire-protect__brief
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · fire-protect__brief 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 fire-protect__brief；chat 不写盘
- 下一刀：在 chat/run 上把 fire-protect__brief 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### steel

- 名称：钢结构
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：steel__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · steel__memo 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 steel__memo；chat 不写盘
- 下一刀：在 chat/run 上把 steel__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### landscape

- 名称：园林景观
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：landscape__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · landscape__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 landscape__memo；chat 不写盘
- 下一刀：在 chat/run 上把 landscape__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### interior

- 名称：室内装修
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：interior__schedule
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 interior__schedule；chat 不写盘
- 下一刀：在 chat/run 上把 interior__schedule 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### facade

- 名称：幕墙
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：facade__brief
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · facade__brief 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 facade__brief；chat 不写盘
- 下一刀：在 chat/run 上把 facade__brief 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### intel-weak

- 名称：智能化弱电
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：intel-weak__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · intel-weak__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 intel-weak__memo；chat 不写盘
- 下一刀：在 chat/run 上把 intel-weak__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### civil-defense

- 名称：人防
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：civil-defense__brief
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · civil-defense__brief 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 civil-defense__brief；chat 不写盘
- 下一刀：在 chat/run 上把 civil-defense__brief 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### hydraulic

- 名称：水利
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：hydraulic__outline
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · hydraulic__outline 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 hydraulic__outline；chat 不写盘
- 下一刀：在 chat/run 上把 hydraulic__outline 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### port

- 名称：港航
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：port__outline
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · port__outline 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 port__outline；chat 不写盘
- 下一刀：在 chat/run 上把 port__outline 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### municipal

- 名称：市政道路
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：municipal__memo
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · municipal__memo 提纲/说明
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 municipal__memo；chat 不写盘
- 下一刀：在 chat/run 上把 municipal__memo 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### bridge

- 名称：桥梁
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：bridge__outline
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · bridge__outline 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bridge__outline；chat 不写盘
- 下一刀：在 chat/run 上把 bridge__outline 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### tunnel

- 名称：隧道
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：tunnel__outline
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · tunnel__outline 提纲/说明
- qa：已有 · design__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 tunnel__outline；chat 不写盘
- 下一刀：在 chat/run 上把 tunnel__outline 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### traffic

- 名称：交通工程
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：traffic__skeleton
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 traffic__skeleton；chat 不写盘
- 下一刀：在 chat/run 上把 traffic__skeleton 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### design-coord

- 名称：设计统筹
- 子代理/车道：`lane-design`
- 对照：yibiao
- 独有：design-coord__minutes
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · design__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 design-coord__minutes；chat 不写盘
- 下一刀：在 chat/run 上把 design-coord__minutes 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `bim` · 车道 `lane-bim`

### bim-coord

- 名称：模型协调
- 子代理/车道：`lane-bim`
- 对照：yibiao
- 独有：bim-coord__clash
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · bim__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bim-coord__clash；chat 不写盘
- 下一刀：碰撞/算量/LOD 只出表头与口径，不接 IFC 真抽量（另开一轮）。

### bim-qto

- 名称：模型算量
- 子代理/车道：`lane-bim`
- 对照：yibiao
- 独有：bim-qto__rules
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · bim__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bim-qto__rules；chat 不写盘
- 下一刀：碰撞/算量/LOD 只出表头与口径，不接 IFC 真抽量（另开一轮）。

### bim-deliver

- 名称：模型交付
- 子代理/车道：`lane-bim`
- 对照：yibiao
- 独有：bim-deliver__lod
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · bim__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 bim-deliver__lod；chat 不写盘
- 下一刀：碰撞/算量/LOD 只出表头与口径，不接 IFC 真抽量（另开一轮）。


## 大类 `planning` · 车道 `lane-planning`

### plan-master

- 名称：总控计划
- 子代理/车道：`lane-planning`
- 对照：yibiao
- 独有：plan-master__network
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · plan-master__network 提纲/说明
- qa：已有 · planning__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 plan-master__network；chat 不写盘
- 下一刀：在 chat/run 上把 plan-master__network 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### plan-lookahead

- 名称：周月计划
- 子代理/车道：`lane-planning`
- 对照：yibiao
- 独有：plan-lookahead__week
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · plan-lookahead__week 提纲/说明
- qa：已有 · planning__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 plan-lookahead__week；chat 不写盘
- 下一刀：在 chat/run 上把 plan-lookahead__week 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### plan-resource

- 名称：资源负荷
- 子代理/车道：`lane-planning`
- 对照：yibiao
- 独有：plan-resource__peak
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · plan-resource__peak 提纲/说明
- qa：已有 · planning__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 plan-resource__peak；chat 不写盘
- 下一刀：在 chat/run 上把 plan-resource__peak 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `construction` · 车道 `lane-construction`

### construction

- 名称：施工方案
- 子代理/车道：`lane-construction`
- 对照：yibiao
- 独有：construction__scheme_draft, construction__fill_scheme_docx
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · construction__scheme_draft, construction__fill_scheme_docx 提纲/说明
- qa：已有 · construction__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 construction__scheme_draft, construction__fill_scheme_docx；chat 不写盘
- 下一刀：scheme_draft 继续 11 章讨论提纲；确认句之后才写盘，不当法定专项。

### method-hazard

- 名称：危大识别
- 子代理/车道：`lane-construction`
- 对照：yibiao
- 独有：method-hazard__judge_hazard
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · construction__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 method-hazard__judge_hazard；chat 不写盘
- 下一刀：判定书只打三态+依据标题；不写可以开工。

### survey

- 名称：测量
- 子代理/车道：`lane-construction`
- 对照：yibiao
- 独有：survey__record
- parse：部分 · 独有 survey__record 可抄用户原文，无扫描 PDF
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · construction__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 survey__record；chat 不写盘
- 下一刀：在 chat/run 上把 survey__record 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### dispatch

- 名称：生产调度
- 子代理/车道：`lane-construction`
- 对照：yibiao
- 独有：dispatch__daily
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · construction__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 dispatch__daily；chat 不写盘
- 下一刀：在 chat/run 上把 dispatch__daily 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `hse` · 车道 `lane-hse`

### safety-brief

- 名称：安全交底
- 子代理/车道：`lane-hse`
- 对照：yibiao
- 独有：safety-brief__talk
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · safety-brief__talk 提纲/说明
- qa：已有 · hse__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 safety-brief__talk；chat 不写盘
- 下一刀：在 chat/run 上把 safety-brief__talk 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### quality

- 名称：质量
- 子代理/车道：`lane-hse`
- 对照：yibiao
- 独有：quality__lot
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · hse__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 quality__lot；chat 不写盘
- 下一刀：在 chat/run 上把 quality__lot 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### env

- 名称：环保文明
- 子代理/车道：`lane-hse`
- 对照：yibiao
- 独有：env__list
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · hse__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 env__list；chat 不写盘
- 下一刀：在 chat/run 上把 env__list 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### emergency

- 名称：应急
- 子代理/车道：`lane-hse`
- 对照：yibiao
- 独有：emergency__plan
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · emergency__plan 提纲/说明
- qa：已有 · hse__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 emergency__plan；chat 不写盘
- 下一刀：在 chat/run 上把 emergency__plan 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `commercial` · 车道 `lane-commercial`

### cost

- 名称：造价
- 子代理/车道：`lane-commercial`
- 对照：yibiao
- 独有：cost__takeoff
- parse：部分 · 独有 cost__takeoff 可抄用户原文，无扫描 PDF
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · commercial__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 cost__takeoff；chat 不写盘
- 下一刀：在 chat/run 上把 cost__takeoff 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### variation

- 名称：变更签证
- 子代理/车道：`lane-commercial`
- 对照：yibiao
- 独有：variation__form
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · commercial__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 variation__form；chat 不写盘
- 下一刀：在 chat/run 上把 variation__form 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### claim

- 名称：索赔调概
- 子代理/车道：`lane-commercial`
- 对照：yibiao
- 独有：claim__notice
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · commercial__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 claim__notice；chat 不写盘
- 下一刀：在 chat/run 上把 claim__notice 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### subcontract

- 名称：分包结算
- 子代理/车道：`lane-commercial`
- 对照：yibiao
- 独有：subcontract__sheet
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · commercial__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 subcontract__sheet；chat 不写盘
- 下一刀：在 chat/run 上把 subcontract__sheet 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### interim

- 名称：验工计价
- 子代理/车道：`lane-commercial`
- 对照：yibiao
- 独有：interim__measure
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · commercial__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 interim__measure；chat 不写盘
- 下一刀：在 chat/run 上把 interim__measure 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `procurement` · 车道 `lane-procurement`

### proc-plan

- 名称：采购计划
- 子代理/车道：`lane-procurement`
- 对照：yibiao
- 独有：proc-plan__schedule
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · proc-plan__schedule 提纲/说明
- qa：已有 · procurement__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 proc-plan__schedule；chat 不写盘
- 下一刀：在 chat/run 上把 proc-plan__schedule 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### proc-compare

- 名称：比价询价
- 子代理/车道：`lane-procurement`
- 对照：yibiao
- 独有：proc-compare__table
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · procurement__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 proc-compare__table；chat 不写盘
- 下一刀：在 chat/run 上把 proc-compare__table 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### proc-vendor

- 名称：供应商
- 子代理/车道：`lane-procurement`
- 对照：yibiao
- 独有：proc-vendor__eval
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · procurement__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 proc-vendor__eval；chat 不写盘
- 下一刀：在 chat/run 上把 proc-vendor__eval 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `plant` · 车道 `lane-plant`

### equip

- 名称：设备管理
- 子代理/车道：`lane-plant`
- 对照：yibiao
- 独有：equip__ledger
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · plant__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 equip__ledger；chat 不写盘
- 下一刀：在 chat/run 上把 equip__ledger 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### warehouse

- 名称：仓管
- 子代理/车道：`lane-plant`
- 对照：yibiao
- 独有：warehouse__log
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · plant__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 warehouse__log；chat 不写盘
- 下一刀：在 chat/run 上把 warehouse__log 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### pack-ship

- 名称：装箱拼柜
- 子代理/车道：`lane-plant`
- 对照：pack-agent
- 独有：pack-ship__list, pack-ship__plan, pack-ship__export, pack-ship__health
- list：已有 · pack-ship__list
- plan：已有 · pack-ship__plan 投影 solver
- export：已有 · pack-ship__export
- can_fit：已有 · 只抄 solver；断线字面 UNSPECIFIED
- mid50：已有 · 只抄 solver；断线 UNSPECIFIED
- utilization：已有 · 只抄 solver；断线 UNSPECIFIED
- xyz：禁止编造 · 未接通不写坐标
- 下一刀：默认召唤本岗时把最近一次 packing_summary 当 solver 快照抄进 plan/export，仍禁止重算 xyz。

### material-site

- 名称：现场材料
- 子代理/车道：`lane-plant`
- 对照：yibiao
- 独有：material-site__recon
- parse：部分 · 独有 material-site__recon 可抄用户原文，无扫描 PDF
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · plant__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 material-site__recon；chat 不写盘
- 下一刀：在 chat/run 上把 material-site__recon 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `lab` · 车道 `lane-lab`

### lab-mix

- 名称：配合比
- 子代理/车道：`lane-lab`
- 对照：yibiao
- 独有：lab-mix__report
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · lab__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 lab-mix__report；chat 不写盘
- 下一刀：在 chat/run 上把 lab-mix__report 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### lab-sample

- 名称：见证取样
- 子代理/车道：`lane-lab`
- 对照：yibiao
- 独有：lab-sample__list
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · lab__scan_forbidden + 高风险确认句
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 lab-sample__list；chat 不写盘
- 下一刀：在 chat/run 上把 lab-sample__list 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### lab-record

- 名称：试验台账
- 子代理/车道：`lane-lab`
- 对照：yibiao
- 独有：lab-record__ledger
- parse：部分 · 独有 lab-record__ledger 可抄用户原文，无扫描 PDF
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · lab__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 lab-record__ledger；chat 不写盘
- 下一刀：在 chat/run 上把 lab-record__ledger 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `finance` · 车道 `lane-finance`

### finance-book

- 名称：核算
- 子代理/车道：`lane-finance`
- 对照：yibiao
- 独有：finance-book__check
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · finance__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 finance-book__check；chat 不写盘
- 下一刀：税务/资金日历只抄 IRAS 页述标题与 9%；税额 UNSPECIFIED。

### finance-fund

- 名称：资金
- 子代理/车道：`lane-finance`
- 对照：yibiao
- 独有：finance-fund__plan
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · finance-fund__plan 提纲/说明
- qa：已有 · finance__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 finance-fund__plan；chat 不写盘
- 下一刀：税务/资金日历只抄 IRAS 页述标题与 9%；税额 UNSPECIFIED。

### finance-tax

- 名称：税务
- 子代理/车道：`lane-finance`
- 对照：yibiao
- 独有：finance-tax__calendar
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · finance__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 finance-tax__calendar；chat 不写盘
- 下一刀：税务/资金日历只抄 IRAS 页述标题与 9%；税额 UNSPECIFIED。


## 大类 `docs` · 车道 `lane-docs`

### supervision

- 名称：资料监理
- 子代理/车道：`lane-docs`
- 对照：yibiao
- 独有：supervision__reply
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · docs__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 supervision__reply；chat 不写盘
- 下一刀：在 chat/run 上把 supervision__reply 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `hr` · 车道 `lane-hr`

### hr-recruit

- 名称：招聘
- 子代理/车道：`lane-hr`
- 对照：yibiao
- 独有：hr-recruit__brief
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · hr-recruit__brief 提纲/说明
- qa：已有 · hr__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 hr-recruit__brief；chat 不写盘
- 下一刀：在 chat/run 上把 hr-recruit__brief 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### hr-labor

- 名称：劳动关系
- 子代理/车道：`lane-hr`
- 对照：yibiao
- 独有：hr-labor__check
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · hr__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 hr-labor__check；chat 不写盘
- 下一刀：在 chat/run 上把 hr-labor__check 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### hr-train

- 名称：培训
- 子代理/车道：`lane-hr`
- 对照：yibiao
- 独有：hr-train__plan
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · hr-train__plan 提纲/说明
- qa：已有 · hr__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 hr-train__plan；chat 不写盘
- 下一刀：在 chat/run 上把 hr-train__plan 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `admin` · 车道 `lane-admin`

### admin-doc

- 名称：公文印章
- 子代理/车道：`lane-admin`
- 对照：yibiao
- 独有：admin-doc__draft
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · admin-doc__draft 提纲/说明
- qa：已有 · admin__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 admin-doc__draft；chat 不写盘
- 下一刀：在 chat/run 上把 admin-doc__draft 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### admin-office

- 名称：会务后勤
- 子代理/车道：`lane-admin`
- 对照：yibiao
- 独有：admin-office__list
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · admin__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 admin-office__list；chat 不写盘
- 下一刀：在 chat/run 上把 admin-office__list 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `it` · 车道 `lane-it`

### it-ops

- 名称：运维权限
- 子代理/车道：`lane-it`
- 对照：yibiao
- 独有：it-ops__runbook
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · it__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 it-ops__runbook；chat 不写盘
- 下一刀：在 chat/run 上把 it-ops__runbook 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### it-data

- 名称：数据备份
- 子代理/车道：`lane-it`
- 对照：yibiao
- 独有：it-data__backup
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · it__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 it-data__backup；chat 不写盘
- 下一刀：在 chat/run 上把 it-data__backup 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### it-app

- 名称：系统需求
- 子代理/车道：`lane-it`
- 对照：yibiao
- 独有：it-app__srs
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · it__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 it-app__srs；chat 不写盘
- 下一刀：在 chat/run 上把 it-app__srs 的用户栏位写全，缺数 [A001]/UNSPECIFIED。


## 大类 `people` · 车道 `lane-people`

### worker-brief

- 名称：工友白话
- 子代理/车道：`lane-people`
- 对照：yibiao
- 独有：worker-brief__talk
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：已有 · worker-brief__talk 提纲/说明
- qa：已有 · people__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 worker-brief__talk；chat 不写盘
- 下一刀：在 chat/run 上把 worker-brief__talk 的用户栏位写全，缺数 [A001]/UNSPECIFIED。

### pm-daily

- 名称：项目日报
- 子代理/车道：`lane-people`
- 对照：yibiao
- 独有：pm-daily__log
- parse：缺口 · 本岗不解析招标；用户原文进草稿，扫描 PDF 仍拒绝
- outline：部分 · run 出内部提纲骨架，未对照易标目录扩写器
- qa：已有 · people__scan_forbidden
- kb：已有 · 分层 KB + search_kb/read_kb（demo/kb）
- write：已有 · 独有 pm-daily__log；chat 不写盘
- 下一刀：在 chat/run 上把 pm-daily__log 的用户栏位写全，缺数 [A001]/UNSPECIFIED。
