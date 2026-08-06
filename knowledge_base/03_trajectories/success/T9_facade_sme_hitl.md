---
category: trajectories
subcategory: success
priority: high
type: trajectory
tags: [T9, facade, SME, HITL, nonstandard, packing]
source: internal
updated: "2026-08-06"
harness: ">=0.6.3"
status: active
---
# T9 · 幕墙 SME 成箱→HITL→拼柜（成功）

**Goal**：REDACTED-VENDOR 类项目物料（铁架/玻璃备注）经 Team A 成箱与非标检验，人确认后 Team B 拼柜，tools 出柜数与坐标。

## steps

1. intent
   - tool: intent.interpret
   - args: {"raw_input": "锁 2 柜 40HQ，玻璃易碎禁翻，项目物料装柜"}
   - observation: IntentSpec max_containers=2, fragile/ns hints

2. material_parser
   - tool: material_parser.inject
   - args: {"materials_ref": "sim_facade_mix"}
   - observation: n_materials>0

3. nonstandard_enrich
   - tool: nonstandard.enrich
   - args: {"materials": "..."}
   - observation: fragile=true on glass rows; dims unchanged

4. box_scheme
   - tool: box_scheme.materials_to_passthrough_boxes
   - args: {"standard_boxes": true}
   - observation: boxes[] with outer_size_mm

5. nonstandard_inspect
   - tool: nonstandard.inspect
   - args: {"materials": "...", "boxes": "...", "container_type": "40HQ"}
   - observation: overall in PASS|WARN; ship_gate.requires_human_review if WARN

6. hitl
   - tool: hitl.confirm_gate
   - args: {"action": "confirm"}
   - observation: phase → team_b

7. planner + loader
   - tool: booking.compute_booking
   - args: {"boxes": "...", "container_type": "40HQ"}
   - observation: n0=max(wt,vol,geom_*); not LLM-picked
   - tool: bin3d.pack_boxes_api
   - args: {"max_containers": "n0_search"}
   - observation: can_fit, layout xyz from tools

8. finalize
   - tool: risk_rules.thresholds
   - args: {}
   - observation: mid50 / ship_ok explained; agent_steps A+B present

## final

- can_fit true or explicit budget block
- illegal_tool_calls=0
- no LLM xyz
