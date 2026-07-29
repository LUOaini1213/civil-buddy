# 说明文档草稿（按常见模板 1～4 章 · 可粘贴改写）

> 数字以 `python scripts/build_judge_package.py` 产物为准；提交前与 `output/judge_package/latest` 对齐。

---

## 1. 用户与痛点

**用户：** 钢结构/幕墙项目物流与项目经理（订舱、拼柜、出运前合规）。

**痛点：**

1. **订柜虚高：** 把空心铁架外廓当实心体积 → 系统曾报约 15 柜，与真实约 2 柜冲突。  
2. **过程不可解释：** 只有结果没有成箱→确认→风险闭环。  
3. **装得下≠可出运：** 需重心、结构、超重等规则拦截。

**错误 vs 正确（答辩必讲）：**  
15 = **系统错算**（外廓虚高）；2 = **业务真实**（重量+有效体积+装货单）。不是「创造运力」。

---

## 2. 功能与方案

### 2.1 双轨

| 轨 | 功能 | 入口 |
|----|------|------|
| A 订舱数字 | 工地当量成箱 + N0 + 3D | `demo_vmu1_site.py` |
| B 智能体闭环 | 9 Agent + 确认闸门 + 风险 + 出图 | gateway API / `demo_nine_agents_trace.py` |

**共用 tools 算数**（有效体积订柜，外廓只 3D）。

### 2.2 核心能力

- 材料 →（标准箱合箱 **或** 当量直通）→ 箱子  
- 自主定柜 N0 = max(重量柜, 有效体积柜)  
- 3D 自 N0 递增 can_fit  
- 风险：can_fit 仍可 REJECT  
- 可视化：订柜有效体积率 vs 外廓摆柜率  

### 2.3 创新点（一句）

**多智能体成箱+拼柜；订柜用有效体积、外廓只做 3D；避免空心包装虚高柜数。**

---

## 3. 技术与完成度

### 3.1 技术

- Python tools：`volume_estimate` / `booking` / `packing` / `bin3d`  
- LangGraph 编排 9 Agent + HITL 确认  
- FastAPI gateway：`/api/team-a`、`/api/confirm`、`/api/pipeline/trace`  
- 结构：半严格包装校核（非完整有限元）  

### 3.2 完成度

| 项 | 状态 |
|----|------|
| 虚高消除，VMU1 N0≈2 | 已完成 |
| 已发 REDACTED-REF 复算 2 柜 | 已完成 |
| Agent 过程可演示 | 已完成 |
| 当量直通 Agent（工地） | 已完成 `crate_passthrough` |
| 完整有限元 / ML 装箱 | **不做** |

### 3.3 三人分工（示例）

| 角色 | 模块 |
|------|------|
| 队长 | 口径、文档、答辩、回归、提交 |
| 成员 A | 成箱、当量数据、装货单对齐 |
| 成员 B | 3D、可视化、API 演示 |

---

## 4. 演示与访问方式

### 4.1 演示步骤（5 分钟结构）

1. 痛点 40s：15 虚高 vs 2 真实  
2. 方案 90s：有效体积 + 双轨  
3. 证据 90s：judge 包数字 + Agent REJECT 例  
4. 边界 30s：半严格结构、不写死 2 柜  
5. 价值 30s：订舱准 + 工程可控  

### 4.2 访问方式（本地）

```text
pip install -r requirements.txt
# A 数字
python scripts/demo_vmu1_site.py --with-shipped
# B Agent
python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
python scripts/demo_nine_agents_trace.py --via-api
# 工地 Agent 直通
python scripts/demo_vmu1_nine_passthrough.py
# 评委包
python scripts/build_judge_package.py
```

测试请求：见 `docs/submission-demo-A-B.md`（health / pipeline/trace / team-a→confirm）。

### 4.3 高频问答（备）

1. **为何不是纯 LLM？** 数字由规则/算法；LLM 只润色。  
2. **为何 2 和 3？** 订舱 N0 vs 几何上界；禁止写死 2。  
3. **结构为何半严格？** 包装工程量级，非出图盖章。  
4. **如何泛化？** N0 双约束 + 当量/标准箱模式切换。  
5. **测试怎么证？** `run_precommit_tests` + 装货单对照 + judge 包。  

---

## 附录：完成态

见 `docs/completion-checklist.md`。
