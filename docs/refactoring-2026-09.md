# 2026-09 项目重构说明

本次围绕任务执行、工作台交互、业务文件和验证入口修复实际缺陷，继续使用
Civil Buddy 宿主、66 岗技能目录与确定性计算工具。

| 范围 | 问题与修改 | 验证入口 |
|---|---|---|
| 任务运行时 | 同一任务重复提交会并发执行、覆盖状态；统一同步/后台准入，原子保存任务快照，异常释放占用，拒绝未知任务 ID | `scripts/test_runtime_threads.py` |
| 工作台 | 抽离 SSE 读取器；处理 UTF-8 分块、CRLF、断流、取消与读流资源释放；防止旧会话、上传和异步载入响应串入当前任务 | `scripts/test_chat_stream.cjs` |
| 交互与确认 | 增加停止接收、保留部分回答、错误恢复和输入标签；高风险确认完整键入签认句，切换任务清空确认；转义动态 HTML 文本与属性 | 同上及 `demo/tests/test_workbench.py` |
| 知识库 | 修复索引钩子的未定义变量；写入失败不绕过沙箱；编辑/删除后更新索引，索引异常可见 | `scripts/test_business_reliability.py` |
| Office | 抽取共用行写入、保存和路径检查；仅替换约定的 `CB草稿-` 工作表；保护用户表和公式，将草稿内容写为文本；坏附件不阻断其余文件 | 同上及 `scripts/test_office_job.py` |
| 轨迹与结果 | 从真实事件导出完整 JSONL，合并数据库失败时的降级日志，原子替换导出文件；保留协议和工具事件，不受回放条数上限截断；`can_fit=UNSPECIFIED` 不再因字符串真值被记为成功 | `scripts/test_trace_artifacts.py` |
| 开发与 CI | Python 统一检查清单，npm 自动选仓库虚拟环境；禁用测试进程模型 Key、dotenv 和断言优化；超时与失败汇总；CI 安装失败立即报错，加入工作台 HTTP 测试 | `scripts/check_project.py`、`scripts/test_check_project.py` |
| 工作台启动 | `civil app` 校验端口、等待本次子进程真实健康响应；支持 `--no-browser`，失败和退出时回收服务 | `scripts/test_app_launcher.py` |
| 会话服务 | 新 `demo/chat_service.py` 统一路由、准入、资料选择、运行记录与交付物快照；纯问答不重放历史写作意图，离线可调用本地工具；工具失败不再标完成 | `scripts/test_workbench_flow.py` |
| 模型与附件 | 补齐 `/api/llm-config`、`/api/upload`、`/api/attachments`；模型配置仅保存在内存；解析文本 PDF/Office 并限制大小、数量与跨会话访问；模型断流保留部分回答并记录失败 | `scripts/test_workbench_settings.py`、`scripts/test_workbench_uploads.py` |
| 使用流程 | 离线首页、完整岗位目录、按岗位显示处理阶段；刷新恢复最近会话、岗位、选中附件及文书；高风险待确认和工具失败均明确显示 | `scripts/test_chat_stream.cjs`、浏览器实测 |
| 日报与辖区 | 抽取共享辖区路由，未知地区为 `UNSPECIFIED`；日报只抽明确事实，项目/日期/部位/天气/出勤/记事/计划进入对应正文与 Excel | `scripts/test_daily_report_content.py`、`scripts/test_memory_slot.py` |
| 岗位文书模块 | 27 个旧岗位的重复扫描、保存和结果逻辑集中到统一路径；新岗位按需载入纯起草模块；多文件写入失败保留实际已写文件 | `scripts/test_post_dispatch.py` |
| 人力与行政 | 劳动/劳务/派遣分表、三级培训；请示/纪要/用印及会务四表；多人、多合同、多决议不串值，支持表格输入 | `scripts/test_hr_drafts.py`、`scripts/test_admin_drafts.py` |
| IT 与 BIM | 系统权限、备份恢复及需求表；模型问题、算量过滤、LOD 与交付检查表；只抄明确事实，凭据不进 IT 文书，不假装扫描或执行系统操作 | `scripts/test_it_drafts.py`、`scripts/test_bim_drafts.py` |
| 勘察设计 20 岗 | 分为基础设计、机电、专项和基础设施模块；每岗专业章节、多对象参数与缺项表、按地区分开的依据；空列、后置对象编号和未知辖区不串值 | `scripts/test_design_basic_drafts.py`、`test_design_services_drafts.py`、`test_design_specialties_drafts.py`、`test_design_infrastructure_drafts.py` |
| 表格输入闭环 | CSV、Word 与 Excel 表格保留行列；上传及授权工程文件夹均进入同一专业工具链；实体只解码一次，多场会议独立出稿 | `scripts/test_workbench_flow.py`、`packing_assistant/document_text.py` |
| 技能与辖区一致性 | 修正技能生成器的默认国家，重新生成 66 岗与路由技能的两套镜像；JSON 确认拒绝非布尔值 | `scripts/test_stack_parity.py`、`scripts/test_http_confirmation.py` |
| 权限与失败传播 | 高风险确认仅接受布尔真值，字符串 false 不授权；只读模式在工具和直接岗位入口均拒写；结构化工具失败不再被外层改成成功；异常后释放会话 | `scripts/test_post_dispatch.py` |
| 分发包 | 默认改为配套 Python 服务与界面，显式文件允许列表、66 skills、SHA-256 清单；启动器只在包内安装依赖，独立目录启动验收 | `scripts/test_trial_pack.py`、`scripts/smoke_workbench_release.py` |

## 本地复跑

```powershell
npm run check
npm run check:full
.\.venv\Scripts\python.exe -m pytest demo/tests -q --basetemp=output/pytest-local
```

开发依赖见 `requirements-dev.txt`。`check:full` 的 Rust 部分使用锁文件及本地
缓存，首次执行前需 `cargo fetch --locked --manifest-path workbench/Cargo.toml`。

## 前一阶段基线（0.5.0-preview，2026-09-12 本机）

- 统一清单现有 **40 个检查组**，全量运行 **40/40** 通过；最终输入归属、会务分稿及发布脚本修改后，相关 **10/10** 检查组复验通过。包含产品冒烟、工作台 HTTP、装箱全链和 Rust。
- Rust：141 项测试通过；工作台 HTTP / 知识库：20 项通过。
- 聊天流与界面行为：32 项；实际工作台流程：18 项；启动器：13 项；模型与流协议：13 项；附件：12 项；真实日报内容：9 项。
- 轨迹导出：8 项通过；现有存储测试：27 项通过；66 岗原有聊天/执行回归通过。
- 业务文件回归有 1 项符号链接用例因当前 Windows 权限跳过，其余通过。
- 新增三十岗内容回归 **186 项**：人力 20、行政 19、IT 18、BIM 24、基础设计 37、机电设计 20、专项设计 28、基础设施设计 20；均包含真实 Markdown/Excel 产物验证。共用派发与权限回归 12 项、HTTP 确认类型 6 项、打包和启动引导 11 项。66 岗回归另强制通用骨架报错，验证全部进入专业起草路径。
- 分发包在独立目录从批处理启动，验证上传、无 Key 问答/起草、MD/XLSX 下载、端口冲突拒绝和重启恢复；66 岗离线生成均验收，未接求解器字段保持 `UNSPECIFIED`。全新包内 `.venv` 从 PyPI 安装依赖成功，并以该独立环境通过同一验收；安装失败路径亦已验证。
- 浏览器实际完成文本附件上传、日报生成及内容预览；刷新后自动恢复岗位、附件和下载入口；模型面板可读，高风险任务停在签认环节。1280×720 桌面和 390×844 窄屏中输入区可见。

最终日志：`output/workbench-complete-full-check.log`（40 组全量）、`output/workbench-complete-final-check.log`（最后 10 组复验）。

阶段日志保留在 `output/workbench-post-full-check.log` 与 `output/workbench-post-final-check.log`；安装与真实服务证据位于 `output/release-smoke/` 各验收目录的 `acceptance.json`、`first-install.log` 和 `installed-requirements.txt`。

最终本地交付包：`dist/civil-buddy-python-workbench-0.5.0-preview.zip`（1,764,653 字节），SHA256 为 `7b028ff6eccca74c25ccf791ad7705b161d48c58c3ee43a3634183d9e35c98f4`，同目录有 `.zip.sha256`。最终包验收记录为 `output/release-smoke/python-workbench-5b6lgjl2/acceptance.json`；首次全新依赖安装证据为 `output/release-smoke/python-workbench-di88cwng/`。最终验收复用该独立依赖环境，产品模块全部来自此次解压目录；requirements 未变。

独立校验记录：`output/workbench-completion-audit.json`。733 个清单文件散列均正确，732 个源输入与当前工作区逐字节一致；额外文件是打包生成的 README。实际 66 岗均成功生成非空文件；三种表格附件完成上传、按字段出稿、Markdown/Excel 下载及恢复；6 种非法确认输入被拒，布尔 false 时工具调用和写入均为 0。测试服务进程树和端口已清理。包仅本地构建，未上传发布。

## 后续可用性补齐（0.5.1-preview）

| 缺口 | 实现与验证 |
|---|---|
| 可编辑 Word | 共用 OOXML 导出器生成标题、段落、列表和真实表格，无新增依赖；已有文件不覆盖，导出失败保留其他产物并报告失败。`test_word_export.py` 13 项通过，另用独立 python-docx 打开、编辑保存并重开 4 岗实际文书。 |
| 后台取消 | 停止按钮请求取消；正在运行的本地工具完成当前调用后不再执行后续步骤。真实模型连接被关闭；浏览器 HTTP 断开同样收尾并释放会话，部分回复和已写文件可恢复。`test_workbench_cancel.py` 9 项通过，包含真实阻塞 socket。<br>**2026-09-20 起契约变更（#33）：** 浏览器断开、锁屏、切任务只是「脱离」，不再取消；本轮继续持有会话直到落盘，页面从 `GET /api/sessions/{sid}` 取回结果。结束一轮的只有两样：停止按钮（`POST /cancel`），以及无人连接超过 `CIVIL_DETACHED_TURN_SECONDS`（默认 600 秒，与页面轮询时长一致；设 0 即回到「断开即取消」）后由服务端自动停止并在记录里写明。脱离信号和时限都挂在 `SessionLease.disconnect()` 上：真实断开时只有它一定会被调用。`test_workbench_cancel.py` 14 项。 |
| 任务备份和迁移 | ZIP 保存完整对话、上传资料及文书；每次导入新建任务、改写下载路径、重新映射附件并清空高风险授权。限制清单、路径、校验和、记录数以及重复引用后的实际写入预算；异常回滚只清理本次新目录。`test_session_bundle.py` 7 项通过。 |
| 项目和会话存储 | 严格 ID、跨线程与进程串行事务、独有临时文件和原子替换；损坏索引保留原字节并拒绝覆盖；有限内存恢复聊天记录。竞争探针保留 120/120 次更新、40/40 个项目。`test_project_storage.py` 19 项通过，1 项因 Windows 无创建符号链接权限跳过。 |

全量日志 `output/workbench-followup-full-check.log`：44/44 检查组通过；备份字段边界、页面下载提示和版本入口更新后，`output/workbench-followup-final-check.log` 的 3/3 相关组通过。页面实际验证日报三种文件入口、Word 下载、备份导入新任务及刷新恢复。内嵌浏览器未报告 blob ZIP 的下载事件，因此另以真实 HTTP 保存 ZIP 后通过页面导入；没有把下载提示当作磁盘保存证据。

随后补齐招标解析、装箱两条 runtime 专用路径的 Word 导出，保持原文和工具数值，不为无表格文书凑造 Excel。新增 `test_runtime_office_exports.py` 8 项真实 API、失败与取消用例已加入统一清单，清单现为 45 组。相关检查记录在 `output/workbench-followup-runtime-final-check.log`（7 组通过，新增专项初跑失败），冻结后的专项复验见 `output/workbench-followup-runtime-office-check.log`（8/8 用例通过）。

本轮最终包：`dist/civil-buddy-python-workbench-0.5.1-preview.zip`，1,784,088 字节，SHA256 `1d33a54041050e9988ce5a652da842a29f07fb6cfaffaf5069987c74eabc1796`。独立目录实际启动验收 `output/release-smoke/python-workbench-2ukoi6rp/acceptance.json` 全部通过：66/66 岗生成且各有有效 DOCX；CSV/DOCX/XLSX 三种资料输入均验证 MD/XLSX/DOCX 内容；任务导出导入、附件和文件字节一致、原任务不变、确认清空、重启恢复、空闲取消及端口/进程清理均核实。依赖未变，复用上一版首次独立安装的虚拟环境，产品代码来自新包。

独立包校验 `output/workbench-followup-audit.json`：736 个清单文件长度与散列正确，735 个源输入与当前工作区逐字节一致；生成的 README 为额外文件。新包仅本地交付，未上传发布。

## 适用边界

- 运行任务的防重入与取消覆盖一个 Python 服务进程；项目索引和会话元数据已有跨进程写入锁，运行队列尚非分布式队列。
- “停止”协作取消后台后续步骤，不能撤销已经发生的计算或写入；第三方同步工具在当前调用结束后停止。
- 备份仅针对单任务，不包含模型 Key、全局知识库、自建岗位、原工程项目配置或外部作业目录；导入任务放入“未归类”，须自行重新归入项目。
- 高风险确认只认本人在本轮键入的确认句（HTTP 用 `confirm_text`）；`confirm_ok` / `p0_confirmed` 布尔不能代替（网关收到真值即 422，MCP 一律拒收），上一轮的确认不带到下一轮，纯问题和未确认的高风险请求不写文书。
- 旧会话中已保存的 `SG` 缺少来源信息，保留原值；用户提供明确辖区后更新。新会话不再默认猜测国家。
- 专用起草覆盖 **66/66**；新增 20 个勘察设计岗位按单体、系统、路段或问题逐项保留明确输入和缺项。`UNSPECIFIED` 与投标阻断规则保留；设计模板不执行专业设计计算，BIM 模板不执行 IFC 扫描。L3 引擎岗仍只有 pack-ship。
- 新分发包需要已有 Python，首次安装依赖需要网络；不含 Python 解释器或 Rust exe。历史 Rust 入口保留用于旧栈维护，不能视为本次 Python 产品同等实现。包仅本地构建，未上传发布。
- 本次验收验证本地业务链路、真实安装和模型降级路径，不代表真实联网模型质量或生产环境验收。
