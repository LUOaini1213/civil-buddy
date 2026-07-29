# Workflow 联网 Plan · 总分总改进法

> 适用：packing-agent 比赛/工程持续改进  
> 形态：**总 → 分 → 总** + **联网对标** + **可复现 workflow**  
> 当前基线版本：`main@f780469` · harness `0.3.0`

---

## 一、总（先定北极星）

### 1.1 一句话目标

**数字可验证（tools）+ 过程可观察（Agent/API/页）+ 口径不穿帮（体积/订柜）**，  
而不是「再堆模型 / 再加 Agent 个数」。

### 1.2 三条北极星（OKR 式）

| Objective | Key Results（可测） |
|-----------|---------------------|
| **O1 订舱可信** | 空心架 V_eff ≪ outer；`check_volume_gates` 绿；VMU1 类案例 N0 量级合理 |
| **O2 像 Agent 可演示** | `/api/pipeline` 有 steps；页底可筛选 Agent；finalize 有 goal_status |
| **O3 全栈可交付** | 网关可起、ZIP/GitHub 可交、一页 INDEX 能讲 3 分钟 |

### 1.3 联网对标原则（行业共识，非跟风）

| 行业点 | 对我们的含义 |
|--------|----------------|
| 多 Agent = 分工 + 可观测 + 轨迹 | 强化 trace/落盘，不硬吹「全能 LLM」 |
| tools/算法算硬约束 | N0/can_fit 禁止 LLM 编造 |
| 持续改进靠指标与门禁 | 每轮必须有 green script / 回归 |
| 交付要可访问入口 | 保留 FastAPI + 前端，不只脚本 |

### 1.4 每轮节奏（建议 3～5 天一小轮）

```text
总  联网扫一眼 + 定本轮唯一北极星（只选 O1/O2/O3 之一为主）
分  并行审计 3～4 条线 → 排 P0/P1 → 实现
总  门禁 + 演示路径走通 + 写「本轮结论」回灌 INDEX
```

---

## 二、分（四条线并行，再收敛）

### 线 A · 体积与订柜（业务准）

| 检查 | 命令 / 落点 |
|------|-------------|
| 空心架 | `python scripts/check_volume_gates.py` |
| 工地数字 | `python scripts/demo_vmu1_site.py` |
| 文档 | `docs/volume-algorithm.md` |
| 代码 | `volume_estimate.py` / `booking.py` / `packing.py` |

**分项改进例：** 字段补齐 content_m3、可疑体积 WARN、禁止 outer 进 N0。

### 线 B · Agent 与 LangGraph（过程可见）

| 检查 | 落点 |
|------|------|
| 图 | `docs/langgraph-graph.md` |
| 轨迹 | `agent_steps` / `/api/pipeline` |
| 对齐 | `docs/ai-agent-alignment.md` |

**分项改进例：** 缺 tools_used 的节点补齐；HITL 后 steps 拼接；replan 次数写进 message。

### 线 C · API + 前端（全栈可摸）

| 检查 | 落点 |
|------|------|
| 健康 | `GET /api/health` |
| 双口径 UI | 拼柜区 volume_summary |
| Agent 面板 | 页底筛选 |

**分项改进例：** 确认流也出 steps；体积卡片；导出 run 包下载链接。

### 线 D · 交付与回归（能交卷）

| 检查 | 落点 |
|------|------|
| 门禁 | `run_precommit_tests.py --quick` |
| 包 | `output/releases/*.zip` |
| 叙事 | 错误 vs 正确口径文档 |

**分项改进例：** 评委包刷新；INDEX 与 commit 对齐。

### 2.1 分项优先级矩阵

| 优先级 | 判据 | 动作 |
|--------|------|------|
| **P0** | 订柜数字错 / 口径混用 | 当轮必修 + 门禁 |
| **P1** | 演示看不见过程 | API/前端/trace |
| **P2** | 体验/文档/引擎可选 | skjolber、润色文案 |
| **不做** | LLM 直接报柜数、无限自治订舱 | 明确拒绝 |

### 2.2 Workflow 怎么跑（联网 plan 的「分」）

```text
phase 总览（可选联网）
  → 1 个 agent：读 docs + web 对标 → 写出本轮北极星 + 禁止项

phase 分项审计（并行）
  → volume | agent-graph | api-frontend | deliver
  → 每线输出 {priority, file, issue, fix_hint}

phase 实现
  → 只做 P0+P1 清单前 N 项（N≤5）

phase 总验收
  → 门禁脚本 + 演示路径 checklist
  → 写本轮「总分总结论」到 scratch / docs
```

项目内脚本：

- `.grok/workflows/full-stack-improve.rhai`（Audit→Implement→Verify）  
- 本文方法可扩展为「先联网总览」再调上述 workflow  

本地 trust 项目 `.grok/workflows` 后：

```text
/workflow full-stack-improve
# 或 args: {"focus":"volume_ui_api"}
```

---

## 三、总（收敛：验收与叙事）

### 3.1 每轮结束必须交三样东西

1. **绿门禁**（至少 `check_volume_gates`；能则 precommit quick）  
2. **可指着的演示路径**（A 数字 或 B Agent 网页一条走通）  
3. **一段总分总口述**（30～60 秒）：

```text
【总】本轮北极星：______（例：订舱不虚高 + 页底可见 Agent）
【分】做了：①… ②… ③…；验证：脚本/页面哪几处
【总】现在版本 main@____；已知限制：______；下一轮只攻 ______
```

### 3.2 当前基线（已完成的「总」）

| 能力 | 状态 |
|------|------|
| 有效体积订柜 | 有门禁脚本 |
| Agent 闭环 API | `/api/pipeline` |
| 页底 Agent + 双口径 | 前端已有 |
| GitHub | `f780469` |
| 压缩包 | `output/releases/packing-agent_全栈提交_*` |

### 3.3 下一轮建议（从「总」再拆一轮「分」）

| 次序 | 主题 | 验收 |
|------|------|------|
| 1 | HITL 确认后 agent_steps 不断档 | 团队A→确认→B，页底全程可筛 |
| 2 | precommit 并入体积门禁 | CI/本地一键绿 |
| 3 | 评委包一键刷新 | INDEX 与 commit 一致 |
| 4 |（可选）skjolber 稳定健康展示 | health 绿时引擎字段正确 |

---

## 四、一页流程图

```text
          ┌─────────────────────────────┐
   总     │ 北极星 O1/O2/O3 + 联网对标   │
          │ 禁止：LLM 报柜 / 无限自治     │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
   分     │ 并行：体积│Agent│API页│交付  │
          │ → P0/P1 清单 → 有限实现      │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
   总     │ 门禁绿 + 演示通 + 结论回写   │
          │ 版本戳 + 下一轮只留 1 主目标  │
          └─────────────────────────────┘
```

---

## 五、和「只写 plan 不落地」的区别

| 坏习惯 | 总分总 workflow 做法 |
|--------|----------------------|
| 只列愿望清单 | 每条带 file + 验收命令 |
| 只联网抄概念 | 联网只服务「禁止项/对标句」，代码门禁为准 |
| 一轮改太多 | 分项并行审计，实现 **≤5** 项 |
| 改完无说法 | 强制 30 秒总分总口述模板 |

**记住：** 总分总是 **沟通与收敛结构**；workflow 是 **执行机器**；联网是 **校准尺子**，不是改算法的理由。
