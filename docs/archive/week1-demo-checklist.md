# 第 1 周 · 演示主路径焊死（3 人 checklist）

**目标：** 任意时刻 10 分钟内跑通工地案例并出结论包。

**叙事钉死：** 订柜用有效体积（N0）；外廓只做 3D；禁止写死 2 柜；2 与 3 若不同要诚实讲。

---

## 固定命令（全员背）

```bash
# 演示主路径（推荐）
python scripts/demo_vmu1_site.py --with-shipped

# 提交前必跑
python scripts/run_precommit_tests.py

# 快速只测算法（无 Excel）
python scripts/run_precommit_tests.py --quick
```

产物：`output/demo_package/latest/`（MD + JSON + README + 图）

---

## 每日待办（示例 5 天）

### Day 1 · 焊死脚本

| 人 | 待办 | 完成标准 |
|----|------|----------|
| 队长 | 确认 `demo_vmu1_site.py` / `run_precommit_tests.py` 进主分支；README 半页入口 | 干净目录能跑通 |
| A | 确认 A: 工地 Excel 路径或文档写清缺失时的提示 | site-only 有明确 MISSING 信息 |
| B | 确认输出 MD/JSON 字段：N0、3D、双率 | 打开 latest/README 能念 30 秒结论 |

### Day 2 · 标准产物包

| 人 | 待办 |
|----|------|
| 队长 | 统一口径表：订柜 N0 vs 3D vs 已发 2 柜对照 |
| A | 材料/当量箱输入可解释（填充分/混型一句） |
| B | 收集 2～3 张图：架构示意、15→2 对比表、侧视/三视 |

### Day 3 · 稳定回归

| 人 | 待办 |
|----|------|
| 全员 | 各自机器跑 `run_precommit_tests.py` |
| 队长 | 绿则打 tag `demo-week1`（可选） |
| A/B | 记录一次失败原因到 `docs/` 或 issue（若有） |

### Day 4 · 口述 3 分钟

| 人 | 待办 |
|----|------|
| 队长 | 痛点 40s + 方案 90s（有效体积） |
| A | 成箱/装货单 60s |
| B | 3D/双率图 60s |
| 全员 | 互问：为何 2 和 3 不同？为何不是纯 LLM？ |

### Day 5 · 周验收

- [ ] `demo_vmu1_site.py` 一键成功  
- [ ] `run_precommit_tests.py` 全绿  
- [ ] `output/demo_package/latest/README.md` 数字与 MD 一致  
- [ ] 3 人各自能讲自己模块  

---

## 第 1 周明确不做

- 不扩新 Agent  
- 不改订柜核心公式（P0–P2 已够）  
- 不为 3D=2 写死 `target_containers`  

---

## 角色对照

| 角色 | 主责 |
|------|------|
| 队长 | 口径、文档、回归是否绿、演示节奏 |
| 成员 A | 成箱/数据/装货单对齐 |
| 成员 B | 3D/可视化/演示操作 |
