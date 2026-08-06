# 3h 产品优化迭代 · 2026-08-06

**Baseline HEAD**: `3b76de1`（联网 9.00 文档）  
**交付 HEAD**: 见本提交  
**Scratch**: goal implementer · `iter3h_*.log`

## 选型（残差 backlog）

| # | 项 | 本轮 |
|---|-----|------|
| A | VGM 人签可见（超 stub 标签） | **已交付** |
| B | 非标夹具 pack-path 冒烟（超 inspect-only） | **已交付** |
| C | llm 影子柜数 reference-only 面加强 | **已交付**（附带于 path_honesty） |
| D | high_util mid50 ≥0.70 | **延期**（实测仍 **66.67%**） |

## 交付 A · VGM human-signoff

**行为**

- `tools/vgm_draft.py`：`record_human_signoff` / `build_vgm_status_public`；草稿双写 `per_container`+`containers`
- `harness._vgm_status` → 完整 `human_signoff` 面板（checklist_item_id=`vgm_signed`、pending_action、ui_visible、ui_label）
- 未签：`draft_vgm_submit` → `blocked_unsigned`
- 已签：status=`signed_local`；submit dry_run 仍不连承运人
- Gateway：`POST /api/vgm/signoff`、`POST /api/vgm/submit-preview`；health `vgm_human_signoff`
- HITL 摘要卡 `vgm_signoff`；前端 pill 显示 ui_label / 已签态

**证据**: `{SCRATCH}/iter3h_improve_vgm_path.log` · `scripts/test_path_honesty_vgm.py` → ALL_PASS  
观测：`submit_blocked=blocked_unsigned` → 签后 `submit_after=dry_run` · `vgm_signed=True`  
一致性（skeptic 修复）：`is_vgm_signed` 同时认 `checklist_checked` **与** `pre_ship_checked`；`record_human_signoff` 双写两侧；撤销清勾选并 `blocked_unsigned`；仅 UI `pre_ship_checked.vgm_signed` 亦可 dry_run。

## 交付 B · 非标 pack-path smoke

**行为**

- `scripts/test_nonstandard_pack_smoke.py` 驱动真实 `run_agent_pipeline`：
  - PACK×3（heavy_cast / thin_sheet / fragile）：pipeline 完成 + nonstandard overall 可见
  - FAIL×2（missing_dims / over_width）：诚实拦截（ship_ok/can_fit/incomplete/blocks_auto）

**证据**: `{SCRATCH}/iter3h_improve_ns_pack.log`  
样例：`ns_thin_sheet_stack can_fit=True ship_ok=True ns=WARN` · `ns_missing_dims_mix can_fit=False ship_ok=False incomplete=True`

## 附带 C · path_honesty cabin 参考面

- `cabin_count_reference_only`、`ui_label`、`booking_containers_note` 进入 public_response
- 前端「路径参考」pill 用 ui_label + booking note

## 门禁（变更后）

`{SCRATCH}/iter3h_gates.log` 全 exit 0：

nonstandard golden · ns_new 8/8 · G-table 15/15 · table API · path_honesty_vgm · profile auto · workteams tiny agree=1.0 · **ns_pack_smoke ALL_PASS**

## mid50 实测（未抬舒适区）

`{SCRATCH}/iter3h_mid50_probe.log`：

```
high_util: mid50=66.67% balance=ok can_fit=True
steel: mid50=100.00%
PASS mid50 CTU  (≥0.60 硬线；未达 ≥0.70 舒适目标)
```

**不声称 mid≥0.70。** 布局限制仍在；3h 窗口优先诚实面与 pack 冒烟。

## 延期

1. high_util mid50 舒适区 ≥0.70（需 densify/策略更深改）  
2. 承运人真 VGM 通道（仍 `not_configured` / dry_run）  
3. 全部 8 套 ns 全 pipeline 批量 pack（本轮 5 套代表性冒烟）  
4. 联网总分重打（本轮非目标）

## 演示只说

> VGM 有人签面板与检查项绑定，未签不可「提交」；llm 路径柜数仅参考；非标夹具可走真实拼柜冒烟。mid50 满载仍约 66.7%，不报 70%。
