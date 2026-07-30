---
category: domain
subcategory: index
priority: high
type: protocol
tags: [README, division, anti-patterns]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# Agent 知识库（检索 / 规范 / 范例）

面向 **packing-agent**（Harness ≥0.6.3）比赛与运行时的 **可检索文档层**。  
与代码内 `knowledge/packing_knowledge_base.json`（箱型数值库）互补：**本目录是规则与说明；JSON 是可执行箱规格。**

## 目录

| 目录 | 优先级 | 用途 |
|------|--------|------|
| [01_rules/](./01_rules/) | **highest** | 硬规则：CTU、体积重量、订舱、合规 |
| [02_tools/](./02_tools/) | high | 工具何时调用、参数、错误处理 |
| [03_trajectories/](./03_trajectories/) | medium | 成功 / 失败恢复轨迹（few-shot，T1–T8） |
| [04_strategies/](./04_strategies/) | medium | 启发式与风险策略 |
| [05_multi_agent/](./05_multi_agent/) | high | 大 Team ⊃ A/B 协议 |
| [06_competition/](./06_competition/) | high（赛期） | 评分、约束、示例任务 |
| [07_domain_knowledge/](./07_domain_knowledge/) | low | 常识补充 |

## 元数据（每篇 YAML frontmatter）

```yaml
---
category: rules
subcategory: ctu_loading
priority: high
type: rule
tags: [void, 15cm, CTU]
source: CTU_code_practice_summary
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
```

检索：工具 `knowledge.search`（`packing_assistant.tools.search_knowledge`）。  
先 `priority=high` + `type=rule`，再 tools / trajectories。

## 切分（Chunking）

| 类型 | 方式 |
|------|------|
| 规则 | 按 `##` 条款切 |
| 工具说明书 | 一工具一文 |
| 轨迹 | 目标→Step(tool/args/obs)→Final |
| 策略 | 按主题小节 |

索引生成：`python scripts/gen_kb_index.py --patch-fm`

## 与 MySQL / 运行时的分工

| 层 | 存什么 | 不存什么 |
|----|--------|----------|
| **knowledge_base/**（本目录） | 规范条文、工具说明、范例轨迹、策略、协作协议 | 会话状态、实时柜位坐标 |
| **knowledge/*.json** | 标准箱外廓/载重/截面数值 | 长文规则 |
| **MySQL / session_store** | run_id、checkpoint、HITL、booking_id、评分结果、物料行 | 大段 CTU 原文（可只存引用 path） |
| **output/** | 本地跑批产物 | 不入库 git |

**原则**：规则与说明书走 **检索**；事务与轨迹事实走 **结构化存储**；Agent 决策时 **rules 覆盖 strategies**。

## Anti-patterns（禁止）

| 禁止 | 原因 |
|------|------|
| 把 3D layout / xyz 写入本库当「知识」 | 破坏 tools 算坐标叙事 |
| 用轨迹替代 run_packing / loader | 轨迹只 few-shot 流程 |
| md 与 JSON 双写冲突数值表 | 数值以 JSON/代码为准 |
| can_fit=False 当出运范文 | 红线 |

见 `05_multi_agent/illegal_tools.md`。

## 代码入口映射

| 知识 | 代码 |
|------|------|
| 标准箱 | `knowledge/packing_knowledge_base.json` + `knowledge.py` |
| 检索 | `tools/search_knowledge.py` · tool id `knowledge.search` |
| Agent 窄接 | `kb_bindings.py` · `05_multi_agent/agent_kb_bindings.yaml` |
| 可行性 | `tools/cargo_feasibility.py` |
| 订舱体积 | `tools/booking.py` · `volume_estimate.py` |
| 多 Agent | `teams/*` · `docs/ARCHITECTURE.md` |
| 比赛基线 | `test/phase0/*` · `scripts/run_phase0_baseline.py` |
| 分卡 | `scripts/eval_knowledge_base_scorecard.py` |
| 裁决横幅 | `verdict.py`（前端总览，不必开 PDF） |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kb/bindings` | Agent→知识路径绑定表 |
| POST | `/api/kb/search` | `{"agent_id","q","limit"}` 窄接检索 |
| GET | `/api/architecture` | 含 `kb_bindings` 摘要 |

## 回归（提交前）

```bash
python scripts/test_search_knowledge.py   # Recall@3 ≥ 0.90
python scripts/test_kb_bindings.py        # 9 Agent 窄接 + loader 不检索
python scripts/eval_knowledge_base_scorecard.py  # 七维 ≥9.5
python scripts/gen_kb_index.py --patch-fm # 刷新 INDEX.yaml
```

## 维护约定

1. **规则改代码时同步 01_rules**（或反过来），数值以 JSON/代码为准。  
2. 新工具：优先 `scripts/gen_tool_docs_from_catalog.py` 再手改。  
3. 新轨迹：必须含 `tool` / `args` / `observation`（见 T1–T8）。  
4. **禁止**把 3D 坐标/session layout 写入本库。
