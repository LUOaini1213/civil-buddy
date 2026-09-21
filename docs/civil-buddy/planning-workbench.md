# 施工排程与场内路线工作台

本轮已接入工作日 CPM、资源约束排程、基线、周承诺、计划文件交换和场内最短路线。计算使用明确输入和确定性工具，无需配置大模型。真实施工计划尚未提供；下方验收来自合成算例和公开测试文件，不能替代真实工程验收。

## 入口与操作

| 页面 | 当前能力 | 操作边界 |
| --- | --- | --- |
| `/engineering/planning` | 编辑工期、WBS、工作日历、四类依赖、资源和进展；计算后查看甘特图、依赖网络、日期与时差 | 该页甘特图展示计算结果。修改参数后重新计算；资源调整先预览差异，再应用，可撤销 |
| `/engineering/schedule` | 原有日期甘特图；拖动日期和进度、整次手势撤销、保存重开 | 保留独立日期编辑模式，不自动执行 CPM 或资源排程 |
| `/engineering/routes` | 编辑道路节点、距离或时间、单向/双向及封路状态，查看最短路线和分段来源 | 独立道路网络；不用于计算施工关键路径，不从示意图位置猜距离或车速 |

施工排程可保存、另存副本、打开最近计划、载入历史为草稿、撤销上次保存。计算失败或输入变动时，上次结果仍保留并标明过期；导出必须引用与当前输入匹配的成功 `run_id`。已应用资源方案修改后，必须重新运行并应用资源调整，或明确改用 CPM，不能在保存或导出时静默变成无资源约束的结果。

## 计算口径

工期、资源需求与容量来自用户或导入文件的明确字段，不根据任务名称、日期差或模型回复编造。统一项目日历用 `weekdays` 表示工作周（星期一为 0），`holidays` 表示额外非工作日。日期范围为 1900–2100 年，排程限工程起点后 10 年内且不晚于 2100-12-31。

- 支持整工作日工期、FS/SS/FF/SF 和正负整数工作日时距；工期 0 为里程碑。内部区间为 `[start_offset, finish_offset)`；正工期的显示结束日期是最后占用工作日，里程碑显示自身边界日期。
- WBS 父任务的输入 `duration`、`progress` 均为 0，依赖与资源为空、实际日期为空；汇总值由叶子任务派生。父任务不能作为前后置工序，汇总结束日期包含末尾里程碑。
- CPM 输出各工序最早/最迟日期、总时差和全部关键任务。依赖环、未知编号、无效层级和不可行边界明确拒绝。甘特图仅画 FS 箭头，四类关系及其时距在依赖网络中查看。
- 实际开始/完成日期目前是进展记录，不锁定已开工任务，不据此预测剩余工期。完成率不会改变明确输入的工期。

CPM 不考虑资源容量，另行报告超配区间。资源调整使用 OR-Tools CP-SAT，在统一日历、不可中断工序及明确容量下，最小化全部叶子工序的完工边界。`OPTIMAL` 表示本次约束下已证明最优；`FEASIBLE` 只表示找到可行方案。时限内没有可行解不等于证明项目不可行。默认求解时限 10 秒，HTTP 子进程另有 40 秒上限。

资源方案显示本次日期和资源用量，不把 CPM 时差或关键任务标记当成资源约束后的结论；这些当前字段清空，原 CPM 比较值留在 `cpm_*`。没有自动增配班组、延长班次、分拆工序、多日历或随日期变化的资源容量。

PPC = 本周已完成承诺数 / 本周全部承诺数 × 100%。尚未结算的承诺仍计入分母并单独显示；未完成项须记录原因，可附制约事项。基线来自已保存的成功计算结果，后续改参不会覆盖；比较中的日期偏差使用日历天。PPC 和计划偏差均不等于工程验收结论。

当前上限：250 项任务、32 类资源、2500 条依赖、500 项资源分配；容量和需求为 1–10000 的整数。资源用量表示完整单位，不是百分数：1 个班组对应 MSPDI `Units=1.0`（100%）。源文件 0.5（50%）等部分资源占用目前不能表示，须明确拒绝，不能暗中缩放或取整；可先在源软件整理为项目明确采用的整单位资源。周承诺最多 2000 条。道路模型最多 200 个节点、500 条边，距离单位为 m、固定通行时间为 min；每段保留道路编号、数值来源和反向通行标记。道路页目前未接独立项目持久化或路线文件导出，不包含车辆路径规划或交通预测。

## 保存、交换与恢复

网页计划记录位于**运行该服务的仓库** `.civil-buddy/out/engineering/plans/`；这是网页适配器采用的 `demo.config.REPO_ROOT`，不等同于任意 CLI 工地目录。客户端不能指定保存路径。记录包含输入、成功结果、计算方式、基线、周承诺、合成标记、导入来源与最多 20 个历史快照，最多保存 100 个计划。

保存使用预期修订号、摘要校验和原子替换；并发冲突要求重新打开或另存副本。取消在写入替换前检查，失败不覆盖原记录。重开读取保存结果，不自动重算，并为当前服务登记新的结果引用。备份或恢复时保留上述完整目录及原始输入文件；本轮尚未提供一键跨机完整项目包。

| 格式 | 导入 / 导出范围 | 交接注意事项 |
| --- | --- | --- |
| JSON | 本工作台计划交换格式：`plan`、`original_dates`、导出说明 | **不是完整项目包**：不含周承诺、基线、历史版本、原文件字节或可直接恢复的资源运行结果。资源日期单独保留，重导入后须明确选择计算方式 |
| CSV / XLSX | 本工作台明确列名与元数据结构，保留任务 ID、层级、依赖、资源、日历、实际日期及原计划日期 | 不是任意进度表智能识别。CSV 对公式前缀作文字转义；XLSX 导出文字单元格，导入拒绝公式、宏和外部工作簿链接 |
| Microsoft Project XML（MSPDI） | 导入受支持子集；导出明确的 8 小时/工作日日粒度 XML | 保留 ID 映射、WBS、四类依赖与整数工作日时距。源文件必须明确工期、项目开始和日历；不靠日期差补工期 |
| MPP / P6 XER / P6 PMXML | 可选 MPXJ + JVM 只读转换，再通过同一 MSPDI 校验 | 本工作台不提供原生 MPP/P6 写回。多项目文件拒绝，要求先从源软件导出单项目；转换不调用 Project/P6 原版排程引擎 |

文件导入上限 8 MiB；XLSX 解压总量上限 32 MiB，XML 禁用 DTD/外部实体并限制节点、深度和文本。MPXJ 在固定命令的临时子进程内执行，45 秒超时，JVM 堆上限 384 MiB；上传内容不能成为命令或客户端文件路径。系统级沙箱不允许该子进程时明确拒绝，不绕过沙箱。

导入先展示报告和原日期，用户确认后应用；导入本身不重新排程。不足整工作日的工期/时距、不同任务日历、循环节假日或额外工作日等不能表达的内容会拒绝或报告；手工排程、约束、成本、基线等未映射语义不能据此称为无损迁移。当前保存的是源文件名、格式、SHA256、原日期和报告，**不保存上传原文件的字节**，交接应另附授权原文件。Project 或本工作台重新计算都可能改变已导出的资源方案日期。

## 安装与启动

使用项目实际 Python 环境；本轮 Windows 验证环境为 Python 3.11。已安装主工作台的同事只需补 `requirements-planning.txt`。首次安装需要网络，后续计算和本地前端资产不依赖在线模型。

```powershell
python -m pip install -r requirements.txt -r requirements-cad.txt
python -m pip install -r requirements-planning.txt
python -m packing_assistant.civil app --port 8767
```

然后打开 `http://127.0.0.1:8767/engineering/planning`。沿用主工作台访问口令、同源请求和读写权限；只读模式不能保存或导出。导出还须完整输入既有确认句 `我明白，将由持证人员签认`；这不代表已获得持证人员签认。

`requirements-planning.txt` 固定 OR-Tools 9.15.6755、NetworkX 3.6.1、openpyxl 3.1.5、defusedxml 0.7.1、MPXJ 16.7.0、JPype1 1.7.1；传递依赖未全部锁定，另一台机器仍需重跑检查。CPM 内核自身使用标准库；缺可选引擎或 JVM 时能力接口明确报告未就绪。安装 Python 包不会自动安装 Java。

### 可选的 MPP / P6 运行时

本机使用从 [Eclipse Adoptium 官方 API](https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jre&os=windows) 获取、校验官方 SHA256 后解压的 Windows x64 Temurin JRE 21。目录为主 checkout 的 `C:\Users\LW\civil-buddy\.tools\java\temurin21\jdk-21.0.12.1+1-jre`；来源记录在 `.tools/java/SOURCE.json`，不是系统安装，也没有修改系统 `PATH` 或 `JAVA_HOME`。

本轮固定包为 [OpenJDK21U-jre_x64_windows_hotspot_21.0.12.1_1.zip](https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_windows_hotspot_21.0.12.1_1.zip)，SHA256 为：

```text
d35f31e712f0fcf6ac5a093edc90204fbff22f720ba3950bd09d331d5e621636
```

另一台 Windows 机器的步骤：从官方来源下载适合其架构的 JRE 压缩包；用 `Get-FileHash -Algorithm SHA256` 与该包官方校验值核对；保留来源和许可文件，解压到本机专用目录。使用其他版本时不能套用上面的摘要。可仅在启动服务的 PowerShell 会话设置实际目录：

```powershell
$env:CIVIL_JAVA_HOME = 'C:\your-project\.tools\java\temurin21\your-jre-directory'
python -m packing_assistant.civil app --port 8767
```

`CIVIL_JAVA_HOME` 必须指向含 `bin/server/jvm.dll` 的 JRE 根目录。未显式设置时，适配器先查仓库本地 `.tools/java/temurin21/*`，Git worktree 也查主 checkout，再尝试 JPype 默认 JVM。`.tools` 本轮在 Git 本地排除规则中，不会随源码自动分发；新电脑需自行准备并检查 `/api/engineering/planning/capabilities` 的 `formats.mpxj.available`。该探测仅证明依赖可找到，真实读取还需测试文件验证。

## 接口与源码位置

| 接口 | 用途 |
| --- | --- |
| `GET /api/engineering/planning/capabilities`、`/example` | 本机能力状态、明确标为合成的演示输入 |
| `POST /api/engineering/planning/calculate`、`/optimize` | CPM / 资源约束求解，成功后返回 `run_id` |
| `GET/POST /api/engineering/planning/projects` | 最近计划 / 保存；更新需 `id` 与 `expected_revision`，资源方案需匹配的运行结果 |
| `GET /api/engineering/planning/projects/{id}?version={n}` | 打开当前或历史修订，保留保存时的结果 |
| `POST /api/engineering/planning/projects/{id}/baseline`、`/undo` | 设置基线 / 撤销上次保存，均校验修订号 |
| `POST /api/engineering/planning/import`、`/export` | 单文件上传及受限导出；导出必需 `run_id` 和确认句 |
| `POST /api/engineering/operations/{id}/cancel` | 用本次 `X-CAD-Operation-ID` 取消排程操作 |
| `POST /api/engineering/routes/calculate`、`/operations/{id}/cancel` | 场内道路计算 / 取消 |

内核在 `packing_assistant/engineering/planning.py`，资源适配在 `planning_optimize.py`，存储在 `planning_records.py`，格式转换在 `planning_exchange.py`，路线在 `routing.py`。网页接入为 `demo/planning_api.py`、`demo/routing_api.py` 和 `demo/static/engineering-planning.*`、`engineering-routing.*`。本轮通过参数面板和确定性按钮操作，尚未将全部新功能接入统一 Agent 对话。

## 本轮验收记录

下表区分自动化、浏览器和待补证据。最终 `npm run check` 为 108/108；提交边界修复另经 3/3 专项检查验证。检查任务数与单个测试条数使用不同口径，不相加。

| 项目 | 已观察到的结果 | 证据范围 |
| --- | --- | --- |
| CPM 核心 | 15/15 通过 | 四类依赖、正负时距、日历、WBS、里程碑、日期边界；小网络穷举独立核对 |
| 资源优化 | 9/9 通过 | 实际 OR-Tools 求解、明确容量、依赖与日期、汇总末里程碑及取消边界 |
| 文件交换 | 19/19 通过 | JSON/CSV/XLSX/XML 往返、整单位资源与部分占用拒绝、公式/实体防护、资源结果日期、2100 年边界 |
| 场内路线 | 8/8 通过 | 明确边权、单向/封路、不可达、平行边与来源、单位和无效输入 |
| 排程 UI 离线测试 | 18/18 通过 | 状态、参数编辑、资源方案应用与撤销、版本/导入和来源报告等界面行为；不等同于浏览器验收 |
| 全项目与提交边界检查 | 最终 `npm run check` 108/108；提交边界专项 3/3 通过 | 专项为 `planning-workbench`、`http-demo`、`runtime-api`；`http-demo` 为 72 passed / 9 skipped，跳过不算通过 |
| HTTP 工作台 | 14/14 通过 | 已按导出必填 `run_id` 复跑；含结果来源、保存/重开、资源日期、冲突、损坏、取消提交及只读边界 |
| 真实浏览器：排程 | 合成 CPM 8 天 → 单班组资源方案 11 天 → 保存，服务重启后重开修订 4 仍为 11 天；保留 8 天基线，周计划 PPC 50% | 本机真实浏览器操作，不是跨电脑迁移验收；修改进度后直接保存被拒，未降为 CPM，撤销可恢复 |
| 真实浏览器：路线与排程窄屏 | 桌面合成路线 150 m；封 R4 后 180 m；再封 R2 后不可达。排程页在 390px 视口内文档总宽 375px，表格可横向滚动，无整页溢出 | 390px 证据仅适用于排程页，路线页仅验桌面；不是实地测量或全设备覆盖 |
| 原生 MPP 读取 | 公开二进制测试文件实际读入 16 项任务及 16 组原日期；网页文件选择器上传后展示报告，确认应用、保存修订 1，再刷新恢复 | 离线和网页实际读取已验；报告明确提示 EffortDriven 不参与本工作台计算。文件是 MPXJ 官方合成回归数据，不是用户真实施工计划 |
| P6 读取 | 从明确合成计划经已安装 MPXJ 写出 XER / PMXML，再实际读入，任务数与工期一致 | 合成往返，不证明任意外部 P6 工程、小时班次和多日历完全兼容 |

MPP 文件来源为 [MPXJ 固定提交的 task-links-project2000-mpp9.mpp](https://github.com/joniles/mpxj/blob/c5e1320cde0acd404031495aa66c17639a57239b/junit/data/generated/task-links/task-links-project2000-mpp9.mpp)，SHA256 为 `15673f1358c4f869244e62226322f730dba9f6b097f2e50108f2afae9991b758`。该文件与来源清单仅保存在本机 `.tools/planning-fixtures/`；测试缺该文件或 MPXJ/JVM 时会跳过相关项，不自动下载，不能把跳过记作通过。

复跑使用准备好的项目环境，不调用真实大模型接口：

```powershell
$env:PYTHON_DOTENV_DISABLED = '1'
python scripts/test_engineering_planning.py
python scripts/test_planning_optimizer.py
python scripts/test_planning_exchange.py
python scripts/test_engineering_routing.py
python scripts/test_planning_workbench.py
node scripts/test_engineering_planning_ui.cjs
npm run check
```

推荐合成演示：A=2，B=4/C=3 均依赖 A，D=2 依赖 B/C；CPM 为 8 个工作日。B/C 共用一个班组为 11 天，两个班组恢复 8 天。演示时先保存 CPM 并建立基线，再预览/应用资源调整、保存重开，记录两条周承诺完成一条以展示 PPC 50%，最后导出并重新导入核对原日期。

尚未验收：用户真实施工计划；源 Project/P6 软件打开导出 XML 后的逐项日期与语义核对；另一台电脑迁移后的整套结果；完整跨机项目包。工程输入到位后，必须核对项目日历、明确工期、资源、约束、关键任务及原文件日期差异，不能用合成通过替代。

## 开源来源与贡献范围

| 依赖 | 本轮用途 | 来源与许可 |
| --- | --- | --- |
| Frappe Gantt 1.2.2 | 本地甘特展示与原日期页拖动 | [上游仓库](https://github.com/frappe/gantt)；MIT，保留在 `demo/static/vendor/frappe-gantt-1.2.2/license.txt`，官方 npm 包来源及 integrity 在同目录 `SOURCE.json` |
| OR-Tools 9.15.6755 | CP-SAT 区间、依赖、累计资源容量及最小完工目标 | [调度说明](https://developers.google.com/optimization/scheduling/job_shop)、[Apache-2.0 许可](https://github.com/google/or-tools/blob/v9.15/LICENSE) |
| NetworkX 3.6.1 | 多重有向道路图与 Dijkstra 最短路 | [最短路文档](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html)、[BSD-3-Clause 许可](https://github.com/networkx/networkx/blob/networkx-3.6.1/LICENSE.txt) |
| MPXJ 16.7.0 | MPP / P6 读取并转换为受限 MSPDI 输入 | [格式和语言说明](https://www.mpxj.org/)、[LGPL-2.1 许可](https://github.com/joniles/mpxj/blob/v16.7.0/LICENSE)；配合 JPype1 与独立准备的 Java 运行时 |

自研部分是整工作日 CPM 内核、输入校验、受限工具适配、资源结果独立复核、项目版本/基线/周承诺、交换报告和网页交互；不宣称实现了 Microsoft Project 或 P6 的完整引擎，也未复制其他项目的保留权利模板、品牌或翻译。具体依赖署名见 `demo/static/engineering-notices.txt`；若再分发库、JRE 或测试数据，还需保留对应版本的许可和来源。学校比赛用途仍须如实说明开源复用与自研范围，比赛规则尚未提供。
