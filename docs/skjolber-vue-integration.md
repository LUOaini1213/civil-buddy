# skjolber 服务 + Vue2 三视角联调

## 组件

| 组件 | 路径 | 端口 |
|------|------|------|
| skjolber-service | `skjolber-service/` | 8080 |
| FastAPI 网关 | `gateway/app.py` | 8000 |
| Vue2 前端 | `frontend/index.html` | 经网关 `/` 提供 |

## 数据流

```
浏览器 Vue2
  → POST /api/team-a | /api/confirm | /api/demo
  → Python Harness（团队A/B）
  → Agent5 loader
       ├─ SKJOLBER_URL 已配置且健康 → POST :8080/api/v1/packer/pack
       └─ 否则 → 本地 1D 回退
  → Agent8 views → 前端 Canvas 绘制 top/side/front
```

## 启动顺序

1. **（推荐）JDK 17 + Maven** 启动 skjolber  
   `cd skjolber-service && mvn spring-boot:run`  
2. 设置环境变量 `SKJOLBER_URL=http://127.0.0.1:8080`  
3. 启动网关  
   `python -m uvicorn gateway.app:app --reload --port 8000`  
4. 浏览器打开 `http://127.0.0.1:8000`

## 前端操作

1. 点「生成装箱方案」→ 表格展示 boxes  
2. 选择柜型 →「确认并拼柜」  
3. 查看三视角 Canvas + 风险报告  
4. 或「一键演示」自动确认全流程  

## 无管理员 / 装不了 Java 时

**不必装 JDK。** Agent5 会走纯 Python 3D：

| engine 值 | 含义 |
|-----------|------|
| `python-laff-3d` | 默认主路径，Extreme Point + LAFF 风格，无 Java |
| `skjolber-*` | 配置了 `SKJOLBER_URL` 且 Java 服务可用 |
| `local-linear-1d-placeholder` | 极端失败时的 1D 兜底 |

实现：`packing_assistant/tools/bin3d.py`  
只起网关即可：

```bash
python -m uvicorn gateway.app:app --port 8000
# 打开 http://127.0.0.1:8000
```

以后有权限再装 JDK，起 `skjolber-service` 并设 `SKJOLBER_URL` 即可切换真实 skjolber。

## 说明

- 装载引擎看响应里 `container_plan.engine`。  
- Vue2 只消费 `views`，与引擎无关。  
