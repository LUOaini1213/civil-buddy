# 二阶段架构：Agent4–8 + skjolber（Spring Boot）

> **最终全貌见 [`overall-architecture.md`](./overall-architecture.md)（Agent0–8）**  
> 与一阶段衔接：材料 → 结构装箱 → **标准 boxes** → 本阶段拼柜（Java/skjolber）→ 风险 → 三视角可视化  
>
> 二阶段智能体：4 规划 · 5 skjolber 装载 · 6 评估 · 7 风险合规 · 8 可视化

## 1. 结论

| 项 | 判定 |
|----|------|
| 3 Agent（Planner / Packer / Evaluator） | ✅ 推荐 |
| Packer 核心用 skjolber | ✅ 正确（准确性 + 开发速度） |
| Spring Boot 封装 | ✅ 匹配二阶段人员栈 |
| 评估闭环回 Planner | ✅ 需加 **max_iteration** 防死循环 |

**建议默认算法策略**

| 场景 | Packager |
|------|----------|
| 常规（箱数较多） | `LargestAreaFitFirstPackager` |
| 箱数 ≤ 6 且要最优 | `BruteForcePackager` + deadline |
| 要更快近似 | `FastLargestAreaFitFirstPackager` / `PlainPackager` |

依赖（Maven Central）：

```xml
<dependency>
  <groupId>com.github.skjolber.3d-bin-container-packing</groupId>
  <artifactId>core</artifactId>
  <version>4.2.1</version><!-- 以当时最新 4.2.x 为准 -->
</dependency>
```

单位统一用 **mm / kg**（与一阶段一致）。

## 2. 端到端数据流

```
Phase1 boxes[] ──HTTP──► POST /api/v1/orchestration/run
                              │
                    ┌─────────▼─────────┐
                    │   Orchestrator    │  maxIter=3
                    └─────────┬─────────┘
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
       Planner            Packer            Evaluator
      (规则/可选LLM)   (skjolber 核心)      (规则评分)
           │                  │                  │
           └──── Plan ────────┴── Layout ────────┴── PASS / REPLAN
```

## 3. 与一阶段字段映射

| 一阶段 `boxes[]` | skjolber / Packer |
|------------------|-------------------|
| `箱号` | `Box.id` / `boxId` |
| `外尺寸_mm.长/宽/高` | `withSize(dx, dy, dz)` |
| `毛重_kg` | `withWeight`（注意库为整数重量时做缩放，见 Agent2 文档） |
| `结构结论==不通过` | Planner 标记 `blockPacking` 或强制单柜人工 |
| `特殊属性` 含超长 | Plan.`constraints.noStack` / 限制旋转 |

柜型默认与一阶段 `CONTAINER_SPECS` 对齐：`20GP/40GP/40HQ/45HQ`（内尺寸 mm、最大载重 kg）。

## 4. 闭环规则

- Evaluator 输出 `decision`: `PASS` | `REPLAN` | `FAIL`
- `REPLAN` 时带 `hints[]` 回 Planner（如：`split_heavy`、`try_45hq`、`no_rotate_long`）
- `iteration >= maxIteration` → `FAIL`，返回最后一次 Layout + 原因

## 5. 模块划分（Spring Boot 单仓多模块或包）

```
packing-phase2/
├── pom.xml
└── src/main/java/com/project/packing/
    ├── PackingPhase2Application.java
    ├── common/          # DTO、柜型常量、错误码
    ├── planner/         # Agent 1
    ├── packer/          # Agent 2 ★ skjolber
    ├── evaluator/       # Agent 3
    └── orchestration/   # 调度与 REST
```

详细 **Agent 2 接口与代码结构** 见：`docs/phase2-agent2-packer-api.md`
