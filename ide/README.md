# IDE 面 · 土木版 Codex

OpenAI Codex 的 IDE 是编辑器里的 agent。Civil Buddy 的 IDE 面是 **MCP + skill 包 + AGENTS.md**，挂在 Cursor / VS Code / Grok 上。仓库不另发 VS Code Marketplace 插件（那是另一套签名与发布）。

## 挂上

工作目录必须是本仓库根。不要把 API Key 写进这些 JSON。

| 宿主 | 把哪份拷过去 |
|------|----------------|
| Cursor | `ide/cursor/mcp.json` → 项目 `.cursor/mcp.json` |
| VS Code Copilot / MCP | `ide/vscode/mcp.json` → 用户 MCP 配置 |
| Grok | `docs/civil-buddy/mcp-host.example.toml` 贴进 `~/.grok/config.toml` |

或命令：

```powershell
python -m packing_assistant.civil mcp --pack construction
python -m packing_assistant.civil mcp --expert pack-ship
```

`--pack bid` 看得见招标工具，看不见 `pack-ship__plan`。

## 和 CLI / 应用的关系

| 面 | 命令 |
|----|------|
| 终端 TUI | `python -m packing_assistant.civil` |
| 一次性 | `python -m packing_assistant.civil "什么是 GST"` |
| 应用 | `python -m packing_assistant.civil app` |
| IDE | 本目录 MCP |
