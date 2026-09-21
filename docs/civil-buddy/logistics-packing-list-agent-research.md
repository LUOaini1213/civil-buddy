# 自动读箱单的物流材料 Agent：选型与接入方案

核查日期：2026-09-21。本文件保留接入前的调研和代码审查；当前实现、安装及边界见 [物流材料与箱单工作台](logistics-workbench.md)。真实业务箱单验收仍待进行。

## 结论

建议在现有工作台增加“箱单识别与材料核对”入口，复用原件存储、材料校验和装箱工具。首选组合是原生 Excel/CSV 读取 + PaddleOCR PP-StructureV3 的 PDF/图片结构识别 + 自建箱单台账。Docling 可作为统一文档解析的替代方案；首版不同时部署多套完整解析流水线。

原件 → 表格与字段提取 → 箱/材料分层台账 → 原文对照及差异核查 → 用户确认 → 材料汇总/导出/装箱计算。

## 官方开源来源

| 项目 | 可复用部分 | 许可及使用边界 | 本项目建议 |
| --- | --- | --- | --- |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | PDF/图片结构识别；PP-StructureV3 提供表格单元格及文字坐标；中英文 OCR | 仓库 Apache-2.0；不等于已经具备物流字段语义 | 首选扫描箱单解析候选，用坐标支持原文定位 |
| [Docling](https://github.com/docling-project/docling) | PDF、Office、图片统一文档结构；OCR、表格、JSON 导出；支持本地 Windows 运行 | 代码 MIT；各模型另有许可 | 需要统一多种工程单据时的替代流水线 |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) + [RapidTable](https://github.com/RapidAI/RapidTable) | 文字、坐标、识别分数和表格结构；可用 ONNX Runtime CPU | 主库 Apache-2.0；模型权重单独核对；PDF 渲染和物流字段映射仍需宿主实现 | Windows CPU 的备选组合，须验证兼容版本及实际单据表现 |
| [invoice2data](https://github.com/invoice-x/invoice2data) | YAML/JSON 模板、正则及明细行提取；支持 Windows | MIT；以发票为起点，箱单需自定义字段；当前可选 AI 回退并非必需 | 固定供应商格式可优先试用模板提取 |
| [pdfplumber](https://github.com/jsvine/pdfplumber) / [Camelot](https://github.com/camelot-dev/camelot) | 电子 PDF 文字、坐标、表格或 DataFrame | 主库 MIT；pdfplumber 无内置 OCR；Camelot 当前提供可选 ML/OCR 路线，传统解析策略仍依赖文本层 | 数字 PDF 的解析候选；解析器评分不是物流字段准确率 |
| [gmft](https://github.com/conjuncts/gmft) | 复杂表格检测、结构还原、DataFrame 和裁剪图 | 主库 MIT；无内置 OCR，模型及可选依赖另核许可；基础模型偏论文表格 | 复杂电子 PDF 备选，须先证明优于较简单方案 |
| [Docpick](https://github.com/ArkNill/docpick) | OCR + 本地模型 + 结构化字段校验；贸易单据及跨单据校核示例 | Apache-2.0；现有内置 schema 未包含专用 packing_list，仍需自建；未验证本机模型运行 | 借鉴业务结构及校核方式，不作为现成完整箱单 Agent |
| [MinerU](https://github.com/opendatalab/MinerU) | 文档结构及表格解析 | 当前 [LICENSE](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md) 为 Apache-2.0 附加条款，不能按纯 Apache-2.0 记录；具体版本需复核 | 复杂版面备选，首版暂不引入 |

另查到 [shipment-doc-extractor](https://github.com/Abdelrahmanmemara/shipment-doc-extractor)：题目与箱单很接近，但当前依赖 Claude API，仓库未见明确 LICENSE，因此不列入直接复制集成方案。公开 README 的速度或节省工时声明不作为本项目验收证据。

以上工具的官方功能说明不代表已经在用户箱单上达到可接受准确率。选型须固定版本、模型与依赖，并保留许可证和来源记录。

## 当前仓库可复用部分与缺口

代码位置均相对于仓库根目录：

- `demo/uploads.py`：有大小限制、附件 ID 和原件存储；Excel 会转换成表格文本，PDF 用 pypdf 提取文字。扫描 PDF 尚无 OCR，图片不在当前上传白名单。
- `packing_assistant/document_text.py`：CSV、DOCX 表格文本化能力可复用，但不能替代单元格及页框来源记录。
- `packing_assistant/tools/table_mapper.py`：可复用表头词典、单位换算和数量检查；现有模型把箱数/件数映射到同一 quantity，净重/毛重竞争同一 weight_kg，不能直接作为新台账。
- `packing_assistant/tools/packing_list_parser.py`：存在按品名、重量、包装估算尺寸的旧逻辑。自动读单路径应保留尺寸未知，不能把估算值当原单尺寸。
- `packing_assistant/agents/material_parser.py`：旧路径包含解析失败后的演示材料回退；新路径应明确报告空解析或缺项，不继承演示回退。
- `packing_assistant/tools/pack_ship_solve.py`：已有材料检查、装箱调用和结果守恒检查；但守恒只说明输入与输出一致，不能证明识别值与原件一致。当前尺寸闸门也未阻断所有 `dims_estimated` 情况。
- `packing_assistant/tools/pack_ship_mcp.py`：可复用读取与计算分离思路；新工具应引用已保存的台账 ID 和版本，不接受模型自行编写的材料数值。

只读合成解析探针已复现：同一行同时含箱数 2、件数 10、每箱 5、毛重 110 kg 时，改变列顺序会得到 quantity=2 或 10，并分别生成 total_weight_kg=220 或 1100，未提示数量语义冲突。该探针说明旧字段模型不适合直接接自动箱单，并非真实箱单识别准确率测试。

## 箱单台账与来源

建立“单据 → 包装箱/托盘 → 箱内材料”的层级，不把一个箱里的多条材料当成多个箱。

| 层级 | 主要字段 |
| --- | --- |
| 单据 | 附件 ID、原件哈希、供应商/订单号（有原文才填）、版本、解析器及模型版本 |
| 包装 | 箱号/托盘号、包装类型、包装数量、外尺寸与单位、净重/毛重、重量适用范围（单箱或合计） |
| 材料 | 材料编号、名称、规格、件数及计量单位、每箱数量、关联包装 ID |
| 字段证据 | 原始值、单位、页码及框坐标，或 sheet/行/列；标准化值；转换/计算依据；人工修订记录 |

未明确的字段保留 `UNSPECIFIED`。原文值、换算值、计算值分开记录。OCR 分数仅用于排序复核，不能当成业务正确率。

必须区分：材料尺寸与箱外尺寸、箱数与件数、每箱数量与总数量、净重与毛重、单件/单箱/整行/整单重量。相同箱号可以合法对应多行材料，不能直接按箱号去重；重复出现的箱重也不能逐材料行累加。

## 用户操作与受限工具

页面左侧显示原单，中间显示可编辑台账，右侧显示差异与对话；点击数值定位原文。先确认字段映射及异常，再生成计算输入。

拟议工具：读取已有附件、提议字段映射、校核台账、按已有材料 ID 汇总、提出修订、应用用户确认的修订、撤销、导出、调用装箱工具。修订显示原值 → 新值，绑定台账版本；取消后不继续执行。模型负责选操作及解释差异，程序负责数量、单位和计算。

示例指令：

- “按箱号汇总铝板，检查总件数和毛重是否对得上。”
- “把箱单和采购清单对比，列出缺件、超发和编号不一致的材料。”
- “列出缺箱外尺寸的箱，先导出待补清单。”
- “只把已确认的包装箱送入拼柜计算。”

“裸材料待成箱”和“已包装箱待拼柜”必须明确选择，不能将包装箱重新当裸材料装箱。导出计算成果继续沿用既有签认与工具结果检查；识别完成不等于可以发货。

## 交付顺序与验收

1. 先修台账语义：分离箱/件、净/毛重和重量范围，移除新路径的估算及演示回退；原生 Excel/CSV 支持来源定位。
2. 接 PDF/图片解析适配器，优先验证 PP-StructureV3；支持页码/坐标、旋转扫描页、跨页续表、合并单元格和重复表头。
3. 接核对页面、对话受限工具、撤销及版本冲突保护；确认后复用现有装箱工具。
4. 保存原件、台账、证据与修订历史；导出 Excel/JSON 和可重开的项目包，导入新副本并重置确认状态。

验收使用经授权的真实箱单及人工核对结果，覆盖不同供应商版式、原生 Excel、数字 PDF、扫描 PDF/照片。逐项检查箱号、材料编号、数量及单位、净毛重及范围、尺寸及单位的精确匹配，以及漏行、重复行、合计差异和来源定位。合成测试补充混合箱、跨页、损坏文件、单位不明、公式无缓存、取消与版本冲突，不替代真实单据验收。

调研阶段没有安装依赖或上传私人箱单。后续实现的验证记录与运行方式见工作台说明；开源功能介绍和合成测试均不能替代真实业务单据准确率验证。
