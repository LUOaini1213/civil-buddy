# 非标件检验 v2（比赛向）

规则引擎对物料/成箱做 **taxonomy 分型 + 分级门禁 + 仪表盘**；LLM 仅可选抽备注字段。

## 一句话

> 标准件走标准箱；非标件先分型分级检验，再 HITL 勾选；柜数与坐标仍是 tools。

## 命令

```bash
python scripts/test_nonstandard_inspect.py
python scripts/inspect_nonstandard.py --all-presets --with-boxes --also-446t

# API
# POST /api/nonstandard/inspect  { materials?|session_id?, with_boxes?, container_type? }
```

产物：`output/nonstandard_inspect/`

## Taxonomy

| tag | 含义 |
|-----|------|
| DATA_GAP | 缺尺寸/重量/估算尺寸 |
| GEO_OVERSIZE | 超长/超宽/超高/超柜 |
| LOAD_HEAVY | 重件/超货载 |
| SHAPE_CUSTOM | 不落标准箱/薄板/异形 |
| PACK_PATH | 工厂架/当量/crate |
| STRUCT_PENDING | 待详设/需加强/不通过 |
| PROCESS_SPECIAL | 易碎/禁翻/禁叠 |
| COMPLIANCE | 危险品提示（边界） |

## 等级

| overall | 行为 |
|---------|------|
| FAIL | 阻断自动出运；`strict_nonstandard_gate` 时禁止 confirm→B |
| NEED_DESIGN | 任一 `structure_pending` 即抬到此档；可演示，非正式结构签章 |
| WARN | 可拼柜 + 预检勾选 |
| PASS | 通过 |

## 确认拼柜勾选门禁

- 前端 HITL：**必填未勾选不可 confirm**；提供「演示一键勾选」
- `POST /api/confirm` 字段：
  - `checklist_checked: {id: bool}`
  - `enforce_ns_checklist: true`（比赛前端默认；自动化测试勿开）
- 服务端亦可 `packing_options.require_ns_checklist=true`

## 管线挂接

- Team A `present_team_a` → `nonstandard_report` / `nonstandard_summary`
- `public_response` 只下发 summary（top≤20）
- `hitl_summary.nonstandard` + 前端 HITL 非标卡
- `pre_ship_checklist` 合并非标必填项
- 可选 enrich：`PACKING_NS_LLM=1` 或 `packing_options.ns_llm_enrich`

## 降噪

规整密实模块（如 high_util）以 **载荷关注** 为主，不因「不落标准箱」全员刷 SHAPE。

## 代码

- `packing_assistant/tools/nonstandard_inspect.py`
- `packing_assistant/tools/nl_nonstandard_enrich.py`
- `scripts/test_nonstandard_inspect.py`
- Tool id: `nonstandard.inspect`
