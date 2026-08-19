# 从零跑起来

产品：内部讨论 AI 草稿。不判定可投标，不判定可以开工。岗数 **66**。`submit_blocked` 默认 true。

全量规划：[product-plan.md](product-plan.md)。切片：[product-completion-plan.md](product-completion-plan.md)。Skill = 怎么写；MCP = 能调什么。

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
| http://127.0.0.1:8765/ | 66 岗工作台 |

本机刚跑过的冒烟：

```powershell
cd C:\Users\LW\civil-buddy
python scripts/test_understand.py
python scripts/test_agent_loop.py
python scripts/test_mcp_stdio.py
```

## 2. 先问一句（必须不写盘）

默认面粘贴「什么是 GST」→ 意图 `chat`，回复含 IRAS 页述 **9%**，无矩阵文件。

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
