# 物流材料与箱单工作台

入口：`/logistics`。主工作台和工程计算页均有“物流材料”链接。

## 使用流程

1. 上传 Excel、CSV/TSV、数字 PDF、扫描 PDF 或 PNG/JPG。JSON 只接受本工作台的 `civil.logistics.v1` 台账格式。
2. 查看识别行、原文位置和异常，保存为项目。原件按 SHA-256 校验保存，不会被修订覆盖。
3. 在表格编辑，或输入“把 R00001 毛重改为 120 kg”。先查看原值 → 新值，再点击应用。数量、单位、重量范围与尺寸范围分别记录。
4. 对照原件确认当前台账。每次应用修订、撤销或导入都需要重新确认。
5. 选择“已包装箱拼柜”或“裸材料成箱”，填写柜型、柜数上限及现有签认确认句，再调用确定性引擎。
6. 导出台账 Excel/JSON 或完整 ZIP 项目包。ZIP 保存原件、台账、证据和保留的版本；导入创建新 ID 并清除确认状态。

“统一 Agent 对话”链接将主聊天绑定到当前箱单。模型模式和无模型模式共用受限工具；对话检查、汇总和修改建议不保存台账。修改和撤销在物流页单独确认。模型不能提交材料数组、尺寸、路径或代码；成功回复来自实际工具结果。

同事的清单可另存一个项目，在对照入口选择它。当前按明确材料编号对照，不按相似名称猜匹配；重复编号会标记为需核对。

## 数据边界

- 缺失字段保持 `UNSPECIFIED`，不默认数量为 1、不按品名猜尺寸、不返回演示材料。
- 箱数、货物数量、每箱数量分别保存；不同计量单位分别汇总。
- 净重、毛重及每箱/单件/整行范围分别保存。明确一致的同箱字段在汇总时避免重复；不能证明箱件关联时不能直接拼柜。
- 已包装输入使用包装外廓和每箱毛重；裸材料输入要求单件尺寸、单件净重和件数，不把已包装材料重新成箱。
- 未明确堆叠或旋转许可时采用不堆叠、不旋转，并独立检查引擎返回的箱位和箱件数量。
- 合成样例标注“合成”，只用于流程测试。当前没有真实供应商箱单的字段准确率报告。
- 扫描 OCR 的复杂合并单元格首版明确报告未处理；没有明确表格结构的文字 PDF 不按散落数字猜行。
- OCR 关闭自动旋转与图像扭曲修正，坐标对应上传原图；倒置或严重歪斜的单据需先调整方向。
- 项目最多保留 20 个历史版本。撤销另存新版本，历史仍可查看；已被旧实现删除的历史不能恢复。
- 普通 Excel 公式不执行；无缓存结果、复杂合并表头或范围不明的单元格会列入核对。
- 内部几何装载草稿不能作为订舱、系固或 VGM 签认结论。

## 本地依赖

主工作台环境安装：

```powershell
python -m pip install -r requirements-logistics.txt
```

OCR 使用独立环境，避免影响 CAD 和工程计算依赖。以下命令在仓库根目录执行：

```powershell
python -m venv .venv-logistics
.venv-logistics/Scripts/python.exe -m pip install -r requirements-logistics-ocr.txt
.venv-logistics/Scripts/python.exe scripts/prepare_logistics_ocr.py
```

预热仅获取官方模型，不读取或上传用户单据。预热成功后在 `output/logistics-ocr-ready.json` 记录解释器、版本和模型缓存；该文件及模型、虚拟环境不提交 Git。处理单据时使用本地子进程，不调用云 OCR，模型未就绪会明确失败。

Linux/macOS 的环境解释器为 `.venv-logistics/bin/python`。自定义解释器可设置 `CIVIL_LOGISTICS_OCR_PYTHON`；可选 `CIVIL_LOGISTICS_OCR_CONFIG` 指向本地 JSON，只允许 `*_model_name`、`*_model_dir` 配置。模型变更后重新预热。

当前固定 PaddleOCR 3.7.0、PaddlePaddle 3.3.1、pdfplumber 0.11.9。PaddleOCR/PaddlePaddle 代码 Apache-2.0，pdfplumber/openpyxl 代码 MIT；模型保留其各自来源与许可。完整开源比较见 [调研与接入方案](logistics-packing-list-agent-research.md)。

## 接口与限制

API 根为 `/api/logistics`：

- `GET capabilities`：文件类型、OCR 就绪状态、大小限制。
- `POST upload`：multipart 原件，返回草稿 ID、台账和检查结果。
- `GET/POST projects`、`GET projects/{id}?version=…`：保存与恢复。
- `POST projects/{id}/propose`、`conversation`：手工/对话建议。
- `GET proposals/{id}`、`POST proposals/{id}/apply`：审阅与应用。
- `POST projects/{id}/confirm`、`undo`、`pack`、`export`。
- `GET projects/{id}/source`、`POST import`：原件与项目包。

所有修订带 `expected_revision`；旧版本冲突返回 409。API 使用现有本地请求、访问口令、沙箱及导出检查。原件最大 8 MiB，项目包最大 24 MiB；解析最多 40 页、5000 行。OCR 单次 240 秒，装箱计算单次 60 秒，并可取消子进程。主聊天和页内操作都绑定项目及版本，取消不发布后续修改建议。

离线检查：`npm run check` 中的 `logistics-intake`、`logistics-workbench`、`logistics-chat`、`logistics-ui`。已安装并预热 OCR 时，可另运行 `python scripts/smoke_logistics_ocr.py`；它使用明确标注的合成图片，不能替代真实箱单验收。

2026-09-21 本机验收：真实 PaddleOCR 推理读取两行合成扫描箱单，箱号、材料编号、箱数、件数、净重、毛重与生成图一致，保存逐格坐标，未知尺寸保持未知。一次 CPU 解析约 83 秒，仅为本机单样例测量。网页上传相同图片也返回 5 箱、22 件、净重 440 kg、毛重 490 kg；这些是测试数据，不是业务记录。浏览器另验证改参提案、应用、撤销和刷新恢复。
