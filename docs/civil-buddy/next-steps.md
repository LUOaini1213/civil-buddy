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
    定时评测环已停。全量规划：**[product-plan.md](product-plan.md)**。切片：[product-completion-plan.md](product-completion-plan.md)。

12. **D1 + MCP + 施工 skill 路径** ✅ 2026-08-19  
    五篇说明书；`demo/mcp_stdio.py`；pack=bid 的 tools 含 KB/招标不含 pack-ship；construction 十一章接 turn。验收：`test_docs_completion.py` · `test_mcp_stdio.py` · `test_construction_skill_path.py`。

13. **T001 / K1 66 岗四件套闸** ✅ 2026-08-19  
    补 `demo/kb/construction/construction/outline.md`、`demo/kb/construction/method-hazard/outline.md`（短指针，不改判定卡）。`scripts/test_kb_schema.py` 遍历 seed 66 岗，缺 README/faq/outline/web-knowledge 即红。demo `catalog_seed` 补上漏掉的 pack-ship，工作台 `/api/catalog` 列出 66。

14. **T021 `--pack construction` 工具隔离** ✅ 2026-08-20  
    stdio tools 含 scheme_draft/scan，不含 tender.parse / bid-parse__extract / pack-ship__plan / method-hazard__judge_hazard；prompts 只有 `civil.construction.scheme`。

15. **T023 kb:// 跨大类拒绝** ✅ 2026-08-20  
    bid-parse 读 `kb://construction/method-hazard/outline.md` 拒绝句。`POST /api/mcp/resources/read`。验收：`python scripts/test_mcp_surface.py`。

16. **T003 eval/live 五针收口 company 页** ✅ 2026-08-20  
    GST 9% / Fire Code 2023 / CTU 2014 非强制 / GeBIZ≠评分 / APPBCA-2026-12 只读 `demo/kb/company/web-portals.md`。验收：`python scripts/test_agent_loop.py`。

17. **平台刀 T007–T062（不含 T030–T047 岗批次）** ✅ 2026-08-20  
    T007/T008 岗 GST 9% 与 CORENET 反例扫描；T002 危大判定书默认 SG WSH/PTW；T004 税务日历 9% 空栏；T006 cost takeoff UNSPECIFIED；T005 fill_scheme / `docx_pending`；T014 agent_loop 读 handoff；T011 parse/file/files 走 ToolEngine（chat 拒写）；T010 `session.summary`；T020 16-pack Host 样例；T024 Grok/Cursor 最小配置；T050 PDF 拒绝句；T052 同 session 抄 can_fit；T062 刀后快闸。主链头指针改为 **T030**。T030–T047 不得一行勾完。行业总判仍 **部分合格**。

18. **T030 construction 收尾 survey + dispatch** ✅ 2026-08-20  
    survey__record 只抄已给点号/坐标（会话附件+原文），都无则表头+[A001]。dispatch__daily 按 outline 十一章落表头；敏感作业只列名，判定交 method-hazard。chat 仍不写盘。验收：`python scripts/test_expert_turn.py` · `cargo test --test workbench survey_record dispatch_daily`。主链头指针改为 **T031**。T031–T047 不得一行勾完。

19. **T031 variation 一岗** ✅ 2026-08-20  
    variation__form 先判定文种再出事实|依据|签认空栏；无变更编号则依据待填。金额 TBD。chat 仍不写盘。T031 批次未完：下一岗 **claim**。不得把 claim/subcontract/interim 一并勾完。行业总判仍 **部分合格**。

20. **T031 claim 一岗** ✅ 2026-08-20  
    claim__notice 出意向栏+证据行+条款原文待贴；工期金额 TBD。不把未送达意向假装已发出。T031 批次未完：下一岗 **subcontract**。不得把 subcontract/interim 一并勾完。

21. **T031 subcontract 一岗** ✅ 2026-08-20  
    subcontract__sheet 按行抄细目；无总包/业主确认金额 TBD。应付人工费与应付分包工程款分列。T031 批次未完：下一岗 **interim**。

平台内核见 [product-improvement-handbook.md](product-improvement-handbook.md)。岗独有写盘下一刀仍按 [post-horizon-2026-08-17.md](post-horizon-2026-08-17.md)。

## 有宿主再做

接上 Claude / Cursor / 本机 MCP 客户端后，再做 `kb://` 分页与订阅（horizon D）。本机无 `link.exe` 时，验收仍以 Python `GET /api/mcp/*` 为准。

## 不做

GeBIZ 递交、托管 200+ 柜型替换 solver、16 类知识库全量 embedding 季更、装箱评分离线循环、内核 Landlock/Seatbelt、以 Grafana/Jaeger 为唯一大盘。
