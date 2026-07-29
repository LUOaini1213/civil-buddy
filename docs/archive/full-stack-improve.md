# 全栈改进工作流

## 目标

把 **tools 算数 + API 可调用 + 网页可观察** 拧成一条可重复的改进闭环，而不是只加 Agent 名字。

## 本地 workflow

项目文件：`.grok/workflows/full-stack-improve.rhai`  
（若环境要求 folder trust，可在本机 `/workflow` 或用 `script_path` 信任后启动）

三阶段：

1. **Audit** 并行：volume / gateway / frontend  
2. **Implement** 按优先级改代码  
3. **Verify** 门禁脚本 + 双指标检查  

## 本轮已落地（全栈）

| 层 | 改进 |
|----|------|
| **Tools** | `estimate_containers` 增加 `n0` 别名；空心架门禁脚本 `scripts/check_volume_gates.py` |
| **API** | `public_response.volume_summary`：N0、订柜有效体积率、外廓摆柜率、绑定约束 |
| **Agent** | structure / evaluator 补 `tools_used`；页底 Agent 轨迹（既有） |
| **Frontend** | 拼柜结果区 **双口径体积说明**；筛选 Agent 输出 |
| **Docs** | 本文件 + volume-algorithm / langgraph-graph |

## 自检命令

```bash
python scripts/check_volume_gates.py
python scripts/demo_agent_closed_loop.py --tiny
# 网关
python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
# 浏览器打开 / → 一键演示 → 看双口径 + 页底 Agent
```

## 优先级原则

1. 订柜体积永不静默用满 outer  
2. 前端/API 永远同时展示 booking vs outer  
3. Agent 输出可点选、可下载  
4. 回归脚本 greenable  
