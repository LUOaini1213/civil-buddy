# GitHub 开源轮子评估 · 2026-08-17

现场：GitHub HTML README + `api.github.com` 星标/协议/是否归档。对照 Civil Buddy：先理解再聊或跑、65 岗独有工具、HITL、不编条款/单价/xyz。

## 结论

没有「土木企业工作台」整仓可换的轮子。

| 用法 | 仓库 | 今天 API |
|------|------|----------|
| 值得当**解析工具**接（扫描招标 PDF） | [opendatalab/MinerU](https://github.com/opendatalab/MinerU) | ★77,736 · 自拟 Apache 系许可证 · 2026-08-16 仍推 |
| 值得对照**投标产品**，不能并进本仓 | [FB208/OpenBidKit_Yibiao](https://github.com/FB208/OpenBidKit_Yibiao) | ★2,362 · **AGPL-3.0** · Electron 桌面 |
| 值得对照 **RFP 问答**，不是施工草稿 | [run-llama/auto_rfp](https://github.com/run-llama/auto_rfp) | ★215 · MIT · OpenAI+LlamaCloud |
| 装箱数学兜底（无 packing-agent 时） | [enzoruiz/3dbinpacking](https://github.com/enzoruiz/3dbinpacking) (py3dbp) | ★458 · MIT · 2023-12 后未推 |
| 施工自动化**菜谱**，不是运行时 | [DDC 221 skills](https://github.com/datadrivenconstruction/DDC_Skills_for_AI_Agents_in_Construction) | ★276 · MIT · SKILL.md 给 Claude Code |
| 不要当轮子 | good-autobid、微软 RFP 加速器（已归档）、US PE 57 岗提示词 | 见下 |

不认营销数字：「中标率 +40%」「3 分钟出标」「一次 20 万字」。

## 投标 / RFP

| 仓库 | 现场看到 | 对 Civil Buddy |
|------|----------|----------------|
| **OpenBidKit 易标** | 解析 / 提纲 / 写标 / 知识库 / 查重入口 / 废标检查。本地解析 + MinerU。Pi Agent。AGPL-3.0：改了或网络提供服务必须开源。 | 工序已对齐。**不能把他们的 Electron 代码并进本仓**（会传染 AGPL）。可继续对照模块，不抄实现。 |
| **good-autobid** | 需求→大纲→终稿；3 次提交；2025-03 停更；无 LICENSE；自称 20 万字。 | 就是提示词流水线。不要接。 |
| **microsoft/…-rfp-…** | 2026-03-20 **归档**。Copilot Studio + Teams + SharePoint。README 写明 *not production ready*。★57。 | 微软栈，不是本机工作台。 |
| **run-llama/auto_rfp** | 抽问题 + 用知识库答。Next.js / Supabase / GPT-4o。MIT。最后推送 2026-01。 | 适合「历史标书问答」。没有危大 HITL、辖区、空价表。 |

## 土木专家岗

| 仓库 | 现场看到 | 对 Civil Buddy |
|------|----------|----------------|
| **DDC 221 skills** | `SKILL.md` 教助手写 ETL / IFC→Excel / 日报。工具在配套仓（CWICR、cad2data）。 | 可偷师「IFC 抽量、日报自动化」**题目**，不要灌 221 份 skill 进工作台。 |
| **asv-digital/agents-us-engineers** | 57 个 Claude 子代理 md。ACI / NEC / OSHA。★1，无 LICENSE，1 次提交。 | 美国 PE 口径。和本仓「不编条款、SG/CN」相反。不要装。 |

Tencent `workbuddy-bench` 是评测集，不是工作搭子产品。

## 解析 / 装箱

| 仓库 | 现场看到 | 对 Civil Buddy |
|------|----------|----------------|
| **MinerU** | PDF/DOCX/PPTX/XLSX → Markdown/JSON。3.1 起不再 AGPL，自拟 Apache 系（仍要读 `LICENSE.md` 附加条款）。 | **最值得接的轮子**：扫描招标、图纸说明。重（模型、GPU/内存）。先可选、后默认。 |
| **py3dbp** | 3D 装箱启发式。MIT。两年未推。 | packing-agent 断线时算柜，仍禁止模型手写 xyz。 |
| **xflp** 等 | Java 装车启发式。 | 同左；本仓装箱岗已走 HTTP 工具。 |

## 和本仓比

Civil Buddy 已有、别人没有成套的：65 岗独有写盘、chat/run/both、确认门、trace、SG 官方标题不编条款。

别人有、本仓弱的：扫描 PDF（MinerU）、标书查重（易标有入口）、一键 Word（易标桌面）、IFC 真抽量（DDC+ifcopenshell）。

## 第二轮深挖（同日）

| 仓库 | API 现场 | 协议 | 怎么用 |
|------|----------|------|--------|
| [docling-project/docling](https://github.com/docling-project/docling) | ★64,839 · 2026-08-15 仍推 | **MIT** | CPU 友好的 PDF/DOCX/PPTX。本仓已接可选 CLI。 |
| [datalab-to/marker](https://github.com/datalab-to/marker) | ★38,782 | Apache-2.0 | 快、多栏好。可选第三引擎。 |
| [IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) | ★2,707 | LGPL-3.0 | BIM 真抽量。未接（bim-qto 仍是口径表）。 |

## 已接到本仓（2026-08-17）

`workbench/src/parse.rs`：`CIVIL_PARSE=auto` 时扫描件试 MinerU → Docling → Marker；文字层够用仍走内置。附件 meta 带 `parse`。health 暴露 `parse.mineru/docling/marker`。

本机当时 **未安装** 任一 CLI（`python -c shutil.which` 均为 None）。装好后重启工作台即可，不必改代码。

## 建议（仍不做）

1. **不要** fork 易标进本仓（AGPL）。
2. **不要** 并 57 个美国 PE 提示词。
3. 装箱仍优先 packing-agent；断线再考虑 py3dbp。
4. IFC 抽量另开一轮，不要和招标解析绑在一起。
