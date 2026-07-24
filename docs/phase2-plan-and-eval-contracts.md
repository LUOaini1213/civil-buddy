# Agent 1 Plan / Agent 3 Evaluate 契约（简版）

## Agent 1 — Planner

```http
POST /api/v1/planner/plan
```

**输入**：`boxes[]`（同一阶段映射）+ 可选 `hints[]`（来自 Evaluator）+ `options`

**输出 LoadPlan**（与 Packer 共用）：

```json
{
  "strategy": "LARGEST_AREA_FIT_FIRST",
  "priority": "LENGTH_FIRST",
  "maxContainers": 1,
  "preferredContainerTypes": ["40HQ"],
  "allowRotation": true,
  "constraints": {
    "noStackBoxIds": ["BOX-01"],
    "fixedBottomBoxIds": [],
    "separateGroups": []
  },
  "timeoutMs": 5000,
  "rationale": ["检测到超长件，限制旋转", "总毛重适合单柜 40HQ"]
}
```

**规则引擎建议（第一期无 LLM 也可）**

1. 任一件长 ≥ 5800mm → `allowRotation=false`，该 box 进 `noStackBoxIds`  
2. 总毛重 > 单柜 maxLoad → `maxContainers = ceil(总重/maxLoad)`  
3. 最长件 > 20GP 内长 → 从 preferred 去掉 20GP  
4. 箱数 ≤ 6 且 hints 含 `seek_optimal` → `BRUTE_FORCE`  
5. 否则默认 `LARGEST_AREA_FIT_FIRST` + `40HQ`

---

## Agent 3 — Evaluator

```http
POST /api/v1/evaluator/evaluate
```

**输入**：`plan` + `packResult` + 原始 `boxes`

**输出**

```json
{
  "decision": "PASS",
  "score": 82.5,
  "checks": [
    { "name": "all_packed", "passed": true, "detail": "" },
    { "name": "weight_limit", "passed": true, "detail": "4.4% < 100%" },
    { "name": "bounds", "passed": true, "detail": "" },
    { "name": "min_volume_util", "passed": true, "detail": "18.5%（单大件可豁免）" }
  ],
  "hints": [],
  "summary": "可出运"
}
```

**decision**

| 值 | 含义 |
|----|------|
| `PASS` | 结束，输出最终方案 |
| `REPLAN` | 带 hints 回 Planner |
| `FAIL` | 不可自动修复（或达到 maxIteration） |

**评分维度（示例权重）**

- 全部装下 40%  
- 重量不超限 25%  
- 空间利用率 20%（可按「是否仅大件」豁免下限）  
- 超长件是否贴底/不旋转 15%  

**hints 枚举（与 Planner 约定）**

- `increase_max_containers`  
- `try_45hq`  
- `try_laff` / `try_brute_force`  
- `split_heavy`  
- `no_rotate_long`  
- `forbid_stack_heavy`
