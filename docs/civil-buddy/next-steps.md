# 下一步（推仓后）

对照 [github-directions-2026-08-17.md](github-directions-2026-08-17.md)。抽取并表（horizon B）已做，不再重开。

## 下一刀（按这个顺序）

1. **招标文件进矩阵** ✅ 2026-08-17  
   粘贴 / 多节选 / `.txt` `.md` `.csv` `.docx` `.xlsx` → 同一套矩阵 + P0。表格按行抄进 `exact_text`。`POST /api/tender/parse`（`sections`）· `/parse/file` · `/parse/files`。扫描 PDF 仍拒绝。验收：`python scripts/test_tender_ingest.py`。

2. **装柜 MCP 工具表**  
   在 `pack-ship` / `civil-mcp` 上拆出可发现的 list / plan / export（利用率、can_fit、mid50、系固待办）。数字只抄本仓 solver；未接通写 `UNSPECIFIED`。

3. **成稿后再审一岗**  
   技术标目录或应答草稿出来后，跑一次禁语/缺项对照矩阵（写盘 `scan_forbidden` 之外的审查步）。不填业绩、不改 `can_fit`。

## 有宿主再做

接上 Claude / Cursor / 本机 MCP 客户端后，再做 `kb://` 分页与订阅（horizon D）。本机无 `link.exe` 时，验收仍以 Python `GET /api/mcp/*` 为准。

## 不做

GeBIZ 递交、托管 200+ 柜型替换 solver、16 类知识库全量 embedding 季更、沙箱 / 通用 spawn / OTEL、装箱评分离线循环。
