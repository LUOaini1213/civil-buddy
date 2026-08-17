# 模型协调 · 联网口径（2026-08-14 现场）

岗位对应：碰撞/协调纪要。不是零碰撞证明，不是开工令。无合成模型不编点数。

辖区：默认新加坡工地（SG）。用户 pack 另指定则从其指定。禁止静默混用 CN / SG。本页不是规范全文库。

## CN

- 施工阶段碰撞可点名《建筑信息模型施工应用标准》GB/T 51235-2017，不摘条文。
- 交付细度影响能不能查：只点《建筑信息模型设计交付标准》GB/T 51301-2018。国内细度用语是项目级/功能级/构件级/零件级，不要偷偷换成 LOD 数字。

## SG

- CORENET X Code of Practice **3.1 Edition（2025-12）**：Federated Model 定义为多专业合成模型，平面 **SVY21（EPSG:3414）**、高程 **SHD**；未对齐先停碰撞。COP 不替代各局 Handbook / Circular / Act。https://info.corenet.gov.sg/regulatory-process/corenet-x-code-of-practice
- 报审前查碰撞是 CORENET X General Modelling Practices 的正式条目（页题 **Check clashes before submission**），不是本岗发明。https://info.corenet.gov.sg/ifc-sg/modelling---authoring/GeneralModellingPractices ；专页 https://info.corenet.gov.sg/ifc-sg/modelling---authoring/GeneralModellingPractices/check-clashes
- 同组建模准备：坐标与 federation 对齐、层名、Block、唯一 GUID、文件体量。未对齐不跑点数。
- IFC+SG 结构：IfcSite / IfcBuilding / IfcBuildingStorey / IfcSpace；属性用标准 Pset + **SGPset**。合成前先核空间树与坐标。https://info.corenet.gov.sg/ifc-sg/requirements---submission/ifcsg-data-structure
- URA：正确 geo-referencing 才便于多专业协调与放样。https://www.ura.gov.sg/guidelines/best-practices/geo-referencing-bim-submissions/
- Construction Gateway 页述：细部（房间布局、疏散、通道）须在主体结构开工前协调；本岗纪要不等于 BP/ST 已批，也不等于可以开工。https://info.corenet.gov.sg/regulatory-process/by-key-gateways
- BCA 质量模型页（页更 **2026-08-07**）：无结构化信息则协调失效、返工。https://www1.bca.gov.sg/growth-and-transformation/productivity/idd-integrated-digital-delivery/ensuring-quality-bim-models/
- Building Plan submission（页更 **2026-07-06**）仍写 ≥30,000 m² 新项目走 CORENET X。强制切换以 APPBCA-2026-12 / URA/PB/2026/08-DCG（2026-07-23）为准：2026-10-01 起新项目 GFA≥5,000 m² 强制 Gateway；不把协调纪要写成网关已过。https://info.corenet.gov.sg/docs/default-source/bca-circulars/circular-for-updates-to-corenet-x-implementation-plan.pdf?sfvrsn=d8a19259_1

## 行业通行做法（非法定档）

- 三类：硬碰撞（几何相交）；软碰撞/间隙（未交但检修、保温、通行不够）；工作流/4D（工序占同一工作面）。不要把软件弹出条数当必须改图数。
- 先 QA：共享坐标、单位、轴网、层、命名；再按专业对（结构×机电等）和分区跑测试集；容差与忽略项用户未给则待填。
- 问题单用 buildingSMART **BCF**（openBIM，可 .bcf 或 API），带视点、责任人、Open / In Progress / Closed。https://www.buildingsmart.org/standards/bsi-standards/bim-collaboration-format/
- 先放大几何（结构/主风管/主管/桥架）再支管。关闭一条须改模版本或「专业确认可接受」。

## 通用 禁令

- 禁止写「已清零可施工 / 已过 CORENET 碰撞检查 / 报审通过 / 可以开工」。SG 不套 JGJ 碰撞等级数字；CN 不把 IFC+SG 当国内强制。无模型整表待填。
