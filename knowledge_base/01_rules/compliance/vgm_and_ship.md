---
category: rules
subcategory: compliance
priority: high
type: rule
tags: [VGM, ship, compliance]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# VGM 与出运合规

## 规则

- VGM 草稿可由工具生成，**必须人签**后才算正式。
- `ship_ok=False` / `can_fit=False` 禁止提交正式出运。
- TMS booking stub 不改变 3D 布局。
- **中新走廊**：中国出口 / 新加坡中转或到港时，装载物理规则仍循 CTU；申报与港区操作见 `07_domain_knowledge/cn_sg_corridor.md`（摘要非法规）。

## 代码

- `tools/vgm_draft.py` · `tms_booking.py` · finalize
