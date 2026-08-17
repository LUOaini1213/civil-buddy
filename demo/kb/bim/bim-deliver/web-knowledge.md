# 模型交付 · 联网口径（2026-08-14 现场）

岗位对应：BIM 交付清单——阶段、细度、格式、命名、拆分、缺项。不编软件授权，不宣称已具备报审或竣工移交条件。

辖区：默认新加坡工地（SG）。用户 pack 另指定则从其指定。禁止静默混用 CN / SG。本页不是规范全文库。

## CN

- 只写全名：《建筑信息模型应用统一标准》GB/T 51212-2016；《建筑信息模型分类和编码标准》GB/T 51269-2017；《建筑信息模型设计交付标准》GB/T 51301-2018（常用项目级/功能级/构件级/零件级）；《建筑信息模型施工应用标准》GB/T 51235-2017；《建筑信息模型存储标准》GB/T 51447-2021；《建筑工程设计信息模型制图标准》JGJ/T 448-2018。
- 地方手册（如上海施工图 BIM 交付要求）仅当用户点名。条款未抽原文 → UNSPECIFIED。

## SG

- 现行报审交付：CORENET X + IFC+SG（IFC + **SGPset**），不是只交原位 RVT。COP **3.1 Edition（2025-12）** 本轮仍为现行本：https://info.corenet.gov.sg/regulatory-process/corenet-x-code-of-practice
- IFC+SG 入门（页述 IFC4 + SGPsets，供 CORENET X 审阅，不是裸 IFC）：https://info.corenet.gov.sg/ifc-sg/start-here/WhatIsIFCSG
- 旧称 BIM e-submission：2016 起尤其 GFA>5,000 sqm 已收 BIM；须 **SVY21 + SHD**。https://www.ura.gov.sg/guidelines/best-practices/geo-referencing-bim-submissions/
- 强制切换：DC25-07（2025-09-10）曾写 2026-10-01 全部新项目不论 GFA。已被 APPBCA-2026-12 / URA/PB/2026/08-DCG（2026-07-23）收窄：2025-10-01 起 GFA≥30,000 m² 已强制；2026-10-01 起仅新项目 GFA≥5,000 m² 强制走 Gateway Processes；GFA<5,000 m² 可继续 CORENET 2.0。https://info.corenet.gov.sg/docs/default-source/bca-circulars/circular-for-updates-to-corenet-x-implementation-plan.pdf?sfvrsn=d8a19259_1
- BCA Building Plan submission（页更 **2026-07-06**）：截至该页 ≥30,000 新项目走 CORENET X，其余仍可 CORENET 2.0。https://www1.bca.gov.sg/safety-and-standards/applications-and-licenses/building-plan-submission/
- 网关交什么以该网关页为准（Design / Construction / Completion；Piling 可选；简单类型可走 DSP）。清单不得自编「已满足全部局要求」。https://info.corenet.gov.sg/regulatory-process/by-key-gateways
- COP「Level of Details」：嵌数据 + 最小尺寸即可，不要求仿真形体。禁止把 AIA/BIM Forum LOD 100–500 写成 CORENET 强制档。
- 合同向交付另有：**Model Content Requirements V2.0 Mar 2026**、BIM Handover Technical Guide（BCA 质量模型页更 **2026-08-07**）。https://www1.bca.gov.sg/growth-and-transformation/productivity/idd-integrated-digital-delivery/ensuring-quality-bim-models/
- FI（电梯/扶梯等）另有 BCA **BIM Guide v3.0（2024-09-26）**；FI 专页更 **2026-03-14**。该页写 FI 纳入协调 BIM，并称 GFA>5,000 m² 项目须交 BIM。不是全专业 LOD 表。https://www1.bca.gov.sg/safety-and-standards/lifts-escalators-and-mechanised-car-parking-systems/building-information-modelling-bim/
- 建模准备：坐标、层名、Block、唯一 GUID、文件体量、报审前 clash。https://info.corenet.gov.sg/ifc-sg/modelling---authoring/GeneralModellingPractices

## 国际名称（CN/SG 均可点，勿当强制 LOD）

- ISO 19650-1 Concepts and principles；-2 Delivery phase of the assets；-3 Operational phase；-4 Information exchange；-5 Security-minded approach（https://www.iso.org/standard/74206.html）；-6 Health and safety information。用语：EIR / BEP / CDE / LOIN（几何、字母数字、文档分开要）。https://www.iso.org/sectors/building-construction/building-information-modelling
- ISO 16739-1:2024 IFC 数据模式。https://www.iso.org/standard/84123.html
- BIM Forum **2025 LOD Specification**（2025-12-31）：自述不规定某阶段必须到哪一档，由项目组自定，配合 BEP。禁止写「必须交 LOD 300」。https://bimforum.org/resource/lod-level-of-development-lod-specification/

## 通用 禁令

- 不把 LOD 数字当成可以施工/结算/报审通过。SG 不套 GB/T 细度级当 IFC+SG 门槛；CN 不写「已按 CORENET 交齐」。无业主 EIR/合同则矩阵待填。
- 不宣称已具备报审或竣工移交条件。不写「可以开工」。DUAL 必须分栏。
