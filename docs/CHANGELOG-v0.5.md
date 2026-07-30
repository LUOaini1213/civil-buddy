# CHANGELOG · v0.5.0+

## v0.6.4 · Agent 知识库（可检索 + 窄接 + 分卡）

| 项 | 说明 |
|----|------|
| `knowledge_base/` | 01–07 规则/工具/轨迹 T1–T8/多Agent/比赛 |
| `knowledge.search` | 关键词检索，不返回坐标 |
| `agent_kb_bindings.yaml` | 9 Agent + 附属角色路径 allowlist |
| `verdict` | 总览裁决横幅（不必开 PDF） |
| CoG R4 | 默认 mid50≥60%，刚性平移+swap+slide |
| 回归 | `test_search_knowledge` · `test_kb_bindings` · `test_mid50_cog` · scorecard |

**Harness**：→ **0.6.4**

---

# 历史 · v0.5.0

**Harness**：0.4.0 → **0.5.0**  
主题：像真 Agent 产品（流式 + 可回放 + HITL 密度）+ 可交付 OSS 壳

## v0.5.x · 3D 堆码（行业对齐）

| 优先级 | 项 | 实现 |
|--------|-----|------|
| **P0** | 可叠优先叠高 + 限高/限层 | `PackPolicy.prefer_stack`；`try_place` 优先上层 EP；`max_stack_height_mm` / `max_stack_layers` |
| **P0** | 不误杀可叠箱 | `prefer_bottom_weight_kg` 默认 **2000**（原 800）；可叠箱不进条带 `_is_frame_like` |
| **P1** | 支撑/稳定 | `_support_area_ratio` ≥ `support_ratio_min`(0.55)；下层须 `stackable`；重上轻下软罚分 |
| **P1** | 箱间绑扎余量 20–50mm | `clearance_mm` 默认 30；同层水平 gap，上下堆叠允许贴顶 |
| **P1** | **CTU 纵中 60/50** | `cog_aware`：系统质量 mid50 + 中段锚点；去掉强贴门端 `px` 主导 |
| **P2** | multi-start **CoG 选优** | 叠高/地面/重底序；fit→柜数→balance→mid50→long→height→空隙→util→stack |
| **P1** | 四点/底心支撑 + 下层承重 | `corner_support`；`max_top_load_kg`；export_strict 抬支撑比 |
| **P1** | 空隙/集中载/可叠未叠 | `layout_quality` + risk `VOID_GAP_15CM` / `CONCENTRATED_LOAD` |
| **P0** | **export_strict 出运门禁** | mid50&lt;60% / 过高重心 → block；evaluator replan |

- API：`packing_options.export_strict / cog_aware / corner_support / multi_start`  
- 指标：`stacking` + `cog` + `layout_quality`；前端 COG mid50 + 堆码/空隙卡  
- 冒烟：`python scripts/test_stack_prefer.py` · `python scripts/test_full_optimize.py`

## v0.5.x · Agent 8 条（编排/HITL/合规工件）

| # | 项 | 模块 |
|---|-----|------|
| 1 | PackingPlan 工件 `packing.plan.v1` | `packing_plan.py` |
| 2 | HITL 策略门 export_strict/CoG/OVER_N0 | `hitl_gates.py` |
| 3 | 有界 replan critic（只改 packing_options） | `agents/replan_critic.py` + harness |
| 4 | Skills 契约 fail-loud | `skills_registry.py` + `docs/skills/*` |
| 5 | 装柜步骤工单 | `tools/load_sequence.py` |
| 6 | VGM Method2 草稿（须人签） | `tools/vgm_draft.py` |
| 7 | 计划 diff 叙事 | `tools/plan_diff.py` |
| 8 | 黄金回归 | `scripts/test_agent_p0_eight.py` |

`finalize` / `public_response` 已挂载上述工件。

## v0.5.x · P0/P1/P2 全链路

| 层级 | 交付 |
|------|------|
| **P0 NL What-if** | `nl_whatif.py` · `nl_query` 锁柜/去超长/仅铁 |
| **P0 score_plan** | `score_plan.py` · what-if `after_is_better` / 更优 |
| **P0 导出** | `export_pack.py` · POR+绑扎 xlsx · `POST /api/export/shipment` |
| **P0 eval** | `eval_harness.py` · tiny/20t · `scripts/eval_harness_cli.py` · CI |
| **P1 replan 日志** | `replan_log.py` → `output/runs/<id>/replan_log.json` |
| **P1 场景示例 preset** | `business_presets.py` · 仅示例（锁1柜/锁2柜/满载）· `/api/business-presets`；龙申/工厂会里案不写死为产品业务 |

## v0.6.0 · 大 Team ⊃ A/B + NL IntentSpec（完整架构重构）

| 项 | 说明 |
|----|------|
| **组织** | 大 Team（编排/HITL/critic/收口）包小 Team A 成箱 + 小 Team B 拼柜 |
| **Agent** | NL 通用入口 → `IntentSpec` → 多工具；非线路写死 |
| **模块** | `intent_spec.py` · `tool_registry.py` · `teams/*` · `docs/ARCHITECTURE.md` |
| **API** | `GET /api/architecture` · `GET /api/tools` · `POST /api/intent` |
| **主路径** | `run_agent_pipeline` → `teams.big_team.iter_big_team_run` |
| **版本** | harness `0.6.0` |

## v0.6.1 · LLM tool-call · 三层组织图 · A/B resume

| 项 | 说明 |
|----|------|
| **LLM 多轮** | `agent_loop.py`；`agent_mode=llm_toolcall\|auto`；白名单工具；无 Key 走 policy |
| **前端** | `index.html` 三层组织图（大 Team ⊃ A + B + HITL） |
| **Resume** | `graph_resume.py`；`GET /api/resume/{id}` · `POST .../team-b`；confirm 走子图 B |

## v0.6.2 · 影子评测 · KPI · TMS 订舱 · CI workflow

| 项 | 说明 |
|----|------|
| **影子评测** | `eval_workteams.py` · `scripts/eval_workteams_cli.py` · `POST /api/eval/workteams` |
| **KPI** | `workteam_kpi.py` · 覆盖率/非法工具/replan · `GET /api/kpi/{session}` |
| **TMS** | `tms_booking.py` · preview/submit · stub 或 `PACKING_TMS_URL` |
| **CI** | `.github/workflows/ci.yml` 对齐 `big_team_a_b` + workteams + TMS |

## v0.6.3 · 比赛收尾 slice（comp）

| 项 | 说明 |
|----|------|
| **标准铁架默认** | 重钢走标准箱库；`validate_boxes_against_kb` 命中率 |
| **超货载** | `cargo_feasibility` + mass_split + critic→box_scheme |
| **锚点** | `t80_long_mix_s297883` 重生；`test_anchor_t80_long_mix.py` |
| **Reflect 轨迹** | agent_steps plan/act/observe/reflect |
| **HITL** | 标准箱架卡片；`test_hitl_resume_competition.py` 3 case 磁盘续跑 |
| **booking 单测** | `test_booking_volume_metrics.py` 双口径 |
| **Phase0** | 权重+30 case 基线；`competition_smoke.ps1` / 评委脚本 |
| **tag** | 建议 `v0.6.3-comp` |

## v0.6.2 · repo hygiene（同日）

| 项 | 说明 |
|----|------|
| **根目录** | PDF/xlsx/png → `data/samples/`；bat → `scripts/win/` |
| **output/** | 整目录 gitignore，仅保留 `.gitkeep`（约 -68k 行垃圾出仓） |
| **docs** | `research/` · `archive/` · `docs/README.md` 索引 |
| **scripts** | `scripts/README.md`；`scripts/dev/` 与 `_*.py` 不入仓 |
| **README** | 仅 v0.6 架构叙事，去掉新旧混写 |
| **commit** | `fd5e51f` chore: repo hygiene |
| **P1 检查表** | `pre_ship_checklist.py` · `/api/checklist` |
| **P1 3D 垫梁色** | scene3d `pad_beam` 红色 |
| **P2 骨架** | VGM dry-run · evidence 索引 · 运价占位 · tip/slide 启发式 |

验收：`python scripts/test_p0_p1_p2_full.py` · `python scripts/eval_harness_cli.py`

## v0.5.x · 偏好档 · POR 单 · What-if 应用

| 项 | 说明 |
|----|------|
| **profiles** | `packing_profiles.py` · `GET /api/profiles` · `POST /api/pipeline/profile` |
| **POR 装柜单** | `por_manifest.v1` 按料号/柜汇总 · finalize + 前端表 |
| **What-if 应用** | `POST /api/whatif/apply` 写回主 session |
| **空隙坐标** | gap_samples 含 `x_m`/`x_mm`，侧视图真实位置标橙带 |
| **验收** | `scripts/test_continue_improve.py` |

## v0.5.x · What-if + 图标注 + CI

| 项 | 说明 |
|----|------|
| **What-if** | `POST /api/whatif` · `GET /api/whatif/scenarios` · `packing_assistant/whatif.py` |
| **plan_diff** | N0 / mid50 / lat / ship_ok 前后对比叙事 |
| **侧视图** | 垫梁红框 + 空隙橙色带（secure_work_order） |
| **前端** | What-if 面板 · 双口径 N0 vs 3D 用柜文案 |
| **CI** | single_team + whatif + auto_mode；有 t80 物料则跑 P0 |

验收：`python scripts/test_whatif_accept.py`

## v0.5.x · 单 Team 有界闭环

| 项 | 说明 |
|----|------|
| **产品口径** | **1 个 Team** 闭环，不再表述为「A 线性 + B 另闭环」 |
| bootstrap | 主控→材料→结构→成箱→HITL |
| 闭环体 | 规划→装载→评估（内环≤3）→风险（外环≤2）；成箱打回仍在同 Team |
| 状态 | `team_mode=single_closed_loop` · `team_loop_round` · phase 仍兼容 `team_b_running` |
| critic | 文案改为「单Team闭环」；只改 options/柜数/路由 |

## v0.5.x · P1 产品与体验

| 项 | 说明 |
|----|------|
| **分柜 mid50 表** | `packing_plan.per_cabin_cog` + 前端表格（绿/黄/红） |
| **R0–R4 管线** | `packing_plan.r_pipeline` before→after；前端芯片流 |
| **绑扎/空隙工单** | `secure_work_order.v1`：气囊/木方/分堆加固；**不拦 ship_ok** |
| **集中载荷 0.25P** | `layout_quality` + 垫梁提示；risk `PAD_BEAM_025P` medium 不 block |
| **API** | `public_response` 暴露 `secure_work_order` / `per_cabin_cog` / `r_pipeline` |

冒烟：`python scripts/test_p1_secure_ui_artifacts.py`

## v0.5.x · P0 合规（LNS / 配额 / 横偏）

| # | 项 | 实现 |
|---|-----|------|
| 1 | **分柜 LNS mid50** | `cog_lns.py`：mid50&lt;target 的柜可多柜迭代；重货中段→轻货回填→两端轻货最后 |
| 2 | **装载重量配额** | `bin3d`：`cog_aware` 多柜时 **先于** 网格/条带按重均分，柜内重货先装 + 中段 EP |
| 3 | **横偏修理** | `cog_lateral.py`：半柜镜像 + **左右质量对换** + y 条带，取 lat 最优 |
| 4 | **multi_start 裁剪** | &gt;120 件仅 default+mid_heavy；&gt;60 件至多 3 候选 |

**验收 t80**（`scripts/test_p0_cog_t80.py`）：worst mid50≥0.55，lat≤0.08，can_fit + ship_ok  
实测示例：mid50≈0.62 / lat≈0.04 / ~20s / multi_start_n=2

## v0.5.x · Agent 自动策略（产品核）

| 项 | 说明 |
|----|------|
| **crate 直通自动识别** | 叠层架/铁件架/note 含 crate·factory_stack，或 ≥70% 行已是柜级外廓 → 禁止标准箱二次撑大 |
| **薄板自动 dense** | H≤80mm 片料占多数 → `dense_mode` + 关 `standard_boxes`（防 4/6m 空心铁架） |
| **`ship_ok` 贯通** | `risk_report.ship_ok` + state.`ship_ok`（PASS/WARN 且 can_fit） |
| **底面积别名** | loader 写 `floor_utilization` ← `floor_utilization_avg` |
| **半柜空洞软 replan** | can_fit 但 outer&lt;30% & book&lt;25% & wt&lt;45% → critic densify+叠高一轮 |
| **预算锁柜** | `lock_max_containers`：replan 不加柜 |

冒烟：`python scripts/test_agent_auto_mode.py`

## v0.5.x · 会里装柜（8/17 龙申 + 8/25 工厂）

| 项 | 说明 |
|----|------|
| 瓦楞 BOM0019 密装 | `2200×1100×1100` ×140件/架；1 柜可装全量密装架+铁件拼柜 |
| `lock_max_containers` | replan 预算锁柜：不加柜，改密装/叠高/`cog_rebalance` |
| 会里出图脚本 | `scripts/run_meeting_aug_agent_viz.py` → `run_agent_pipeline` 闭环 |
| 龙申 1 柜实测 | 外廓 **51%** / 重量 **68%** / can_fit（相对旧 39%/55% 提升） |
| 工厂第一批 | 贪心 + 2 柜 fit 试装；重料子集常 **1 柜重量~72%**，预算 2 柜留余量 |

产物：`output/meeting_aug_ship/agent_viz/`

## v0.5.x · LNS / 配额 / 横偏

- **LNS** `tools/cog_lns.py`：worst_mid50 柜销毁重装（重货中段）  
- **多柜配额**：`pack_items` 重量均分到柜 + 柜内重货先装  
- **横偏** `tools/cog_lateral.py`：左右半柜交换 + y 条带靠中  
- 冒烟：`python scripts/test_lns_balance_lat.py`

## v0.5.x · R2 条带 + 出运停损

- **R2** `tools/cog_slab.py`：纵向条带按质量重排靠中（Davies 墙交换简化）  
- **R3** 轻量：再跑一轮 R4 强制修最差柜  
- **停损**：mid50≥40% 可出运；≥55% 不再因 mid50 空转 replan；0.40–0.55 最多软 replan 1 轮  
- 管道：`R0/R1 → R2 → R4 → R3 → R0/R1`  
- 冒烟：`python scripts/test_r2_slab_stop.py`

## v0.5.x · R0/R1 完整

- **R0** `validate_cog_r0`：每柜 mid50/纵偏/横偏/竖向门禁 + 最差柜  
- **R1a** 刚性平移至质量中心（min 1mm，mid50 不下降才接受）  
- **R1b** 横向镜像修左右偏心  
- 管道：`apply_r0_r1` → R4 → 再 R0/R1 收口  
- 冒烟：`python scripts/test_r0_r1.py`

## v0.5.x · R4 中段局部修理

- `tools/cog_repair.py`：带外重货 ↔ 带内轻货 **swap** + 重货 **x 向滑入** 25–75%L  
- 接在 R1 之后；目标 mid50≥0.55（`r4_target_mid50`）  
- 冒烟：`python scripts/test_r4_repair.py`

## v0.5.x · 不可出运闭环打回

| 触发 | 路由 | 动作 |
|------|------|------|
| 成箱结构不通过 | `box_scheme` | 自动 `crate_passthrough`+dense，重跑 structure→box_scheme→规划装载 |
| 装不下 | `planner` | `max_containers+1` + 叠高/multi_start |
| 重心/60/50/偏心 | `planner` | 强化 `cog_aware` + multi_start 重排 |
| 达上限 | stop | 再 `need_revision` 人工 |

- `risk_report.auto_replanable` + `reject_to`
- harness：**内环** evaluator replan + **外环** risk 后出运打回（≤2 轮）
- 冒烟：`python scripts/test_agent_p0_eight.py`

## P0

1. **SSE** `POST /api/pipeline/stream` + `iter_agent_pipeline`  
2. **trace.jsonl** `output/runs/<run_id>/trace.jsonl`（可回放）  
3. **HITL 摘要卡** `hitl_summary` + 前端高密度确认条（resume）

## P1

4. **Docker** `Dockerfile` + `docker-compose.yml`  
5. **CI** `.github/workflows/ci.yml` smoke  
6. **Team UI** 实时 roster、Agent 详情抽屉、运行自动跟可视化  
7. **引擎 A/B** 总览嵌 `/api/engine-ab`  
8. **Skills 文档** `docs/skills/README.md`

## P2

9. **OTEL/Langfuse 开关** `packing_assistant/otel_hooks.py`（`PACKING_OTEL` / `PACKING_LANGFUSE`）  
10. **会话历史** `/api/runs` · `/api/runs/compare` · 前端「历史」Tab  
11. 3D 仍为等轴测 canvas（Three.js 可选后续，避免强依赖）

## 升级注意

- 前端默认演示走 SSE；失败自动回退 `/api/demo`  
- 旧 `/api/pipeline` 整包响应仍可用  
- 版本号见 `packing_assistant.config.HARNESS_VERSION`

## v0.5.1 对标打磨（GitHub 仍主流 Agent 模式）

**Harness**：`0.5.0` → **`0.5.1`**

对照 **DeerFlow / agents-observe / LangGraph HITL / OpenHands OTEL**（2026 仍有效）：

| 模式 | 我们补的 |
|------|----------|
| 标准事件信封 | `schema: packing.stream.v1` + `type/run_id/node/parent_node/status/duration_ms/ts` |
| 回放 | `GET /api/runs/{id}/replay` SSE + 历史页「回放」 |
| 进度可视 | 顶栏 progress + N/11 agents |
| **Durable HITL** | `session_store.py` → `output/runs/<run_id>/session_state.json`；`/api/confirm` RAM miss 读盘 |
| **Stream = Graph replan** | `iter_agent_pipeline` 在 evaluator 后若 `need_replan` 回环 planner→loader→evaluator（≤2），发 `type: replan` |
| **Tool observe** | SSE/trace `tool_start` / `tool_end`；OTEL span 带 `run_id`/`node`/`tool` |
| 冒烟 | `python scripts/smoke_agent_product.py [--http]` |

仍不做：通用 DeerFlow 超级助手、纯 LLM 坐标、完整 AG-UI 协议栈、WebSocket 多订阅总线（可后续）。

## v0.5.2 · Checkpoint 列表 / resume API / 前端恢复

在 v0.5.1 文件落盘基础上补齐产品面：

- `packing.checkpoint.v1` 元数据 + 原子写
- `GET /api/checkpoints?pending_hitl=true`
- `GET /api/checkpoints/{thread_id}?include_state=true`
- `POST /api/checkpoints/{thread_id}/resume`
- 前端：HITL 待恢复 pill · 历史页恢复并确认
- `python scripts/test_hitl_checkpoint.py [--http]`
- 说明：`docs/hitl-checkpoint.md`

## v0.5.3 · 三项全做

1. **LangGraph 真 checkpoint**  
   - `langgraph-checkpoint-sqlite` → `output/langgraph_checkpoints.db`  
   - `run_team_a` / `run_team_b` 经 `invoke_with_checkpoint`  
   - `GET /api/lg/threads` · `GET /api/lg/threads/{id}`  

2. **OTEL 真导出**  
   - `PACKING_OTEL=1` → OTLP HTTP + 默认 `output/otel/spans.jsonl`  
   - `requirements-observability.txt`  

3. **WebSocket 多 tab**  
   - `WS /ws/session/{session_id}` · `/ws/runs/{run_id}`  
   - `ws_hub` 与 SSE 同源广播  
   - 前端顶栏 `ws live`  

测试：`python scripts/test_observability_stack.py`
