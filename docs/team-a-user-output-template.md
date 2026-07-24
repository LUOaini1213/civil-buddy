# 团队A 给用户的输出模板（装箱方案）

> 阶段：材料清单 → 团队A 跑完后、**进入用户确认前**  
> 用途：前端展示 / 主控 `final_response`（phase=A）/ 导出 PDF·Excel 的统一结构  
> 配套机器可读 JSON：见下文「标准 JSON 载荷」

---

## 一、展示结构（推荐 UI 分区）

```
┌────────────────────────────────────────────────────────────┐
│  ① 页头：项目与结论摘要                                      │
├────────────────────────────────────────────────────────────┤
│  ② 材料汇总表                                                │
├────────────────────────────────────────────────────────────┤
│  ③ 箱子方案明细（可展开每箱装载内容）                          │
├────────────────────────────────────────────────────────────┤
│  ④ 结构与加固提示                                            │
├────────────────────────────────────────────────────────────┤
│  ⑤ 重量与箱型统计                                            │
├────────────────────────────────────────────────────────────┤
│  ⑥ 待用户确认区（柜型选择 + 调整意见 + 操作按钮）              │
└────────────────────────────────────────────────────────────┘
```

---

## 二、给人看的 Markdown / 文本模板

可直接作为聊天回复或报告正文（占位符用 `{{ }}`）。

```markdown
# 装箱方案确认单

**会话**：{{session_id}}  
**方案编号**：{{packing_plan_id}}  
**生成时间**：{{generated_at}}  
**项目**：REDACTED-PROJECT · 钢结构件  

---

## 一、结论摘要

| 项 | 内容 |
|----|------|
| 材料条目 | {{material_line_count}} 种 / 共 {{total_pieces}} 件 |
| 材料总重 | {{total_material_weight_kg}} kg |
| 木箱/铁箱数量 | {{box_count}} 个 |
| 箱子总净重 | {{total_net_weight_kg}} kg |
| 箱子总毛重 | {{total_gross_weight_kg}} kg |
| 结构结论 | {{structure_overall}}（通过 {{structure_pass}} / 需加强 {{structure_reinforce}} / 不通过 {{structure_fail}}） |
| 建议柜型（供参考） | {{suggested_container_types}} |

> 请核对下列装箱方案。确认后请选择集装箱类型，系统将进行拼柜计算（skjolber）。

---

## 二、材料汇总

| 序号 | 材料ID | 名称 | 规格 | 长×宽×高(mm) | 单重(kg) | 数量 | 总重(kg) | 分类 |
|------|--------|------|------|--------------|----------|------|----------|------|
{{#materials}}
| {{index}} | {{id}} | {{name}} | {{spec}} | {{length_mm}}×{{width_mm}}×{{height_mm}} | {{weight_kg}} | {{quantity}} | {{total_weight_kg}} | {{category}} |
{{/materials}}

**小计**：总件数 {{total_pieces}}，总重量 {{total_material_weight_kg}} kg。

---

## 三、装箱方案明细

{{#boxes}}
### {{box_id}} · {{box_type}}

| 项 | 值 |
|----|-----|
| 外尺寸 (mm) | 长 {{outer_size_mm.length}} × 宽 {{outer_size_mm.width}} × 高 {{outer_size_mm.height}} |
| 净重 / 毛重 | {{net_weight_kg}} kg / {{gross_weight_kg}} kg |
| 特殊属性 | {{special_attributes_text}} |
| 加固要求 | {{reinforcement_text}} |

**装载内容**

| 材料ID | 名称 | 数量 |
|--------|------|------|
{{#content}}
| {{material_id}} | {{name}} | {{quantity}} |
{{/content}}

---
{{/boxes}}

---

## 四、结构与加固提示

{{#structure_notes}}
- {{.}}
{{/structure_notes}}

{{^structure_notes}}
- 未发现必须阻断的结构问题；正式出运前仍建议包装工程师复核。
{{/structure_notes}}

---

## 五、箱型与重量统计

| 箱型 | 数量 | 合计毛重(kg) |
|------|------|--------------|
{{#box_type_stats}}
| {{box_type}} | {{count}} | {{gross_weight_kg}} |
{{/box_type_stats}}

| 统计项 | 数值 |
|--------|------|
| 箱数 | {{box_count}} |
| 总净重 | {{total_net_weight_kg}} kg |
| 总毛重 | {{total_gross_weight_kg}} kg |
| 最重单箱 | {{heaviest_box_id}}（{{heaviest_box_gross_kg}} kg） |
| 最长单箱 | {{longest_box_id}}（{{longest_box_length_mm}} mm） |

---

## 六、请您确认（必须）

### 1）选择集装箱类型（必选其一）

- [ ] **40HQ**（默认推荐）
- [ ] **40GP**
- [ ] **20GP**
- [ ] **45HQ**
- [ ] 其他：________（请注明）

系统建议：{{suggested_container_types}}  
建议说明：{{container_suggestion_reason}}

### 2）对装箱方案的意见（可多选 / 可填空）

- [ ] 方案无误，按此进入拼柜  
- [ ] 需要调整：去掉/合并某些箱（请说明）  
- [ ] 需要调整：某材料改箱型（请说明）  
- [ ] 其他需求：________________

### 3）操作

| 操作 | 含义 |
|------|------|
| **确认并拼柜** | 提交 `action=confirm` + 柜型 → 启动团队B |
| **调整后重算装箱** | 提交 `action=revise` + 调整说明 → 重跑团队A |
| **取消** | 结束本轮 |

---

*本页仅含装箱方案，不含三维拼柜布局。拼柜结果在您确认后生成。*
```

---

## 三、标准 JSON 载荷（主控 → 前端 / 用户确认接口）

团队A 完成后，主控对用户（或前端）下发如下结构；**用户确认接口**见第四节。

```json
{
  "phase": "await_user_confirm",
  "session_id": "sess-001",
  "packing_plan_id": "PKG-20260724-001",
  "generated_at": "2026-07-24T15:30:00+08:00",
  "project_name": "REDACTED-PROJECT",

  "summary": {
    "material_line_count": 12,
    "total_pieces": 120,
    "total_material_weight_kg": 8500.0,
    "box_count": 8,
    "total_net_weight_kg": 8200.0,
    "total_gross_weight_kg": 9100.0,
    "structure_overall": "需加强",
    "structure_pass": 6,
    "structure_reinforce": 2,
    "structure_fail": 0,
    "suggested_container_types": ["40HQ"],
    "container_suggestion_reason": "总毛重与最长件适合 40HQ 单柜或双柜评估，建议优先 40HQ"
  },

  "materials": [
    {
      "id": "M001",
      "name": "镀锌钢通",
      "spec": "150x150x6",
      "length_mm": 6000,
      "width_mm": 150,
      "height_mm": 150,
      "weight_kg": 69.7,
      "quantity": 6,
      "total_weight_kg": 418.2,
      "category": "超长件"
    }
  ],

  "boxes": [
    {
      "box_id": "BOX-01",
      "box_type": "6米铁架",
      "outer_size_mm": {
        "length": 6000,
        "width": 1100,
        "height": 1550
      },
      "net_weight_kg": 418.2,
      "gross_weight_kg": 669.2,
      "content": [
        {
          "material_id": "M001",
          "name": "镀锌钢通",
          "quantity": 6
        }
      ],
      "special_attributes": ["超长"],
      "reinforcement": ""
    }
  ],

  "structure_constraints": [],
  "structure_notes": [
    "BOX-02 建议底部加横梁",
    "存在超长件，拼柜时建议靠门且禁止竖放"
  ],

  "stats": {
    "by_box_type": [
      { "box_type": "6米铁架", "count": 2, "gross_weight_kg": 1500.0 },
      { "box_type": "4米铁架", "count": 5, "gross_weight_kg": 6200.0 },
      { "box_type": "3米木箱", "count": 1, "gross_weight_kg": 400.0 }
    ],
    "heaviest_box_id": "BOX-03",
    "heaviest_box_gross_kg": 2100.0,
    "longest_box_id": "BOX-01",
    "longest_box_length_mm": 6000
  },

  "user_prompt": {
    "title": "请确认装箱方案并选择集装箱类型",
    "required_fields": ["action", "container_type"],
    "container_options": [
      {
        "value": "40HQ",
        "label": "40HQ 高柜",
        "recommended": true
      },
      {
        "value": "40GP",
        "label": "40GP 平柜",
        "recommended": false
      },
      {
        "value": "20GP",
        "label": "20GP",
        "recommended": false
      },
      {
        "value": "45HQ",
        "label": "45HQ",
        "recommended": false
      }
    ],
    "actions": [
      {
        "action": "confirm",
        "label": "确认并拼柜",
        "description": "按当前箱子列表进入团队B拼柜"
      },
      {
        "action": "revise",
        "label": "调整后重算装箱",
        "description": "根据 adjust_note 重跑团队A"
      },
      {
        "action": "cancel",
        "label": "取消",
        "description": "结束本轮"
      }
    ],
    "hint": "未确认前不会进行三维拼柜计算"
  },

  "display_markdown": "（可选）服务端已渲染的完整 Markdown 正文，字段同第二节模板"
}
```

### 字段说明（摘要）

| 字段 | 说明 |
|------|------|
| `phase` | 固定 `await_user_confirm`，主控处于等待人工确认 |
| `packing_plan_id` | 本轮装箱方案 ID，确认时原样回传 |
| `summary` | 卡片区结论 |
| `materials` / `boxes` | 与 api-spec 团队A 产出一致 |
| `structure_notes` | 给人看的短提示列表（由结构约束+箱属性生成） |
| `stats` | 图表/统计区 |
| `user_prompt` | 驱动确认表单的元数据 |
| `display_markdown` | 可选；有则前端可直接渲染富文本 |

---

## 四、用户确认回传（前端 → 主控）

### 4.1 确认并进入团队B

```json
{
  "session_id": "sess-001",
  "packing_plan_id": "PKG-20260724-001",
  "action": "confirm",
  "container_type": "40HQ",
  "max_containers": 2,
  "adjust_note": "",
  "confirmed_box_ids": ["BOX-01", "BOX-02", "BOX-03"]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `action` | 是 | 固定 `confirm` |
| `container_type` | 是 | `20GP` \| `40GP` \| `40HQ` \| `45HQ` |
| `max_containers` | 否 | 默认 1 或由主控/规划决定 |
| `confirmed_box_ids` | 否 | 若只拼部分箱；默认全部 |
| `adjust_note` | 否 | 确认时一般为空 |

主控：校验 `packing_plan_id` 与会话状态 → 启动 **团队B**（plan 中带上用户指定 `container_type`）。

### 4.2 调整后重跑团队A

```json
{
  "session_id": "sess-001",
  "packing_plan_id": "PKG-20260724-001",
  "action": "revise",
  "container_type": null,
  "adjust_note": "去掉 BOX-02；连接板单独木箱；钢梁不要和钢柱合箱"
}
```

主控：不进团队B；把 `adjust_note` 交给团队A（或解析智能体）重算 → 再次下发本节模板。

### 4.3 取消

```json
{
  "session_id": "sess-001",
  "packing_plan_id": "PKG-20260724-001",
  "action": "cancel"
}
```

---

## 五、前端交互建议（Vue2）

1. **默认落地页** = 本模板 JSON，而非直接拼柜结果。  
2. 「确认并拼柜」按钮：校验已选 `container_type` 后 `action=confirm`。  
3. 箱表明细支持展开 `content`；`special_attributes` 用 Tag 展示。  
4. `structure_fail > 0` 时：「确认并拼柜」可二次警告或禁止（产品策略可配）。  
5. 确认后进入 loading → 展示团队B 结果（方案 + 风险报告 + 三视角）。

---

## 六、与主控 `status` 对应

| 时机 | status / phase |
|------|----------------|
| 团队A 成功，等待确认 | `status=success` 且业务 `phase=await_user_confirm`（或单独字段 `awaiting_confirm=true`） |
| 用户 confirm 后团队B 中 | `phase=team_b_running` |
| 团队B 完成 | `phase=done`，返回拼柜+风险+三视角 |
| 材料不足 | `status=need_more_info`，不进入确认模板 |

---

## 七、一页纸示例（假数据）

```markdown
# 装箱方案确认单
方案编号：PKG-DEMO-001 | 箱数：2 | 总毛重：1412 kg | 结构：全部通过

| 箱号 | 箱型 | 外尺寸(mm) | 毛重 | 内容 |
|------|------|------------|------|------|
| BOX-01 | 6米铁架 | 6000×1100×1550 | 921 kg | 钢梁×6、H型钢柱×4 |
| BOX-02 | 6米铁架 | 6000×1100×1550 | 491 kg | 连接板×20 |

建议柜型：【40HQ】  
请确认柜型后点击「确认并拼柜」。
```

---

## 变更

| 版本 | 说明 |
|------|------|
| 1.0.0 | 团队A 用户输出模板 + 确认回传 JSON（配合最终架构 HITL） |
