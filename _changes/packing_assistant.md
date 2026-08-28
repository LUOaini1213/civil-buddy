# packing_assistant 质量整改记录（2026-08-25）

共改动 41 个文件（+156 / -141 行）。全部为内部实现调整，公共 API（模块路径、函数/类名、签名、返回结构、CLI 入口）保持不变；新增字段均为返回 dict 的**追加键**，不影响既有消费方。

测试：`python -m pytest scripts/ -q` → **48 passed**（基线 46 passed / 2 failed；
`test_more_examples.py::test_eleven_hundred_frames_floor` 由本次修复转绿）。
`python scripts/demo_one_shot.py` 冒烟测试通过。

## bug 修复

- `packing_assistant/tools/cog_repair.py`：`_rigid_shift_to_max_mid50` 增加「贴端墙 + 货块跨度 ≥80% 柜长」守卫。此前对铺满地面的分布式货（如 12×1.1m 铁架双列条带）会整体平移拉开端墙去刷 mid50 —— 该"提升"只是箱心跨越 [0.25L,0.75L] 带边界的离散伪影（重心实际仅移动 ≤(L-span)/2），代价却是端墙留出无支撑滑移间隙，违反 CTU 贴端墙实务。修复后 `test_eleven_hundred_frames_floor`（12 个 1.1m 架 1×40HQ 贴端墙）通过；跨度 <80% 的场景（如 4×4m 架，`test_booking_regression`）仍正常平移抬 mid50。
- `packing_assistant/tools/cog_shift.py`：`shift_layout_to_mass_center`（R1a）加同一守卫：贴端墙且跨度 ≥80% 柜长时禁止纵向平移（原守卫仅在 mid50 已达标时保墙）。
- `packing_assistant/tools/cog.py`：修复混合质量口径 bug。`cog_for_layout` 原逻辑对缺毛重的箱直接用体积(mm³, 量级 1e9)当"质量"与 kg 混算，一只缺重箱即可把重心/mid50 拉到完全失真。现改为：部分缺重时按「已知箱平均密度 × 体积」估算缺重箱质量；全部缺重时保持纯体积代理（相对比例仍有意义）。`mass_basis` 字段语义不变。

## 健壮性

- `packing_assistant/tools/bin3d.py`：
  - `pack_items`/`pack_boxes_api` 柜型归一化：大小写/空白容错（"40hq" → "40HQ"）；未知柜型仍回退 40HQ，但结果新增 `container_type_fallback` 键标注 requested/used，不再静默吞数据错误。
  - `pack_boxes_api` 对外尺寸缺失/非法（≤1mm）的箱新增 `input_warnings` 返回键，避免缺数据箱被静默当作 1mm 小箱而误报 can_fit。
- `packing_assistant/ws_hub.py`：`EventHub._recent` 事件缓冲原按 key 无限增长（长跑 gateway 内存泄漏）。新增键数上限（512）与 `_evict_stale_recent_locked`：超限时优先淘汰无在线订阅者的最老键，publish/别名广播两条路径均接入。

## 性能

- `packing_assistant/tools/bin3d.py`：`_strip_pack_floor` 汇总未装项时的 `it not in left`（对 dataclass 全字段比较的 O(n²) 扫描）改为 box_id 集合判重，行为等价（最终仍按 box_id 去重、保序）。
- `packing_assistant/agents/loader.py`：`_local_1d` 布局回填中对每条布局 `next(b for b in boxes ...)` 的 O(n²) 查找改为预建 box_id → box 字典。

## 结构优化

- `packing_assistant/kb_bindings.py`：删除 `_parse_simple_yaml` 中整段死代码 —— 手写缩进解析第一遍构建的 `root` 从未被使用，函数最终总是返回 `_parse_yaml_list_aware(text)`；现直接调用后者（PyYAML 优先逻辑不变）。
- `packing_assistant/session_store.py`：`_checkpoint_status` 删除不可达分支（`phase == "await_user_confirm"` 在函数开头已返回）。
- `packing_assistant/tools/bin3d.py`：为核心公共入口 `pack_items` / `pack_boxes_api` 补充完整参数/返回值 docstring（含未知柜型回退与 CoG 修理管道说明）。

## 清理

- 删除未使用的 import（typing 符号、stdlib、函数级 import 元组），涉及：
  `config.py`、`nodes.py`、`hitl_gates.py`、`hitl_summary.py`、`packing_plan.py`、
  `trace_events.py`、`civil_tui.py`、`verdict.py`、`tool_registry.py`、`whatif.py`、
  `knowledge.py`、`score_plan.py`、`p2_stubs.py`、`skills_registry.py`、
  `workteam_kpi.py`、`export_pack.py`、`kb_bindings.py`、`intent_spec.py`、
  `runtime/middleware.py`、`runtime/agent_loop.py`、`runtime/eval_live.py`、
  `teams/team_a.py`、`tools/table_mapper.py`、`tools/design_facts.py`、
  `tools/layout_quality.py`、`tools/dims_override.py`、`tools/tender_review.py`、
  `tools/visualize.py`、`tools/cog_shift.py`、`tools/structure_calc.py`。
  （保留 `harness.py` / `expert_turn.py` / `teams/big_team.py` / `agents/risk_compliance.py`
  中被 pyflakes 标记的顶层 import：属对外 re-export 面，按"不改公共 API"约束不动；
  `otel_hooks.py` 的 `import langfuse` 为可用性探测，带 noqa，保留。）
- 删除赋值后从未使用的死变量：
  - `tools/booking.py`：`soft_lb`、`cur_mid0`、`best_mid_plan`/`best_mid_val`（选优逻辑本就只用 best_ge55/best_ge60/densify_pick，行为不变）
  - `agents/planner.py`：`gross`；`agents/finalize.py`：`risk_passed`
  - `nl_whatif.py`：`net`；`tools/dims_override.py`：`c_wt`
  - `tools/packing.py`：`two_row_cap`；`runtime/agent_loop.py`：`plan`
