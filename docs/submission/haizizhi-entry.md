# 海之子杯 2026 · AI 智能体挑战 — 提交入口

> 本文是从 README 首屏移出的参赛材料，保留原文以便评委对照复跑；其中 R1–R23 为内部 UX 迭代轮次编号，「完全合格」为按赛题 checklist 的自评，不是官方评审结论。

## 参赛提交入口（海之子杯 · AI 智能体挑战）

| 评审维度 | 项目证据 | 可复跑命令 |
|----------|----------|------------|
| **场景创意价值** | 土木版 Codex：66 岗工作台，NL 一句话 pack 入口出真数字（tools 算柜数/坐标，模型只路由） | 起两个服务后在 :8765 聊天框输入 `pack test/sim_materials/small_one_container/materials.xlsx`（起法：Releases exe 双击，或 `cd demo && uvicorn app:app --port 8765`；引擎 `uvicorn gateway.app:app --port 8000`。只起 :8765 无引擎时会得到如实的说明卡，不出假数字） |
| **AI 协同能力** | Agent Middleware 策略引擎+失败恢复：四拍纠偏剧本（正常下单 → 越权被拒 → 工具挂掉自动恢复 → 成本超限熔断）；HITL 人确认后才拼柜 | `python scripts/demo_agent_middleware.py` |
| **技术创新** | 装箱引擎 NL→IntentSpec→白名单 tools→HITL→影子评测；446t 单票对照 29→25 柜（mid50 0.594，risk=WARN 口径）；本地校准综合分对外口径 **8.85** | `python main.py --demo` · `python main.py --eval` |

> **66 岗诚实分级**（L1 知识库 66/66 · L2 工具写盘 36/66 · L3 引擎岗 1，每级挂可复跑验收）：[docs/depth-ladder.md](docs/depth-ladder.md)。申报定位与三维度证据映射：[docs/submission/haizizhi-positioning.md](docs/submission/haizizhi-positioning.md)。
>
> **UX 证据链（23 轮迭代，R1 立规矩 → R23 门禁自检）**：R17 界面填 Key（评委自带，不必改 .env）· R19 co-work 壳（左项目树 · 单一聊天框）· R20-21 `pack <本机路径>` 与回形针上传 · R22-23 物料来源诚实性（表读不到必须明说，网关/exe/CI 三层门禁）。设计公理/逐轮总结/附录 N-R 见 [docs/ux/ux-design-spec.md](docs/ux/ux-design-spec.md)；断网专项 `python scripts/test_offline_ui.py`（外域请求 0、pageerror 0）；端到端金线 `python scripts/r13_golden_path_e2e.py`（8/8 PASS，需 playwright）；体验记分卡 `python scripts/eval_competition_scorecard.py --skip-phase0`（本地校准综合 8.85，赢线 PASS）。

### Agent Middleware（赛道 1 · 完全合格）

对照表：[docs/civil-buddy/track1-qualified.md](docs/civil-buddy/track1-qualified.md)。  
Runtime 只深做两层：**策略引擎**（拒绝弹原因）和 **失败恢复**（retry → `UNSPECIFIED` 审计链）。  
剧本写死：正常下单 → 越权被拒 → 工具挂掉自动恢复 → 成本超限熔断。  
行业现网总判（人改口）：[industry-agent-eval-2026-08-25.md](docs/civil-buddy/industry-agent-eval-2026-08-25.md) — 内部起草搭子 **合格**；签认/投标 **不合格**。

```powershell
python scripts/demo_agent_middleware.py
npm run check
```

`npm run check` 必须过。不得把 API Key 提交进仓。
