# 智能装箱与拼柜 · 多智能体 Harness

面向 **远东新加坡陆路交通局办公楼项目** 钢结构件：  
**材料清单 → 铁箱/木箱（结构）→ 拼柜装载 → 风险合规 → 三视图**。

## 最终架构（9 智能体 + 用户确认）

```
用户输入（材料清单）
  →【1 主控】开头选柜 + 双利用率目标 + 二层堆码策略
  →【团队A】2 材料解析 · 3 结构 · 4 装箱方案
  → 输出装箱方案给用户
  →【用户确认】★ 必选柜型 / 可调整 / 可取消
  →【团队B】5 规划 · 6 装载 · 7 评估 · 8 风险 · 9 可视化
  →【主控收口】结尾复核柜型 + 汇总报告
```

### 安全提示

- **不要提交** `deepseek api.txt`、`.env`、任何 `*apiKey*` 文件（已在 `.gitignore`）
- 复制 `.env.example` → `.env`，填入自己的 LLM Key

| 文档 | 说明 |
|------|------|
| [docs/overall-architecture.md](docs/overall-architecture.md) | **最终完整架构** |
| [docs/team-a-user-output-template.md](docs/team-a-user-output-template.md) | **团队A 给用户的输出模板** |
| [docs/api-spec.md](docs/api-spec.md) | **JSON 接口定稿 v2.1** |
| [docs/phase2-agent2-packer-api.md](docs/phase2-agent2-packer-api.md) | skjolber 封装参考 |

## 设计原则

- 计算用代码（结构 / 合箱 / skjolber / 规则评分）
- LLM：意图、解析辅助、风险解释、文案润色
- 接口：snake_case，mm/kg，Agent 间只传标准 JSON

## 运行（代码已按最终架构落地）

```bash
cd E:\ai比赛
pip install -r requirements.txt

# 全流程（自动确认 40HQ，便于演示）
python main.py --demo --trace

# 只跑团队A → phase=await_user_confirm（等人确认）
python main.py --team-a

# 交互：团队A → 输入柜型 → 团队B
python main.py --interactive

# 回归
python main.py --eval
```

| 代码 | 对应 |
|------|------|
| `agents/material_parser` | 团队A 材料解析 |
| `agents/structure_agent` | 团队A 结构计算 |
| `agents/box_scheme` | 团队A 装箱方案 |
| `agents/present_team_a` | 用户确认载荷 |
| `agents/planner` | 团队B 规划 |
| `agents/loader` | 团队B 装载（**占位**，待 skjolber） |
| `agents/evaluator` | 团队B 评估 |
| `agents/risk_compliance` | 团队B 风险合规 |
| `agents/visualizer` | 团队B 三视角 |
| `harness.run_team_a / run_team_b` | 主控闸门 |

## 技术分工

- Agent0 + 团队A + 网关：Python / LangGraph + **FastAPI**  
- Agent5：**Java Spring Boot + skjolber**（`skjolber-service/`）  
- Agent8：`views` → **Vue2**（`frontend/index.html`，CDN 无需 npm）  

## 联调：装载引擎 + Vue2（**无需 Java / 管理员权限**）

本机若装不了 JDK，**默认使用纯 Python 3D 引擎**（`python-laff-3d`），接口与 skjolber 对齐，Vue2 可直接画三视角。

```bash
pip install -r requirements.txt
python -m uvicorn gateway.app:app --reload --port 8000
# 浏览器打开 http://127.0.0.1:8000
# 按钮「跑 test PDF 样例」/ 报表 /api/test-shipments/report
```

### test/ 装箱单整批（同一项目拼柜，默认接 DeepSeek）

```bash
python scripts/run_test_shipments.py
# 输出:
#   output/test_shipments/summary.json
#   output/test_shipments/report.html
#   output/test_shipments/report.xlsx
#   output/test_shipments/*_project.json
```

### 钢结构 Excel 测试集（远东多 sheet 拆分 + 合成）

网上几乎没有「材料→铁架→拼柜」同业务完整 Excel。以项目内远东表为主：

```bash
python scripts/build_steel_test_set.py   # 从 SLT0*远东*.xlsx 拆分 → test/excel/
python scripts/run_excel_tests.py       # 材料清单跑 TeamA/B
# 输出: output/excel_tests/report.html
```

| 文件 | 来源 |
|------|------|
| `test/excel/test_materials_01.xlsx` | 报价单 |
| `test/excel/test_boxes_2m.xlsx` 等 | 装货单按铁架类型 |
| `test/excel/test_full_flow.xlsx` | 材料+箱明细+柜型 |
| `test/excel/synthetic/*.xlsx` | 短件/超长/近限重/超重/混装 |

### 公开 3D-BPP 基准（拼柜引擎冒烟，非钢结构业务）

```bash
python scripts/fetch_external_datasets.py   # D-Wave sample txt
python scripts/convert_bpp_to_cases.py      # → test/benchmarks/*.json + excel/
python scripts/run_benchmark_cases.py       # 第二阶段 pack_boxes_api
# 输出: output/benchmarks/report.html
```

| 数据 | 用途 |
|------|------|
| D-Wave sample_data_1/2 | 单柜/多柜算法冒烟 |
| case_a 小件 20GP | 易装 |
| case_b 长件 40HQ | 偏铁架风格 |
| case_c / overweight | 限重与风险 |
| **远东 Excel** | **业务正确性 / 答辩主案例** |

尺寸覆盖：`knowledge/dims_override.json`（关键词命中则替换估算尺寸）。

Agent5 装载优先级：

1. `SKJOLBER_URL` 指向的 Java skjolber 服务（有 JDK 时可选）  
2. **纯 Python 3D**（`packing_assistant/tools/bin3d.py`）← **无管理员时的主路径**  
3. 旧 1D 线性兜底  

有管理员/JDK 时再装 Java 并设置 `SKJOLBER_URL` 即可无真实 skjolber，代码不用改。

### 3）API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/team-a` | 团队A，返回装箱方案 + `phase=await_user_confirm` |
| POST | `/api/confirm` | `action=confirm\|revise\|cancel` |
| POST | `/api/demo` | 自动确认全流程 |
| GET | `/api/health` | 网关 + skjolber 状态 |

## 环境变量

见 `.env.example`（含 `SKJOLBER_URL`）。
