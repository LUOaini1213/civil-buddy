# 从零跑起来

产品：内部讨论 AI 草稿。不判定可投标，不判定可以开工。岗数 **66**。`submit_blocked` 默认 true。

全量规划：[product-plan.md](product-plan.md)。切片：[product-completion-plan.md](product-completion-plan.md)。  
必读链：本文 → [PROTOCOL.md](PROTOCOL.md) · [MCP.md](MCP.md) · [SKILLS.md](SKILLS.md) · [KB.md](KB.md)。Skill = 怎么写；MCP = 能调什么。

## 1. 起两个入口

仓库根：`C:\Users\LW\civil-buddy`。

```powershell
cd C:\Users\LW\civil-buddy
python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

```powershell
cd C:\Users\LW\civil-buddy\demo
# 若无 demo/.env：copy .env.example .env ，填 DEEPSEEK_API_KEY（不要提交）
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

| 打开 | 用途 |
|------|------|
| http://127.0.0.1:8000/ | 先理解再处理 · Agent 循环 `POST /api/agent` |
| http://127.0.0.1:8000/workbench | 真装箱 3D / HITL |
| http://127.0.0.1:8765/ | 66 岗工作台（Python `demo/` 或 Rust `workbench/run.ps1`） |

土木企业上手（Rust 工作台，不需要先起 Python demo）：

```powershell
cd C:\Users\LW\civil-buddy\workbench
.\run.ps1
```

召唤专家后：提问不写盘；说「写一份」才出内部讨论草稿。可上传广联达/Excel 导出的 `xlsx`/`csv` 和招标 `docx`/`txt`，缺价标 `UNSPECIFIED`。

有表格的岗会在会话目录另存同名 `.xlsx`，用 Excel 直接打开。要把稿落到工程文件夹、并让专家**直接读该夹里的 Word/Excel**（不必再点上传）：

```powershell
$env:CIVIL_JOB_ROOT = "C:\Users\LW\Documents\某工地"
```

目录须已存在。说「写一份」会自动抄夹内 `.xlsx` / `.docx` / `.csv` / `.txt`。点名已有工作簿（如「现场台账」）时，在该文件里只增改 `CB草稿-*` 工作表，**不改你原来的表**。**禁止**把 `D:\layout` 当缺省作业根。construction 方案另有模板 `专项施工方案-AI草稿.docx`。这不是接管本机 Word/Excel 窗口，也不是全盘搜索。

扫描件 PDF：产品默认拒绝（无文字层）。可选 `CIVIL_PARSE=auto` 走 MinerU/Docling；失败仍拒绝，不装 OCR 成功。不要把扫描 PDF 当已抽出招标。

本机刚跑过的冒烟（刀后快闸）：

```powershell
cd C:\Users\LW\civil-buddy
python scripts/test_understand.py
python scripts/test_agent_loop.py
python scripts/test_mcp_stdio.py
python scripts/test_mcp_surface.py
python scripts/test_kb_schema.py
python scripts/test_official_title_scan.py
python scripts/test_memory_slot.py
python scripts/test_tender_parse_engine.py
python scripts/test_exclusive_engine.py
python scripts/test_construction_skill_path.py
python scripts/test_docs_completion.py
python scripts/test_office_job.py
```

## 2. 先问一句（必须不写盘）

默认面粘贴「什么是 GST」→ 意图 `chat`，回复含 IRAS 页述 **9%**，无矩阵文件。  
把 `session_id` 当工地/标段档案号一直带着；上下文在服务端槽里，不要把整段聊天再贴给 DeepSeek。只读槽：`GET /api/context/{session_id}`。

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
