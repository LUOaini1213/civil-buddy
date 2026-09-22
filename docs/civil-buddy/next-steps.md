# 产品完成流水与当前验收

> 当前状态：**本地发布验收已完成，后续按用户试用反馈迭代**。本页编号是历史已做记录，不是新待办队列；权威状态见 [product-plan.md](product-plan.md) §7.2 / §11 / §15。设计 20 岗已按逐岗字段与 105 项回归完成；66 岗源码包已完成本地验收。

对照 [github-directions-2026-08-17.md](github-directions-2026-08-17.md)。抽取并表（horizon B）已做，不再重开。

## 已做流水（历史顺序）

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

22. **T031 interim 一岗（T031 批次完）** ✅ 2026-08-20  
    interim__measure 计量草表含开累/本期申报/监理审/业主核；无确认不编应付合价。主链头指针改为 **T032**（plan-master 先）。T032–T047 不得一行勾完。

23. **T032 plan-master 一岗** ✅ 2026-08-20  
    plan-master__network 固定 WBS｜紧前｜里程碑待填｜关键线路=待计算。不编持续天数。T032 批次未完：下一岗 **plan-lookahead**。不得把周月/资源一并勾完。

24. **岗独有收进 ToolEngine** ✅ 2026-08-20  
    66 岗 exclusive 按名 `register`。agent_loop / MCP `tools/call` 调 `survey__record` 等，不再拿 `write_deliverable` 冒充。chat 与兄弟岗 `permission_denied`。验收：`python scripts/test_exclusive_engine.py`。主链头指针仍是 **T032 · plan-lookahead**。

25. **API 会话槽装配** ✅ 2026-08-20  
    DeepSeek 无会话。`assemble_context` 每轮读/写 `session.summary`：项目名粘滞、P0 粘滞、压缩提示进 chat。`GET /api/context/{session_id}`。默认幕墙项目名不得盖槽。验收：`python scripts/test_memory_slot.py`。T032 指针不变。

26. **T032 plan-lookahead 一岗** ✅ 2026-08-20  
    plan-lookahead__week 出四周表；制约未清不得写入本周承诺。不编风速限值、不写可以复工。T032 批次未完：下一岗 **plan-resource**。不得把资源一并勾完。行业总判仍 **部分合格**。

27. **T032 plan-resource 一岗（T032 批次完）** ✅ 2026-08-20  
    plan-resource__peak 拆劳动力｜机具｜材料三表；无定额/需用计划数量待填。不写已满足施工需要、不把无证件设备列入进场。主链头指针改为 **T033**（lab-mix 先）。T033–T047 不得一行勾完。行业总判仍 **部分合格**。

28. **T033 lab-mix 一岗** ✅ 2026-08-20  
    lab-mix__report 四层目录（初步/基准/试验室/施工）；无试验数据则施工配比整节待填。不编 kg/m³。高风险须确认句。T033 批次未完：下一岗 **lab-sample**。不得把取样/台账一并勾完。行业总判仍 **部分合格**。

29. **T033 lab-sample 一岗** ✅ 2026-08-20  
    lab-sample__list 出类别｜部位｜见证人空｜升级路径；组数 [A001]。不编合格结论。高风险须确认句。T033 批次未完：下一岗 **lab-record**。行业总判仍 **部分合格**。

30. **T033 lab-record 一岗（T033 批次完）** ✅ 2026-08-20  
    lab-record__ledger 加报告编号待核｜仪器检定｜结论待填。不编报告号。主链头指针改为 **T034**（supervision 先）。T034–T047 不得一行勾完。行业总判仍 **部分合格**。

31. **T034 supervision 一岗（T034 批次完）** ✅ 2026-08-20  
    supervision__reply 来文复述｜拟办｜证据目录；暂停/复工只出目录，不签发复工。主链头指针改为 **T035**（safety-brief 先）。T035–T047 不得一行勾完。行业总判仍 **部分合格**。

32. **T035 safety-brief 一岗** ✅ 2026-08-20  
    safety-brief__talk 11 栏；毫米/电话 [A001]。高风险须确认句。T035 批次未完：下一岗 **quality**。不得把质量/环保/应急一并勾完。行业总判仍 **部分合格**。

33. **T035 quality 一岗** ✅ 2026-08-20  
    quality__lot 主控｜一般｜隐蔽三表，结果=未检。不给合格结论。T035 批次未完：下一岗 **env**。

34. **T035 env 一岗** ✅ 2026-08-20  
    env__list 扬尘/弃土/污水/夜间/市容五行，限值 UNSPECIFIED。T035 批次未完：下一岗 **emergency**。不得把应急一并勾完。行业总判仍 **部分合格**。

35. **T035 emergency 一岗（T035 批次完）** ✅ 2026-08-20  
    emergency__plan 综合目录+点名专项+演练表头；电话医院待填。不编响应分钟数。高风险须确认句。主链头指针改为 **T036**（equip 先；pack-ship 已富跳过）。T036–T047 不得一行勾完。行业总判仍 **部分合格**。

36. **T036 equip 一岗** ✅ 2026-08-20  
    equip__ledger 只抄用户设备名与已给证件；无证件不编进场结论。高风险须确认句。T036 批次未完：下一岗 **warehouse**。不得把仓管/现场料一并勾完。行业总判仍 **部分合格**。

37. **T036 warehouse 一岗** ✅ 2026-08-20  
    warehouse__log 按行抄收发原文；有数只抄、无数 TBD；无盘点不编盈亏。T036 批次未完：下一岗 **material-site**。不得把现场料一并勾完。行业总判仍 **部分合格**。

38. **T036 material-site 一岗（T036 批次完）** ✅ 2026-08-20  
    material-site__recon 按行抄应耗/领料/盘点；算不出节超则 TBD。无盘点不编盈亏。主链头指针改为 **T037**（proc-plan 先）。T037–T047 不得一行勾完。行业总判仍 **部分合格**。

39. **T037 proc-plan 一岗** ✅ 2026-08-20  
    proc-plan__schedule 先分甲供/甲指/自采再列表；无供方周期则提前期 UNSPECIFIED。金额门槛不默写。T037 批次未完：下一岗 **proc-compare**。不得把比价/供方一并勾完。行业总判仍 **部分合格**。

40. **T037 proc-compare 一岗** ✅ 2026-08-20  
    proc-compare__table 一行一家多列；无报价不编价；定商标待制度定；写盘后 procurement__scan_forbidden。T037 批次未完：下一岗 **proc-vendor**。不得把供方一并勾完。行业总判仍 **部分合格**。

41. **T037 proc-vendor 一岗（T037 批次完）** ✅ 2026-08-20  
    proc-vendor__eval 出准入｜考察｜短名单；分数/结论待核；禁止成交结论。不编证书号和业绩额。主链头指针改为 **T038**（finance-book 先）。T038–T047 不得一行勾完。行业总判仍 **部分合格**。

42. **T038 finance-book 一岗** ✅ 2026-08-20  
    finance-book__check 出报销勾选｜科目对照｜对账缺口；金额 [A001]。不编分录、不编盈亏。T038 批次未完：下一岗 **finance-fund**。不得把资金岗一并勾完。行业总判仍 **部分合格**。

43. **T038 finance-fund 一岗（T038 批次完）** ✅ 2026-08-20  
    finance-fund__plan 出收入/支出窗口；金额 TBD；不构成付款指令。无合同节点不编付款承诺。主链头指针改为 **T039**（worker-brief 先）。T039–T047 不得一行勾完。行业总判仍 **部分合格**。

44. **T039 worker-brief 一岗** ✅ 2026-08-20  
    worker-brief__talk 按 script 写三段口播；无尺寸不报毫米。不是书面交底签认件。T039 批次未完：下一岗 **pm-daily**。不得把日报一并勾完。行业总判仍 **部分合格**。

45. **T064 作业根 Office** ✅ 2026-08-20  
    有 markdown 表的岗 run 后另存 `.xlsx`（会话目录；若设 `CIVIL_JOB_ROOT` 再抄一份）。禁止默认 `D:\layout`。不是桌面壳、不是接管 Word 窗口。主链头指针仍 **T039 pm-daily**。行业总判仍 **部分合格**。

46. **T065 作业根直接读本机文件** ✅ 2026-08-20  
    授权 `CIVIL_JOB_ROOT` 后，run 自动抄夹内 xlsx/docx/csv/txt，不必再点上传。`GET /api/job` 列出已看到的文件。禁止 `D:\layout`、禁止全盘搜索。主链头指针仍 **T039 pm-daily**。行业总判仍 **部分合格**。

47. **T066 授权夹内改已有 Excel 草稿表** ✅ 2026-08-20  
    点名作业根里已有的 `.xlsx` 时，只写入 `CB草稿-*` 工作表，业主原表不动。不是 COM 接管正在打开的 Excel。主链头指针仍 **T039 pm-daily**。行业总判仍 **部分合格**。

48. **T067 本机桌面窗口** ✅ 2026-08-20  
    `scripts/civil-buddy-desktop.ps1` 起本机工作台并用 Edge/Chrome `--app` 开窗口。不是腾讯桌面壳、不是 IM 遥控。禁止 `D:\layout`。主链头指针仍 **T039 pm-daily**。行业总判仍 **部分合格**。

49. **T068 可下载试用** ✅ 2026-08-20  
    历史 T068 记录已由 2026-09-12 的 Python 源码分发包取代：MIT LICENSE、启动器与依赖安装、无 Key 本地起草；[TRY.md](../../TRY.md) 写明安装与使用边界。旧 Rust exe 不代表当前 Python 工作台；本轮未发布 GitHub Release。主链头指针仍 **T039 pm-daily**。行业总判仍 **部分合格**。

50. **T039 pm-daily 一岗（T039 批次完）** ✅ 2026-08-20  
    pm-daily__log 出天气待填｜部位｜形象（不编百分比）｜出勤待填。不是监理日志、不是施工日志签认件。主链头指针改为 **T040**（hr-recruit 先）。T040–T047 不得一行勾完。行业总判仍 **部分合格**。

51. **H 块插入主链（08-25 联网评估）** 2026-08-25  
    评测后不仿 Codex Rust 壳。主链头指针改为 **H1**（目录预算闸）→ H2 HITL → H3 MCP 假宿主 → H4 skill 来源可见 → 再回 T040。H5 模型隐式选用延期。行业总判仍 **部分合格**。

52. **H1 技能目录预算闸** ✅ 2026-08-25  
    `catalog_preamble` / `format_catalog_listing` 超 8000 字先缩短 description 再省略尾部。`civil skills` 与 `/skills` 走同一函数。`agent_loop` 与路由器 prompt 不灌 66 份 SOP。验收：`python scripts/test_codex_expert_skills.py` · `python scripts/test_civil_codex.py`。主链头指针改为 **H2**。行业总判仍 **部分合格**。

53. **H2 HITL T013 收口** ✅ 2026-08-25  
    `high_risk_unconfirmed` 统一 agent_loop / exclusive / write_deliverable。全部 high 岗未确认 0 份稿；chat 仍放行。验收：`python scripts/test_civil_codex.py`。

54. **H3 MCP 假宿主联测** ✅ 2026-08-25  
    `scripts/test_mcp_host_client.py` 对 `civil mcp --pack construction` 发 initialize / tools/list / tools/call search_kb。无 tender.parse、无 pack-ship__plan。

55. **H4 面可见 skill 来源** ✅ 2026-08-25  
    工作台回复旁标 `$id · 显式|规则选用|未点名`。TUI `/status` 同样。主链头指针改回 **T040**（hr-recruit）。行业总判仍 **部分合格**。

56. **MW1 赛道 1 Agent Middleware** ✅ 2026-08-25  
    深做两层：策略引擎（拒绝弹原因）+ 失败恢复（timeout→retry→UNSPECIFIED 审计链）。现场四拍：下单 → 越权 → 降级 → 成本熔断。`npm run check` 过。主链头指针仍 **T040**。

57. **人改口 2026-08-25**  
    赛道 1 **完全合格**（track1-qualified.md）。内部起草搭子 **合格**。签认/可投标/可开工仍 **不合格**。08-17「总判：部分合格。」历史句不改。

58. **联网复核官方口径** 日志 2026-08-25  
    IRAS 仍页述 9%；Fire Code 仍 2023；CTU 仍 2014 非强制；GeBIZ 仍是门户；APPBCA-2026-12 仍是 2026-10-01 起 GFA≥5,000 m²。BCA site records 标题未改。MOM FCF 广告 14 日只作 T040 旁证。**不改** 08-17 历史总判句。主链头指针仍 **T040 hr-recruit**。签认/可投标/可开工仍不合格。

59. **civil serve App Server** ✅  
    JSON-RPC `initialize` / `thread/start` / `turn/start` 跑本仓 harness，不是 openai/codex 二进制。无 Cloud、无通用 shell。验收：`python scripts/test_civil_codex.py`。主链头指针仍 **T040 hr-recruit**。

60. **T040 hr-recruit 一岗** ✅ 2026-08-28  
    hr-recruit__brief 出职责｜任职｜面试问法；薪资仅当用户给数才抄，否则待填不编市场带宽。chat 不写盘。兄弟岗调 hr-recruit__brief 拒绝。主链头指针仍 **T040**（下一岗 hr-labor）。T040 其余岗不得一行勾完。行业总判仍 **部分合格**。

61. **K4 hr-labor 岗库** ✅ 2026-08-28  
    劳动关系 README 字段表；faq 补 SG（Employment Act / KETs / contract of service / TADM / 无 nationwide minimum wage）；outline 补 SG 分表。2026-08-28 打开 MOM *About the Employment Act*（更 2026-07-14）与中国政府网《保障农民工工资支付条例》。检索闸：`search_kb(hr-labor)` 命中本岗、看不见 hr-recruit。**不勾** hr-labor 独有写盘。主链头指针仍 **T040**（hr-labor__check）。K4 其余岗不得一行勾完。行业总判仍 **部分合格**。

62. **K4 66 岗内容闸** ✅ 2026-08-28  
    每岗 faq≥5、README 字段表、outline 缺数栏；`search_kb`/`list_kb` 命中本岗私库、不见兄弟私库。验收：`python scripts/test_kb_k4_depth.py`。K3 隔离一并收口。**不勾** 独有写盘，主链头指针仍 **T040 hr-labor**。不做 16 类 embedding 季更。行业总判仍 **部分合格**。

63. **T040 hr-labor** ✅ 2026-09-12：合同类型分表、多人记录隔离，补偿 [A001]；`test_hr_drafts.py`。
64. **T040 hr-train** ✅ 2026-09-12：三层课题及签到空栏，用户资料进入真实 Excel；同上。
65. **T041 admin-doc** ✅ 2026-09-12：请示、纪要、用印专用栏，逐条决议不借期限；`test_admin_drafts.py`。
66. **T041 admin-office** ✅ 2026-09-12：场地、议程、与会、资料及后勤表，决定栏空；同上。
67. **T042 it-ops** ✅ 2026-09-12：系统权限矩阵、升级路径、凭据不进稿；`test_it_drafts.py`。
68. **T042 it-data** ✅ 2026-09-12：逐系统恢复目标、备份及演练记录；不宣称已执行；同上。
69. **T042 it-app** ✅ 2026-09-12：角色、流程、功能、验收分条，过滤接口凭据；同上。
70. **T043 bim-coord** ✅ 2026-09-12：模型、问题及提资接口独立记录，不假装碰撞扫描；`test_bim_drafts.py`。
71. **T043 bim-qto** ✅ 2026-09-12：过滤/扣减/来源校核，用户数量明示才抄；同上。
72. **T043 bim-deliver** ✅ 2026-09-12：LOD、命名、拆分、交付检查表，核验保持未知；同上。

73. **T044 architecture** ✅ 2026-09-12：单体总平面、分区面积与功能、消防分区及疏散用户值、无障碍、竖向、节能和专业接口；缺面积、宽度不推算；`scripts/test_design_basic_drafts.py`。
74. **T044 structure** ✅ 2026-09-12：单体体系、构件荷载与组合、材料、基础输入、抗震资料及复核清单；承载力、配筋和截面计算结果保持 UNSPECIFIED；`scripts/test_design_basic_drafts.py`。
75. **T044 geotech** ✅ 2026-09-12：孔号与分层、c/φ/水位和来源、勘探试验、地基比选、监测及提资；孔层缺项不借值，不替正式勘察报告；`scripts/test_design_basic_drafts.py`。
76. **T044 facade** ✅ 2026-09-12：幕墙体系、风压与分格、预埋后锚固、气密水密变位、防火防雷、加工检测和维护接口；不选厚度或签验收结论；`scripts/test_design_basic_drafts.py`。
77. **T045 plumbing** ✅ 2026-09-12：系统水源/水压、市政接驳、室内出户及井标高、给排水分区、雨水回用、消防水资料；管径和选泵计算待核；`scripts/test_design_services_drafts.py`。
78. **T045 hvac** ✅ 2026-09-12：室内外参数、逐时冷热负荷、风水系统、防排烟联锁、机房竖井与消声保温；主机、风管及排烟量不代算；`scripts/test_design_services_drafts.py`。
79. **T045 electrical** ✅ 2026-09-12：市政电源、容量和负荷系数、变配电用户方案、照明、防雷接地、线路及消防/弱电接口；不选变压器或电缆；`scripts/test_design_services_drafts.py`。
80. **T045 fire-protect** ✅ 2026-09-12：救援条件、防火分区、疏散避难、消防水、防排烟、报警联动、电气及报审目录；不作审图通过或放行结论；`scripts/test_design_services_drafts.py`。
81. **T045 steel** ✅ 2026-09-12：构件体系与跨度、荷载、材料规格、螺栓焊缝、稳定支撑、防腐防火及加工安装接口；截面和连接计算未执行；`scripts/test_design_services_drafts.py`。
82. **T046 landscape** ✅ 2026-09-12：软硬分区、竖向灌排、铺装及苗木规格数量、顶板覆土、室外设施和消防交通接口；未给苗木表不选规格；`scripts/test_design_specialties_drafts.py`。
83. **T046 interior** ✅ 2026-09-12：房间地墙顶及隔墙、防水材料厚度上翻、防潮隔声、门窗五金、天花开洞和外窗收口；只抄用户样板资料；`scripts/test_design_specialties_drafts.py`。
84. **T046 intel-weak** ✅ 2026-09-12：子系统范围、点数及品牌、桥架路由、点位关联、供电 UPS 接地与消防网络接口；不编品牌或布点；`scripts/test_design_specialties_drafts.py`。
85. **T046 civil-defense** ✅ 2026-09-12：防护单元等级及平战功能、口部/设备归属、通风滤毒超压、给排水和转换接口；不互换 CN/SG 概念或代审图；`scripts/test_design_specialties_drafts.py`。
86. **T046 hydraulic** ✅ 2026-09-12：水工对象、水文断面和地勘孔、堤防护岸、闸泵用户参数、导流度汛和观测；无水文地质不选尺寸或流量；`scripts/test_design_specialties_drafts.py`。
87. **T047 port** ✅ 2026-09-12：泊位船型、水位波浪潮流、结构比选、前沿尺度、航道回旋水域、装卸堆场与水利接口；不计算桩长或靠船力；`scripts/test_design_infrastructure_drafts.py`。
88. **T047 municipal** ✅ 2026-09-12：路段桩号、平纵横断、路面结构、排水标高、管线权属及导改接口；不拆算车道宽或选路面厚度；`scripts/test_design_infrastructure_drafts.py`。
89. **T047 bridge** ✅ 2026-09-12：桥位跨径及桥型比较、上下部结构、支座桥面、水文通航抗震及施工接口；不锁最优桥型或计算钢束桩长；`scripts/test_design_infrastructure_drafts.py`。
90. **T047 tunnel** ✅ 2026-09-12：用途净空、工法地层、开挖支护、防水接缝、监控量测、洞口及机电防灾接口；支护参数和监测阈值待核；`scripts/test_design_infrastructure_drafts.py`。
91. **T047 traffic** ✅ 2026-09-12：交通影响/施工导改任务、调查来源与独立情景、组织及标志信号、仿真资料和指标；未运行仿真或优化配时；`scripts/test_design_infrastructure_drafts.py`。
92. **T047 design-coord** ✅ 2026-09-12：图纸版本、会审问题、提资责任期限、变更记录、逐条决议和闭环证据；不代签发，不内置审批面积阈值；`scripts/test_design_infrastructure_drafts.py`。

设计新增 20 岗均有各自章节、提资及缺项表，L2 为 66/66；设计四组 105 项回归及统一检查 40/40 通过，T044–T047 已逐岗认领完成。新稿规范引用来自用户资料、未核验，CN/SG/EU 依据与接口分栏；本轮不改变既有法规范事实或历史行业总判。

平台内核见 [product-improvement-handbook.md](product-improvement-handbook.md)。当前主链状态按 [product-plan.md](product-plan.md) §11 / §15：**本地发布验收已完成，后续按用户试用反馈迭代**。0.5.0-preview 已基于 66 岗源码完成解压复验；尚未发布 GitHub Release。没有新设虚构任务号；延期项保持延期。

93. **0.5.0-preview 本地发布验收** ✅ 2026-09-12：隔离依赖、解压模块来源、无 Key 聊天、66 岗起草、CSV/DOCX/XLSX 表格上传→实际 Markdown/Excel 下载与恢复、非法确认 HTTP 422、重启及进程清理通过。开发仓库验收入口 `scripts/smoke_workbench_release.py --all-experts`；zip 散列与 `acceptance.json` 另存包外，不宣称 GitHub 已发布。

## 有宿主再做

接上 Claude / Cursor / 本机 MCP 客户端后，再做 `kb://` 分页与订阅（horizon D）。本机无 `link.exe` 时，验收仍以 Python `GET /api/mcp/*` 为准。

## 不做

GeBIZ 递交、托管 200+ 柜型替换 solver、16 类知识库全量 embedding 季更、装箱评分离线循环、内核 Landlock/Seatbelt、以 Grafana/Jaeger 为唯一大盘。
