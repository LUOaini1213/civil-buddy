# 模型算量 · 联网口径（2026-08-14 现场）

岗位对应：过滤规则和模型量。不编综合单价，不宣称可结算。无模型不编「准确量」。

辖区：默认新加坡工地（SG）。用户 pack 另指定则从其指定。禁止静默混用 CN / SG。本页不是规范全文库。

## CN

- 模型几何量 ≠ 清单量。清单/定额扣洞、重叠、分类以用户点名的计算规范为准。
- 计价标准只写全名、且仅本栏：《建设工程工程量清单计价标准》GB/T 50500-2024（住建部公告 2024 年第 212 号；公开转载 2025-09-01 实施）；废止本《建设工程工程量清单计价规范》GB 50500-2013。用户合同若仍绑 2013 版，按合同写。本轮 `mohurd.gov.cn` DNS 未解析，不编造部站深链。
- 交付细度影响能不能量：只点《建筑信息模型设计交付标准》GB/T 51301-2018，不摘正文。
- 施工应用可点《建筑信息模型施工应用标准》GB/T 51235-2017。钢筋/土方/脚手架未按计算规则建模则标「不能从本模型出」。

## SG

- IFC+SG 为报审数据（**SGPset** 监管属性），不是工料清单。提量若走 IFC，须另写用了哪版 schema、哪些数量集；缺属性标「模型未赋」。https://info.corenet.gov.sg/ifc-sg/start-here/WhatIsIFCSG
- ISO 16739-1:2024 页述含 property and quantity set definitions。buildingSMART 公开墙例 **Qto_WallBaseQuantities**：Length / Width / Height、Gross/Net FootPrint Area、Gross/Net Side Area、Gross/Net Volume、Gross/Net Weight。页述：毛侧面积/毛体积不计洞，净量扣洞。只当公开数量集名称，不编 GUID、不编单价。https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/Qto_WallBaseQuantities.htm
- 导出可能丢属性或乱单位。buildingSMART：IFC **4.3.2.0** = ISO 16739-1:2024；推荐交换用 .ifc（SPFF）。https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/
- CORENET X / BIM e-submission 模型是协调与审批用，不是验工收方。强制网关见 URA DC25-07，不把报审模型量写成进度产值。https://www.ura.gov.sg/guidelines/circulars/dc25-07/
- COP「Level of Details」只要嵌了 IFC+SG 数据与最小尺寸即可（例：树可用棒棒糖体）。不得据此发明可计量档。https://info.corenet.gov.sg/regulatory-process/corenet-x-code-of-practice
- BCA Building Plan submission（页更 **2026-07-06**）：≥30,000 m² 新项目走 CORENET X。https://www1.bca.gov.sg/safety-and-standards/applications-and-licenses/building-plan-submission/
- 公共工程若用 PSSCOC，计量条款名见 **Clause 21 Measurement**（官方 PDF 目录名）；Option Module A Bills of Quantities。不把 IFC Qto_* 写成 PSSCOC 收方。https://www1.bca.gov.sg/growth-and-transformation/procurement/standard-contract-forms/public-sector-standard-conditions-of-contract-psscoc/

## 国际名称（CN/SG 均可点）

- ISO 19650-1/2 管信息需求与交付期交换（EIR / 交换），不管国内清单扣减。https://www.iso.org/standard/68078.html
- 一模多算：实物几何、清单规则、消耗量并排必须标口径名，禁止合成一个「工程量」。

## 通用 禁令

- 不编综合单价、市场价、可直接结算。SG 不算 GB 清单；CN 不把 Qto_* 当定额规则。无过滤规则不报准确量。单价交造价。不把模型量写成报审通过或可结算。不写「可以开工」。
