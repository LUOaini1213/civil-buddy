# Scripts

## 统一质量检查

`npm run check` 与 `python scripts/check_project.py` 使用同一份检查清单。
默认检查覆盖运行时、界面、业务文件和产品冒烟；`--full` 加跑 API、装箱链路
与 Rust（需提前缓存 Cargo 依赖）。每项有超时，失败会汇总。

```bash
npm run check
npm run check:full
npm run check -- --list
npm run check -- --only chat-stream,runtime-threads,business-files,trace-artifacts
```

工作台完整使用流程的独立回归：

```powershell
npm run check -- --only app-launcher,workbench-settings,workbench-uploads,workbench-flow
```

覆盖真实本地 HTTP 启停、模型配置与模拟模型流、PDF/Office 附件解析、无 Key 起草、下载和会话恢复。`check:full` 还运行 `demo/tests` 的 HTTP 回归，需要 `requirements-dev.txt`。

可选语义摘要的来源校验、服务隔离与本地模拟模型 HTTP 回归：

```powershell
npm run check -- --only semantic-memory,semantic-integration,semantic-http
```

任务记忆重建与问答不误生成文件的 HTTP 回归：

```powershell
npm run check -- --only context-rebuild,readonly-routing,task-routing
```

新增回归分别验证 SSE 分块与会话隔离、后台任务防重入、知识库索引与 Office
文件保护，以及 JSON/dual/SQLite 的轨迹保真。旧的 `run_precommit_tests.py`
保留为历史比赛与较大数据集检查入口。

## One-shot（新人 / 开源首页入口）

| 脚本 | 用途 |
|------|------|
| **`demo_one_shot.py`** | **一键演示**：默认 smoke；`--closed-loop` / `--eval-tiny` / `--all` |

```bash
python scripts/demo_one_shot.py
python scripts/demo_one_shot.py --all
```

## CI / 产品入口（保留在本目录）

| 脚本 | 用途 |
|------|------|
| `smoke_agent_product.py` | 产品冒烟（demo_one_shot 默认调用） |
| `demo_agent_closed_loop.py` | 闭环自检（感知→规划→工具→目标） |
| `eval_harness_cli.py` | tiny/20t 评测 |
| `eval_workteams_cli.py` | steps vs llm 影子评测 + KPI |
| `test_agent_auto_mode.py` | 自动模式 |
| `test_whatif_accept.py` | what-if |
| `test_continue_improve.py` | 持续改进项 |
| `test_p0_p1_p2_full.py` | P0–P2 链 |
| `test_single_team_loop.py` | 闭环（命名历史） |
| `run_t60_main.py` / `run_t80_main.py` | 大料试跑 |
| `compare_pack_engines.py` | 引擎 A/B |

```bash
python scripts/demo_one_shot.py
python scripts/smoke_agent_product.py
python scripts/eval_workteams_cli.py --tiny-only
python scripts/eval_harness_cli.py
```

## Windows 启动

见 `scripts/win/`（`start-gateway.bat` 等）。

当前 Python 工作台分发包（不上传发布）：

```powershell
.\.venv\Scripts\python.exe scripts/build_workbench_release.py --version 0.9.0-preview
.\.venv\Scripts\python.exe scripts/smoke_workbench_release.py dist/civil-buddy-python-workbench-0.9.0-preview.zip --all-experts
```

打包使用明确允许列表，包含新岗位源码、66 份 skills、KB 及静态资源；排除环境密钥、会话和本机附件。zip 及逐文件清单带 SHA-256。冒烟脚本独立解压，从批处理启动，验证 HTTP、文书、附件、重启恢复并清理测试进程。首次安装会在包内创建 `.venv`，需要 Python 和网络；参数见 `scripts/start_workbench.py`。

## 本地实验

`scripts/dev/` 与 `scripts/_*.py` **不入仓**（gitignore），仅本机临时实验。

## 比赛回归（precommit --quick 已挂）

| 脚本 | 用途 |
|------|------|
| `run_precommit_tests.py` | booking + volume gates + 下列单测（`--quick` 跳过工地 Excel） |
| `test_booking_regression.py` | 订柜 N0* / 空心体积 / 铁架条带 |
| `test_nonstandard_tools.py` | nonstandard.inspect/enrich 实跑 |
| `test_cog_shift_mid_ok.py` | mid50 OK 贴墙不纵向拉开 |
| `test_phase0_task_success.py` | task_success 计分单元 |
| `test_facade_sme_mini.py` | 幕墙 SME 小票 A→B 闭环 |
| `test_hollow_volume_n0.py` | 空心 outer 不绑架订舱体积 |
| `competition_smoke.ps1` | 评委向 hard gates + scorecard |

