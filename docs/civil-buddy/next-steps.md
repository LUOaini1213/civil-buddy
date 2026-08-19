# 下一步（推仓后）

对照 [github-directions-2026-08-17.md](github-directions-2026-08-17.md)。抽取并表（horizon B）已做，不再重开。

## 下一刀（按这个顺序）

1. **招标文件进矩阵** ✅ 2026-08-17  
   粘贴 / 多节选 / `.txt` `.md` `.csv` `.docx` `.xlsx` → 同一套矩阵 + P0。表格按行抄进 `exact_text`。`POST /api/tender/parse`（`sections`）· `/parse/file` · `/parse/files`。扫描 PDF 仍拒绝。验收：`python scripts/test_tender_ingest.py`。

2. **装柜 MCP 工具表** ✅ 2026-08-17  
   `pack-ship__list` / `pack-ship__plan` / `pack-ship__export` 可发现。利用率、`can_fit`、`mid50`、系固待办只抄本仓 solver；未接通写 `UNSPECIFIED`。`GET/POST /api/mcp/tools`（demo + gateway）。验收：`python scripts/test_mcp_surface.py`。

3. **成稿后再审一岗** ✅ 2026-08-17  
   技术标目录或应答草稿出来后，跑禁语/缺项对照矩阵（`scan_forbidden` 之外的 `tender.review.v1`）。不填业绩、不改 `can_fit`。`POST /api/tender/review`。验收：`python scripts/test_tender_review.py`。

4. **沙箱** ✅ 2026-08-17  
   应用层路径 + spawn 策略（非内核 jail）。允许写根；`.env` / secret / key 拒绝；通用 spawn 拒绝。验收：`python scripts/test_sandbox.py`。

5. **OTEL 大盘** ✅ 2026-08-17  
   `PACKING_OTEL=1` 文件导出 + `GET /api/otel/dashboard` 列 `run_id` / node / tool / duration。非夹具。验收：`python scripts/test_otel_dashboard.py`。

6. **默认面先理解再聊或跑** ✅ 2026-08-17  
   gateway `/` · `POST /api/turn`：提问 `chat` 不写盘；成稿 `run` 仍进现有矩阵。内部讨论 AI 草稿，不判定可投标。验收：`python scripts/test_understand.py`。

7. **66 岗同一套 chat / run** ✅ 2026-08-17  
   `GET /api/experts` + `POST /api/turn` 带 `expert_id`。每岗独有工具只在 run；高风险须确认句。验收：`python scripts/test_expert_turn.py`。

8. **每岗对照易标/pack-agent 长程规划** ✅ 2026-08-17  
   66 条独立规划 + 16 条车道。见 `docs/civil-buddy/post-horizon-2026-08-17.md`。验收：`python scripts/test_post_horizon.py`。

9. **P0 运行时内核** ✅ 2026-08-19  
   pack-ship 抄 `packing_summary`（断线 `UNSPECIFIED`）；`runtime/tool_engine.py` 鉴权/超时/熔断；`runtime/scheduler.py` 状态机 + `/api/runs/{id}`。验收：`python scripts/test_runtime_p0.py`。

10. **完整 Agent 循环 + 沙箱门** ✅ 2026-08-19  
    `runtime/agent_loop.py`：understand → Scheduler → ToolEngine；chat 不写盘；写盘/`spawn` 过 `sandbox.assert_write` / `request_spawn`。`POST /api/agent` · `GET /api/eval/live`（离线官方标题针，不抓 IRAS）。验收：`python scripts/test_agent_loop.py`。

11. **过夜空转（废止）**  
    定时评测环已停。现行完善规划：**[product-completion-plan.md](product-completion-plan.md)**（技术文档 / 知识库 / MCP / Skill，不定时限）。

平台内核见 [product-improvement-handbook.md](product-improvement-handbook.md)。岗独有写盘下一刀仍按 [post-horizon-2026-08-17.md](post-horizon-2026-08-17.md)。

## 有宿主再做

接上 Claude / Cursor / 本机 MCP 客户端后，再做 `kb://` 分页与订阅（horizon D）。本机无 `link.exe` 时，验收仍以 Python `GET /api/mcp/*` 为准。

## 不做

GeBIZ 递交、托管 200+ 柜型替换 solver、16 类知识库全量 embedding 季更、装箱评分离线循环、内核 Landlock/Seatbelt、以 Grafana/Jaeger 为唯一大盘。
