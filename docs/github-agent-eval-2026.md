# GitHub 优秀 Agent 对标评估（2026 · 仍有效）

> 评估日：2026-07-29 · packing-agent Harness **v0.5.x**

## 1. 仍「没过时」的对标项目

| 项目 | 为何仍有效 | 学什么 | 不盲从什么 |
|------|------------|--------|------------|
| **DeerFlow 2.0** | Super-agent harness 标杆：skills、sandbox、tracing | skills 表、doctor/smoke、落盘 | 做成通用个人助手冲淡装箱 |
| **agents-observe** | 多 agent 实时面板 + 回放 | SSE/事件流、回放、父子关系 | 绑死 Claude Code hooks |
| **LangGraph** | 生产图、interrupt、checkpoint | HITL resume、有状态图 | 重写掉领域 tools |
| **OpenHands** | OTEL / 评测文化 | 可选 OTEL、回归门禁 | 全量沙箱编码 agent |
| **CopilotKit / AG-UI** | Agent↔UI 状态协议 | 事件信封标准化 | 整站 React 重写 |

装载算法类（skjolber / DeepPack3D）仍是 **引擎层**，不是 Agent 产品对标。

## 2. packing-agent 已具备

- 领域竖切：材料→结构→成箱→HITL→拼柜→风险→三视图  
- 计算用代码，非 LLM 编柜数  
- Team Mode UI + SSE 流式点亮  
- `trace.jsonl` + runs 历史  
- HITL 摘要卡 + Docker/CI  

## 3. 本轮已补（v0.5.1）

1. `packing.stream.v1` 事件信封  
2. `/api/runs/{id}/replay` 回放  
3. 顶栏进度条  
4. `scripts/smoke_agent_product.py`  

## 4. 剩余差距（下一迭代）

| 优先级 | 项 |
|--------|-----|
| P1 | LangGraph 真 checkpoint interrupt（非仅 phase 字段） |
| P1 | token/cost 字段（有 LLM 时） |
| P2 | Three.js 真 3D |
| P2 | WebSocket 替代长连接 SSE（多 tab） |
| P2 | support-bundle / make doctor |

## 5. 结论

相对 2026 GitHub 主流，我们 **不缺「又一个框架」**，缺的是 **可观测协议与回放体验**——本轮已对齐一截。  
继续深化 **装箱领域 + 流式可观测**，而不是追 star 数堆通用 harness。
