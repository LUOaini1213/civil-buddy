---
category: tender_delivery
subcategory: trajectories
priority: high
type: trajectory
tags: [TD1, tender, packing, HITL, facade]
source: internal
updated: "2026-08-06"
harness: ">=0.6.4"
status: active
---
# TD1 · 招标要点 → 装柜交付（成功）

**Goal**：从招标文本抽出运输/包装要求，确认后跑成箱拼柜，输出响应矩阵。

## steps

1. tender_parse
   - tool: tender.parse
   - args: {"text": "招标文件节选…"}
   - observation: requirements[] 含 packaging/transport

2. tender_checklist
   - tool: tender.checklist
   - args: {"requirements": "…"}
   - observation: redlines + must_respond

3. hitl_tender
   - tool: hitl.confirm_gate
   - args: {"scope": "tender_scope"}
   - observation: confirmed

4. team_a_box
   - tool: box_scheme / material.parse
   - args: {"materials": "项目料单"}
   - observation: boxes[]

5. team_b_pack
   - tool: booking.compute_booking + bin3d.pack_boxes_api
   - args: {}
   - observation: can_fit, n0, layout from tools

6. response_matrix
   - tool: tender.response_matrix
   - args: {"requirements": "…", "evidence": "packing summary"}
   - observation: rows status covered|pending

## final

- 响应矩阵非空
- illegal_tool_calls=0
- 无 LLM xyz
