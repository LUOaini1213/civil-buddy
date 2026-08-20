# MCP

Skill 是 SOP。MCP 是动作。不要把装箱 skill 名（`bin3d.pack`）当成 MCP tool。

对照 MCP 2026-07-28：`tools` · `resources`（`kb://`）· `prompts`。

## stdio（Host 用这个）

无 MSVC 时用 Python（本机已跑 `scripts/test_mcp_stdio.py`）：

```powershell
cd C:\Users\LW\civil-buddy
python demo/mcp_stdio.py --pack bid
python demo/mcp_stdio.py --pack construction
python demo/mcp_stdio.py --expert pack-ship
```

有 Rust 二进制时：

```powershell
.\workbench\target\release\civil-mcp.exe --pack bid
```

`--pack` = 大类（如 `bid` `construction` `plant`）。`--expert` = 岗 id。pack=bid 的 `tools/list` 含 KB + 招标，**不含** `pack-ship__plan`。

样例配置：[mcp-host.example.toml](mcp-host.example.toml)。16 个 pack 都有可复制注释行，不要求一次全挂。

### Grok（最小）

把 `mcp-host.example.toml` 里 `civil-construction` 三行贴进 `~/.grok/config.toml` 的 MCP 段。工作目录为仓库根。本机已跑：`python demo/mcp_stdio.py --pack construction` 的 `tools/list` 含 `construction__scheme_draft`，不含 `pack-ship__plan`。

### Cursor（最小）

`.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "civil-construction": {
      "command": "python",
      "args": ["demo/mcp_stdio.py", "--pack", "construction"],
      "cwd": "C:\\\\Users\\\\LW\\\\civil-buddy"
    }
  }
}
```

本机已跑同一命令。不要把 `DEEPSEEK_API_KEY` 写进该文件。

## HTTP（本机网关 / 工作台）

| 方法 | Python 工作台 :8765 | 网关 :8000 |
|------|---------------------|------------|
| capabilities | `GET /api/mcp/capabilities` | （pack-ship 子集） |
| resources | `GET /api/mcp/resources?expert_id=` | — |
| prompts | `GET /api/mcp/prompts?expert_id=` | — |
| tools | `GET /api/mcp/tools?expert_id=` | `GET /api/mcp/tools` |
| call | `POST /api/mcp/tools/call` | `POST /api/mcp/tools/call` |

## 第一批 tools

| name | 谁可见 |
|------|--------|
| `search_kb` `read_kb` `list_kb` | 当前层 |
| `write_deliverable` | run；chat 拒绝 |
| `tender.parse` `tender.review` | bid 大类 / bid-parse |
| `bid-parse__extract` 等独有 | 仅该 `expert_id` |
| `pack-ship__list/plan/export/health` | 仅 pack-ship / plant |
| `*__scan_forbidden` | 本大类 |

`kb://` 越权返回「拒绝：…」，不装成空库。chat 调写盘 → `permission_denied`。xyz 只抄 solver 或 `UNSPECIFIED`。
