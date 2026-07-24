# API Spec：装箱拼柜 8+1 智能体 JSON 接口

| 项 | 值 |
|----|-----|
| 版本 | `2.1.0` |
| 状态 | **最终完整架构定稿**（含团队A/B + **用户确认闸门**） |
| 命名 | **英文 + 下划线**（snake_case） |
| 单位 | 长度 **mm**，重量 **kg**，利用率 **0~1 小数** |
| 空列表 | 一律 `[]`；无数据对象 `{}`；仅 `previous_plan` 等允许 `null` |
| 组成 | **Agent0 主控 + Agent1~8 业务智能体** |

架构总览见 [`overall-architecture.md`](./overall-architecture.md)。

---

## 设计原则

1. 智能体之间**只传本文标准 JSON**；原始长文本仅进入 Agent0 / Agent1。  
2. Agent0：意图、调度、状态、多轮、**汇总转发**；业务计算在 1~8。  
3. 字段名全链路一致。  
4. Java / Python 共用契约。

## 数据流（含用户确认闸门）

```
user_input
  → Agent0 主控
      →【团队A】Agent1→2→3
      → 输出装箱方案给用户（phase=await_user_confirm）
      → ★ 用户确认：柜型 / 调整 / 取消
            ├─ revise → 重跑团队A
            ├─ cancel → 结束
            └─ confirm + container_type
                  →【团队B】Agent4→5→6→7→8
                  → 拼柜方案 + 风险报告 + 三视角
  → Agent0 返回用户
```

> **未收到用户 `action=confirm` 前，禁止启动团队B / skjolber。**  
> 团队A 给用户的展示模板见 [`team-a-user-output-template.md`](./team-a-user-output-template.md)。

---

## 公共约定

### intent

| 值 | 含义 |
|----|------|
| `full_process` | 全流程 1→8 |
| `packing_only` | 仅 1→3，再 7（结构相关风险）+ 可选 8 |
| `consolidation_only` | 已有 boxes，从 4 起 |
| `adjust` | 基于 context 调整后重跑受影响节点 |

### status

`success` | `need_more_info` | `error`

### category

`普通件` | `超长件` | `重件`

---

## Agent 0：主控智能体

### 输入

```json
{
  "user_input": "用户原始指令或材料清单文本",
  "session_id": "会话ID",
  "context": {
    "previous_boxes": [],
    "previous_plan": null
  }
}
```

### 输出（两种阶段）

**阶段 A：团队A 完成，等待用户确认**

```json
{
  "intent": "full_process",
  "phase": "await_user_confirm",
  "status": "success",
  "final_response": "装箱方案已生成，请确认柜型后继续拼柜。",
  "packing_plan_id": "PKG-20260724-001",
  "boxes": [],
  "materials": [],
  "summary": {},
  "structure_notes": [],
  "user_prompt": {},
  "container_plan": {},
  "evaluation": {},
  "risk_report": {},
  "risks": [],
  "image_data": {},
  "views": {}
}
```

完整字段与 Markdown 模板见 `team-a-user-output-template.md`。

**阶段 B：用户已确认，团队B 完成**

```json
{
  "intent": "full_process",
  "phase": "done",
  "status": "success",
  "final_response": "给用户的最终文字回复",
  "boxes": [],
  "container_plan": {},
  "evaluation": {},
  "risk_report": {},
  "risks": [],
  "image_data": {},
  "views": {}
}
```

| 字段 | 来源 |
|------|------|
| `phase` | `team_a_running` \| `await_user_confirm` \| `team_b_running` \| `done` |
| `boxes` | 团队A / Agent3 |
| `container_plan` | Agent5（确认前为 `{}`） |
| `evaluation` | Agent6 |
| `risk_report` / `risks` | Agent7 |
| `image_data` / `views` | Agent8 |
| `final_response` | Agent0 汇总 |
| `intent` / `status` | Agent0 |

### 用户确认回传（前端 → 主控）

```json
{
  "session_id": "sess-001",
  "packing_plan_id": "PKG-20260724-001",
  "action": "confirm",
  "container_type": "40HQ",
  "max_containers": 2,
  "adjust_note": "",
  "confirmed_box_ids": []
}
```

`action`：`confirm` | `revise` | `cancel`（详见 team-a 模板文档）。

---

## Agent 1：材料解析智能体

### 输入

```json
{
  "raw_data": "Excel内容或用户粘贴的材料清单"
}
```

### 输出

```json
{
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
  "summary": {
    "total_pieces": 120,
    "total_weight_kg": 8500
  }
}
```

---

## Agent 2：结构计算智能体

### 输入

```json
{
  "materials": []
}
```

### 输出

```json
{
  "structure_constraints": [
    {
      "material_ids": ["M001", "M002"],
      "recommended_box_type": "4米铁架",
      "max_load_kg": 2500,
      "need_reinforcement": true,
      "reinforcement_plan": "底部加横梁 + 纵向加强",
      "reason": "单件超长且总重较高"
    }
  ],
  "global_advice": {
    "prefer_iron_box": true,
    "safety_factor": 1.8
  }
}
```

---

## Agent 3：装箱方案智能体

### 输入

```json
{
  "materials": [],
  "structure_constraints": []
}
```

### 输出

```json
{
  "boxes": [
    {
      "box_id": "BOX-01",
      "box_type": "4米铁架",
      "outer_size_mm": {
        "length": 4000,
        "width": 1100,
        "height": 1750
      },
      "gross_weight_kg": 251,
      "net_weight_kg": 180,
      "content": [
        {
          "material_id": "M001",
          "name": "镀锌钢通",
          "quantity": 4
        }
      ],
      "special_attributes": ["超长", "需加固"],
      "reinforcement": "底部横梁"
    }
  ]
}
```

> **一→二阶段交接物**：`boxes`

---

## Agent 4：规划智能体

### 输入

```json
{
  "boxes": []
}
```

Replan 时主控可附加（可选）：

```json
{
  "boxes": [],
  "replan_context": {
    "round": 2,
    "suggestions": [],
    "previous_evaluation": {}
  }
}
```

### 输出

```json
{
  "plan": {
    "strategy": "长度优先 + 重货下沉",
    "container_type": "40HQ",
    "max_containers": 2,
    "priority_order": ["BOX-01", "BOX-03", "BOX-02"],
    "special_rules": [
      "超长件优先靠柜门放置",
      "单箱毛重>200kg必须底层"
    ]
  }
}
```

---

## Agent 5：装载执行智能体（skjolber）

### 输入

```json
{
  "boxes": [],
  "plan": {}
}
```

### 输出

```json
{
  "container_plan": {
    "container_type": "40HQ",
    "containers_used": 1,
    "space_utilization": 0.86,
    "weight_utilization": 0.71,
    "can_fit": true,
    "layout": [
      {
        "box_id": "BOX-01",
        "container_no": 1,
        "position": { "x": 0, "y": 0, "z": 0 },
        "size": { "dx": 4000, "dy": 1100, "dz": 1750 },
        "rotation": "LWH",
        "layer": 1
      }
    ],
    "unpacked_box_ids": []
  }
}
```

| 字段 | 说明 |
|------|------|
| `position` | 柜内坐标 mm |
| `size` | 放置后占位尺寸 mm（旋转后） |
| `unpacked_box_ids` | 未装入；无则 `[]` |
| 利用率 | **0~1** |

实现：Java + **skjolber/3d-bin-container-packing**。详见 `phase2-agent2-packer-api.md`。

---

## Agent 6：评估优化智能体

> 质量与是否重规划；**不做**完整合规长文与出图。

### 输入

```json
{
  "container_plan": {},
  "boxes": []
}
```

### 输出

```json
{
  "evaluation": {
    "passed": true,
    "score": 87,
    "space_utilization": 0.86,
    "weight_utilization": 0.71,
    "risks": [
      "空间利用率偏低（提示项，供 Agent7 引用）"
    ],
    "suggestions": [
      "将BOX-03与BOX-05位置互换"
    ],
    "need_replan": false
  }
}
```

| 字段 | 说明 |
|------|------|
| `need_replan` | true → 主控回 Agent4 |
| `suggestions` | 给 Planner 的调整建议 |
| `passed` | 质量是否达标（可与 Agent7 合规结果一并决定最终 status） |

---

## Agent 7：风险合规智能体

> 规则引擎 + 评分模型 + **可选 LLM 解释**。  
> 合并：结构约束、箱子特殊属性、布局越界/超重/重心、评估风险。

### 输入

```json
{
  "boxes": [],
  "plan": {},
  "container_plan": {},
  "evaluation": {},
  "structure_constraints": [],
  "global_advice": {}
}
```

### 输出

```json
{
  "risk_report": {
    "passed": true,
    "compliance_score": 92,
    "level": "low",
    "items": [
      {
        "code": "OVERLENGTH",
        "severity": "medium",
        "box_id": "BOX-01",
        "message": "超长件，需确认绑扎与靠门策略",
        "source": "box_special"
      },
      {
        "code": "COG_SHIFT",
        "severity": "low",
        "box_id": null,
        "message": "柜后部重心略偏高",
        "source": "layout"
      }
    ],
    "risks": [
      "BOX-01 超长件，需确认绑扎与靠门策略",
      "柜后部重心略偏高"
    ],
    "explanation": "（可选 LLM）面向业务的风险说明与出运建议…",
    "blockers": []
  }
}
```

| 字段 | 说明 |
|------|------|
| `level` | `low` \| `medium` \| `high` \| `critical` |
| `items` | 结构化风险，便于前端列表 |
| `risks` | 纯文案列表（兼容主控 `risks` 字段） |
| `explanation` | LLM/模板生成的合规说明 |
| `blockers` | 阻断出运的硬项；无则 `[]` |
| `passed` | 无 blocker 且合规分达阈值 |

`severity`：`low` | `medium` | `high` | `critical`  
`source`：`structure` | `box_special` | `layout` | `weight` | `evaluation` | `rule`

---

## Agent 8：可视化智能体

> 根据布局生成**俯视、侧视、正视**三视角；优先输出**结构化绘图数据**供 Vue2 渲染。

### 输入

```json
{
  "container_plan": {},
  "boxes": [],
  "options": {
    "render_mode": "draw_data",
    "export_png": false,
    "views": ["top", "side", "front"]
  }
}
```

| `render_mode` | 含义 |
|---------------|------|
| `draw_data` | 只返回前端绘图 JSON（推荐） |
| `png` | 后端出 PNG，填 `image_data` |
| `both` | 两者都给 |

### 输出

```json
{
  "views": {
    "top": {
      "name": "俯视",
      "camera": "top",
      "container": {
        "length_mm": 12032,
        "width_mm": 2352,
        "height_mm": 2698
      },
      "elements": [
        {
          "box_id": "BOX-01",
          "x": 0,
          "y": 0,
          "width": 4000,
          "depth": 1100,
          "color": "#4C78A8",
          "label": "BOX-01"
        }
      ]
    },
    "side": {
      "name": "侧视",
      "camera": "side",
      "container": {
        "length_mm": 12032,
        "width_mm": 2352,
        "height_mm": 2698
      },
      "elements": [
        {
          "box_id": "BOX-01",
          "x": 0,
          "z": 0,
          "width": 4000,
          "height": 1750,
          "color": "#4C78A8",
          "label": "BOX-01"
        }
      ]
    },
    "front": {
      "name": "正视",
      "camera": "front",
      "container": {
        "length_mm": 12032,
        "width_mm": 2352,
        "height_mm": 2698
      },
      "elements": [
        {
          "box_id": "BOX-01",
          "y": 0,
          "z": 0,
          "depth": 1100,
          "height": 1750,
          "color": "#4C78A8",
          "label": "BOX-01"
        }
      ]
    }
  },
  "image_data": {
    "top": { "path": null, "format": "png", "base64": null },
    "side": { "path": null, "format": "png", "base64": null },
    "front": { "path": null, "format": "png", "base64": null }
  },
  "legend": [
    { "box_id": "BOX-01", "color": "#4C78A8", "box_type": "4米铁架" }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `views` | 三视角结构化数据（Vue2/ECharts/Canvas） |
| `image_data` | 后端出图时按视角填 path/base64；纯前端模式可各为 null 或整体 `{}` |
| `legend` | 图例 |

坐标与 Agent5 `layout` 一致（mm）。无 `container_plan.layout` 时：`views` 各视角 `elements: []`，或仅箱清单示意。

---

## 主控编排顺序

| 步骤 | Agent | 写入状态 |
|------|-------|----------|
| 1 | 1 材料解析 | materials, summary |
| 2 | 2 结构计算 | structure_constraints, global_advice |
| 3 | 3 装箱方案 | boxes |
| 4 | 4 规划 | plan |
| 5 | 5 装载 | container_plan |
| 6 | 6 评估 | evaluation；need_replan→回 4 |
| 7 | **7 风险合规** | risk_report, risks |
| 8 | **8 可视化** | views, image_data |
| 9 | 0 汇总 | final_response, status, intent |

**intent 裁剪**

| intent | 路径 |
|--------|------|
| `full_process` | 1→2→3→4→5→6→(replan?)→7→8 |
| `packing_only` | 1→2→3→7（结构/箱属性风险）→8（可选） |
| `consolidation_only` | boxes 自 context → 4→5→6→7→8 |
| `adjust` | 受影响节点起，结束于 7→8 |

---

## 端到端最小示例（Agent0 输出）

```json
{
  "intent": "full_process",
  "final_response": "已完成装箱与 40HQ 拼柜。空间利用率 86%，合规评分 92，风险等级 low。详见风险报告与三视角图。",
  "boxes": [],
  "container_plan": {},
  "evaluation": { "passed": true, "score": 87, "need_replan": false },
  "risk_report": {
    "passed": true,
    "compliance_score": 92,
    "level": "low",
    "items": [],
    "risks": [],
    "explanation": "",
    "blockers": []
  },
  "risks": [],
  "views": {},
  "image_data": {},
  "status": "success"
}
```

---

## 与实现映射

| Agent | 实现落点 |
|-------|----------|
| 0 | LangGraph / harness |
| 1 | parse_input |
| 2 | structure_calc → structure_constraints |
| 3 | packing 贪心合箱 |
| 4 | Spring planner |
| 5 | Spring + **skjolber** |
| 6 | 利用率评分 |
| 7 | risk_check + 评分 + LLM 解释 |
| 8 | visualize 升级 / Vue2 消费 views |

---

## 变更记录

| 版本 | 说明 |
|------|------|
| 1.0.0 | 0~6 初版 |
| 1.1.0 | 曾合并「方案输出」为单一 Agent7 |
| 2.0.0 | Agent7 风险合规 + Agent8 可视化 |
| **2.1.0** | **团队A/B 划分 + 强制用户确认闸门；团队A 输出模板文档** |
