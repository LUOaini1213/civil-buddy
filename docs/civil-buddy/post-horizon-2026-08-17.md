# 66 岗对照易标 / pack-agent 的长程规划（2026-08-17）

> 已做/未做以全量规划书 [product-plan.md](product-plan.md) §7 / §15 为准。本文保留每岗「下一刀」原文；bid 三岗 handoff 与 construction 十一章 md **已经落地**，勿再当缺口。

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
- 下一刀：expert_turn 把 run_tender_pipeline 的 handoff 另存 tender.handoff.json，供后岗读；本岗 submit_blocked 仍 true。

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
- 下一刀：expert_turn 专用 gaps：读 handoff 或重跑 pipeline，落盘三列已响应/未响应/招标未提供正文，不代判废标。

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
- 下一刀：expert_turn 读 scoring_points 调 build_tech_outline_from_handoff；无评分点不套上个项目目录。


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
- 下一刀：architecture__memo 按 outline.md 一次写 10 章，面积/疏散 [A001]，文末只贴已核官方标题。

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
- 下一刀：structure__calc_outline 按大纲落十章 + qa 自检表；无地勘不定承载力。

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
- 下一刀：geotech__brief 只抄用户 SI 分层/孔号；未出现的 c/φ、水位写未在原文检出。

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
- 下一刀：plumbing__memo 按大纲落十章；管径/水压只抄用户资料，消防水量交消防岗。

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
- 下一刀：hvac__memo 按大纲扩写；无负荷则主机/风管/排烟量 [A001]。

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
- 下一刀：electrical__memo 落供配电/应急/防雷/消防电源；弱电整节交 intel-weak。

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
- 下一刀：fire-protect__brief 按大纲写 11 章专篇目录；无来源限值，不替代审图。

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
- 下一刀：steel__memo 按大纲落体系/材料/连接；无跨度荷载不写梁高螺栓焊缝。

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
- 下一刀：官方标题表锁定 Greenery 5.1；landscape__memo 只准抄表，胸径无苗木表则待填。

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
- 下一刀：interior__schedule 收成房间×饰面界面表；无样板不编品牌。

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
- 下一刀：facade__brief 按大纲落体系；无风压不写厚度；SG 稿禁 38 号/JGJ。

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
- 下一刀：标题表锁定 COPIF 2018；2026 征求意见标非已生效；点数品牌待填。

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
- 下一刀：成稿强制 SG/CN 分栏；SG 只抄 HS/SS 与 TRHS/THSS 标题，不写墙厚门樘。

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
- 下一刀：三本 PUB COP 带生效日；Coastal Protection 必须同时写 2028 生效。

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
- 下一刀：CN/SG 分栏标题表；SG 稿无 JTS；无水位波浪不写桩长。

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
- 下一刀：municipal__memo 灌 principles.md；只抄 CDC A3 / SDRE Rev I 标题。

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
- 下一刀：bridge__outline 比选不锁定最优；无跨径则梁高钢束失败。

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
- 下一刀：按用户工法分节；无地质不写支护参数；防火标题公路/轨交/房建不混。

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
- 下一刀：traffic__skeleton 先选建成后 TIA 或施工导改；无流量不写饱和度。

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
- 下一刀：纪要收成表；文首只抄 APPBCA-2026-12（GFA≥5000 强制 Gateway）。


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
- 下一刀：bim-coord__clash 按 outline 出碰撞表（硬/间隙/留洞/4D），无模型整表待填。

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
- 下一刀：bim-qto__rules 把过滤说明拆成行表，工程量单价列固定 TBD。不接 IFC 真抽量。

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
- 下一刀：bim-deliver__lod 一次写出坐标系/拆分/命名/LOD 表头，不宣称报审。


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
- 下一刀：plan-master__network 固定 WBS|紧前|里程碑待填|关键线路=待计算。

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
- 下一刀：plan-lookahead__week 出四周表；制约未清不得写入本周承诺。

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
- 下一刀：plan-resource__peak 拆劳动力|机具|材料三表，数量待填。


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
- 下一刀：run_expert_steps 在 scheme_draft 之后调用 fill_scheme_docx，不再跳过；仍是讨论提纲。

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
- 下一刀：重写 judge-card.md 默认 SG WSH/PTW + 信息不足；37 号令只放 CN 栏。

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
- 下一刀：已做 T030。survey__record 只抄已给点号/坐标；都无则表头+[A001]。

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
- 下一刀：已做 T030。dispatch__daily 按 outline 十一章落表头；敏感作业只列名，判定交 method-hazard。


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
- 下一刀：safety-brief__talk 按 outline 写全 11 栏；毫米/电话 [A001]；确认句后才写盘。

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
- 下一刀：quality__lot 出主控|一般|隐蔽三表，结果=未检；写盘后 hse__scan_forbidden。

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
- 下一刀：env__list 拆扬尘/弃土/污水/夜间/市容五行，限值 UNSPECIFIED。

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
- 下一刀：emergency__plan 出综合目录+用户点名专项+演练表头，电话医院待填。


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
- 下一刀：cost__takeoff 按行 parse 清单成规则|量待填|单价 TBD，不编综合单价。

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
- 下一刀：已做 T031 variation。variation__form 先判定文种再出事实|依据|签认空栏；无变更编号则依据待填。

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
- 下一刀：已做 T031 claim。claim__notice 出意向栏+证据行+条款原文待贴；工期金额 TBD。

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
- 下一刀：subcontract__sheet 按行 parse 细目；无总包/业主确认不编金额。

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
- 下一刀：interim__measure 出开累/本期/监理审/业主核空表；无确认不编应付合价。


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
- 下一刀：proc-plan__schedule 先分甲供/甲指/自采再列表，提前期 UNSPECIFIED。

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
- 下一刀：proc-compare__table 一行一家多列；定商标待制度定；写盘后 scan_forbidden。

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
- 下一刀：proc-vendor__eval 出准入|考察|短名单，分数/结论待核，禁止中标结论。


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
- 下一刀：expert_turn 用 equip__ledger 写出与 Rust 同表头台账，只抄用户设备名与已给证件。

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
- 下一刀：warehouse__log 按行 parse 收发原文；有数只抄、无数 TBD；无盘点不编盈亏。

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
- 下一刀：sidecar/packing_summary 快照抄进 pack-ship__plan/export；先 health；无则四字段字面 UNSPECIFIED；禁止重算 xyz。

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
- 下一刀：material-site__recon 按行 parse 应耗/领料/盘点；算不出节超则 TBD。


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
- 下一刀：lab-mix__report 四层目录；无试验数据则施工配比整节待填。

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
- 下一刀：lab-sample__list 出类别|部位|见证人空|升级路径；组数 [A001]。

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
- 下一刀：lab-record__ledger 加报告编号待核|仪器检定|结论待填。


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
- 下一刀：finance-book__check 出报销勾选+科目对照+对账缺口，金额 [A001]。

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
- 下一刀：finance-fund__plan 出收入/支出窗口，金额 TBD，不当付款指令。

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
- 下一刀：finance-tax__calendar 加税种|节点|资料是否齐全；税率空白，只可抄 IRAS 页述 9%。


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
- 下一刀：supervision__reply：来文复述|拟办|证据目录；暂停/复工只出目录，不写复工许可。


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
- 下一刀：hr-recruit__brief 出职责|任职|面试问法；薪资仅当用户给数才抄。

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
- 下一刀：hr-labor__check 按合同类型分表+必备条款对照；补偿 [A001]。

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
- 下一刀：hr-train__plan 出公司/项目/班组三层课题表+签到空栏。


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
- 下一刀：admin-doc__draft 按文种套请示/纪要/用印三套栏，禁止代用印。

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
- 下一刀：admin-office__list 出场地|议程|与会|资料目录，决定栏留空。


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
- 下一刀：it-ops__runbook 出系统|角色|升级路径|联系人待填，禁止写密钥。

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
- 下一刀：it-data__backup 按系统行出 RPO/RTO/介质/演练空，禁止编小时数。

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
- 下一刀：it-app__srs 按行 parse 需求笔记成角色|场景|验收待填，禁止接口地址。


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
- 下一刀：worker-brief__talk 按 script.md 写三段口播；无尺寸不报毫米。

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
- 下一刀：pm-daily__log 出天气待填|部位|形象（禁编百分比）|出勤待填。
