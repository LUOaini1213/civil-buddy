# 从零跑起来

产品：**土木版 Codex**（完整面：TUI · exec · app · IDE/MCP · 并行 thread）。内部讨论 AI 草稿。不判定可投标，不判定可以开工。岗数 **66**（每个是一份 skill）。`submit_blocked` 默认 true。

```powershell
python -m packing_assistant.civil
python -m packing_assistant.civil "什么是 GST"
python -m packing_assistant.civil exec --confirm "写临边专项方案讨论提纲"
python -m packing_assistant.civil app
python -m packing_assistant.civil mcp --pack construction
python -m packing_assistant.civil serve
python -m packing_assistant.civil skills
python -m packing_assistant.civil --sandbox read-only "出一份税务日历"
```

TUI 斜杠：`/skills` `/new` `/bg` `/threads` `/resume` `/approvals` `/sandbox` `/confirm` `/files` `/mcp` `/status` `/help`。  
配置：`civil.toml.example` → `civil.toml`。IDE：`ide/README.md`。

全量规划：[product-plan.md](product-plan.md)。切片：[product-completion-plan.md](product-completion-plan.md)。  
试用（Python 分发包，无 Key 可本地起草）：仓库根 [给试用的人.md](../../给试用的人.md)。
必读链：本文 → [PROTOCOL.md](PROTOCOL.md) · [MCP.md](MCP.md) · [SKILLS.md](SKILLS.md) · [KB.md](KB.md)。Skill = 怎么写；MCP = 能调什么。

## 1. 启动工作台

在仓库根目录使用 Python 3.11 或更新版本：

```powershell
cd C:\Users\LW\civil-buddy
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m packing_assistant.civil app
```

服务就绪后浏览器自动打开 `http://127.0.0.1:8765`。保持终端运行，按 Ctrl+C 停止服务。若端口已被占用，增加 `--port 8766`；只需要服务时增加 `--no-browser`。已有虚拟环境可跳过创建步骤。

无需 API Key 即可试用：

1. 点「浏览 66 岗」查看岗位，或点「了解岗位能力」并发送。
2. 点「生成日报模板」并发送；未提供的事实保留待填。
3. 在文书卡中预览 Markdown，下载 Markdown / Excel。
4. 点附件按钮上传当前任务的资料，再说明要从哪些事实起草。单文件上限 20 MB，每会话最多 12 个附件；一次请求最多 25 MB。
5. 在左侧重新打开任务，恢复消息、上次选择的附件和历史交付物。每轮交付物保留独立副本。
6. 输入框下方点「任务记忆与本地搜索」，核对自动提取的任务记忆，按关键词找回历史与所选附件原文。长对话按完整请求预算压缩，原文在本机保留；详见 [上下文与本地检索](CONTEXT.md)。
7. 直接输入「全面检查投标响应并汇总缺项」，并选择招标和响应附件。页面展示解析、两个并行子任务、汇总结果与预算；「岗位资料与工具」可查 66 岗契约，详见 [协作说明](COLLABORATION.md)。

需要开放式问答时，在「设置 → 模型设置」填写 API Key、Base URL 和模型名称并保存。空 Key 保留当前 Key；「恢复启动配置」撤销本次运行的修改。Key 不写入聊天记录、浏览器存储或配置文件；重启后恢复环境配置。高风险起草要求键入完整确认句，纯提问不触发文件生成。

同一设置窗口提供「长对话自动生成语义摘要」，默认关闭，保存不会立即调用模型。启用后只对已配置模型的问答生效：接近预算时，每轮最多增加 1 次同模型调用，整理当前任务较早的已提交历史，最近 4 条保留原文。摘要有字符位置与数字依据校验，但仍未核验；当前更正优先，失败或 12 秒超时沿用规则记忆与检索。可在「任务记忆与本地搜索」查看摘要及原文；输入框下方的调用量和预算是估算，不代表费用。

重启或恢复启动配置后，该开关关闭。64 KiB 摘要缓存可留存，重新开启时须核对本任务来源；完整原文不删除。备份导入新任务后重建规则记忆和索引，不直接信任旧语义摘要。摘要不进入业务起草字段或签认参数；详见 [上下文与语义摘要](CONTEXT.md#可选模型语义摘要)。

如需真装箱 3D / HITL，再单独启动工程装柜服务：

```powershell
cd C:\Users\LW\civil-buddy
.\.venv\Scripts\python.exe -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

| 打开 | 用途 |
|------|------|
| http://127.0.0.1:8000/ | 先理解再处理 · Agent 循环 `POST /api/agent` |
| http://127.0.0.1:8000/workbench | 真装箱 3D / HITL |
| http://127.0.0.1:8765/ | 当前 66 岗工作台（Python `demo/`，入口 `civil app`） |

历史 Rust `workbench/run.ps1` 与 `scripts/civil-buddy-desktop.ps1` 保留用于旧栈维护，不是本次 Python 工作台的启动入口；新版界面与业务接口请配套使用 `civil app`。当前 Windows 分发包的 `start-workbench.bat` 会启动同一 Python 服务。

召唤专家后：提问不写盘；说「写一份」才出内部讨论草稿。可上传广联达/Excel 导出的 `xlsx`/`csv` 和招标 `docx`/`txt`，缺价标 `UNSPECIFIED`。

文书会另存可编辑的 `.docx`，有表格的岗同时另存 `.xlsx`。可从文书卡下载 Word 或 Excel；设置菜单支持单任务 ZIP 备份和导入，导入始终创建新任务，操作步骤见 [试用说明](../../给试用的人.md)。要把稿落到工程文件夹、并让专家**直接读该夹里的 Word/Excel**（不必再点上传）：

```powershell
$env:CIVIL_JOB_ROOT = "C:\Users\LW\Documents\某工地"
```

目录须已存在。说「写一份」会自动抄夹内 `.xlsx` / `.docx` / `.csv` / `.txt`。点名已有工作簿（如「现场台账」）时，在该文件里只增改 `CB草稿-*` 工作表，**不改你原来的表**。**禁止**把 `D:\layout` 当缺省作业根。construction 方案另有模板 `专项施工方案-AI草稿.docx`。这不是接管本机 Word/Excel 窗口，也不是全盘搜索。

文本 PDF 可直接上传。扫描 PDF 无文字层时会提示无法提取，需先提供文字版；不能把扫描件当作已抽出招标。工程装柜服务另有 `CIVIL_PARSE=auto` 的可选解析器，此配置不代表工作台已提供 OCR。

本机刚跑过的冒烟（刀后快闸）：

```powershell
cd C:\Users\LW\civil-buddy
npm run check
python scripts/demo_agent_middleware.py
python scripts/test_understand.py
python scripts/test_agent_loop.py
python scripts/test_mcp_stdio.py
python scripts/test_mcp_host_client.py
python scripts/test_mcp_surface.py
python scripts/test_kb_schema.py
python scripts/test_kb_k4_depth.py
python scripts/test_official_title_scan.py
python scripts/test_memory_slot.py
python scripts/test_codex_expert_skills.py
python scripts/test_civil_codex.py
python scripts/test_tender_parse_engine.py
python scripts/test_exclusive_engine.py
python scripts/test_construction_skill_path.py
python scripts/test_docs_completion.py
python scripts/test_office_job.py
python scripts/test_desktop_launcher.py
python scripts/test_llm_byok.py
python scripts/test_trial_pack.py
```

## 2. 先问一句（必须不写盘）

默认面粘贴「什么是 GST」→ 意图 `chat`，解释概念但不默认填入税率，无矩阵文件。未提供的辖区、税率及适用期资料保持 `UNSPECIFIED`。
把 `session_id` 当工地/标段档案号一直带着；上下文在服务端槽里，不要把整段聊天再贴给模型。只读槽：`GET /api/context/{session_id}`。

或：

```powershell
curl -s http://127.0.0.1:8000/api/agent -H "Content-Type: application/json" -d "{\"text\":\"什么是 GST\"}"
```

## 3. 接 MCP Host（无 MSVC）

```powershell
cd C:\Users\LW\civil-buddy
python demo/mcp_stdio.py --pack bid
```

Host 配置样例：[mcp-host.example.toml](mcp-host.example.toml)。说明：[MCP.md](MCP.md)。

## 4. 高风险写盘

确认句必须原句：`我明白，将由持证人员签认`。未勾选则 `waiting_hitl`，0 份稿。
