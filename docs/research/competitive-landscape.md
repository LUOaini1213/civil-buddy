# 竞品 / 同类对照（packing-agent v0.4+）

> 定位：**钢结构件场景下的可观测多智能体装柜 Harness**，不是又一个 3D-BPP 库，也不是「LLM 直接出坐标」的 demo。

## 一句话

| 类型 | 代表 | 相对我们 |
|------|------|----------|
| 算法库 | skjolber、DeepPack3D | 引擎层；我们可插拔接入 |
| LLM 装柜 | Smart Stowage (Gemini 双引擎) | 观感/COG 叙事强；我们确定性工具 + 9 Agent 竖切 |
| 装载软件 | EasyCargo、LoadMaster | 现场 UX；我们是 Agent 流水线 |
| 通用框架 | LangGraph / CrewAI | 我们已用图编排 + HITL；壁垒在领域 tools |

## 能力矩阵

| 能力 | packing-agent | skjolber / DeepPack3D | Smart Stowage | EasyCargo 类 |
|------|---------------|------------------------|---------------|--------------|
| 材料→标准箱 | ✅ | ❌ | ❌ | 手动 |
| 结构/详设阻断 | ✅ | ❌ | 弱 | ❌ |
| 3D 拼柜 | ✅ laff + 可选 skjolber | ✅ 专 | ✅ | ✅ |
| 多 Agent + HITL | ✅ | ❌ | 弱 | ❌ |
| 评估 replan | ✅ | 利用率 | COG/效率 | 利用率 |
| COG 可视化 | ✅ 三视图+等轴测 | ❌ | ✅ Three.js | 部分 |
| NL 改方案 | ✅ | ❌ | prompt | ❌ |
| 引擎 A/B 证据 | ✅ `compare_pack_engines.py` | 自研 | 双引擎 UI | 闭源 |

## 我们补齐过的「缺口」（对标后）

1. **观感**：三视角 COG 红点 + 等轴测可旋转 3D（canvas，无重度依赖）
2. **证据**：`python scripts/compare_pack_engines.py` → `output/engine_ab_report.json`
3. **叙事**：本文档 + README 链接

## 刻意不跟的方向

- 主路径改成纯 LLM 出坐标（牺牲可测/可审计）
- 为 RL 而 RL（钢结构标准箱场景收益有限）
- 商业装载 SaaS 级多租户/运价联动（超 scope）

## 相关命令

```bash
# 引擎对照
python scripts/compare_pack_engines.py

# 多轮回归
python scripts/run_multi_round_tests.py --suite full --rounds 2
```
