# 提交演示：A 数字 + B Agent/API（准必须）

**口径钉死：** 15=系统错算（外廓虚高），2=业务真实；见 [wrong-vs-right-narrative.md](wrong-vs-right-narrative.md)。  
**产物一键：** `python scripts/build_judge_package.py --refresh`

## 直接回答

1. **9 Agent + API 有没有用？**  
   **有用**——证明多智能体工程闭环（成箱/确认/风险/出图），**不是**替代 booking 算更准柜数。

2. **比赛一定要用 API 吗？**  
   **未必条文强制公网**，但说明里若有「访问方式 / 测试步骤」→ **至少一种可访问入口**。  
   你们已有 FastAPI：**本地 gateway 性价比最高**；官方若要求公网 URL 再挂云。

---

## 演示 A · 数字（订舱）

```bash
pip install -r requirements.txt
python scripts/demo_vmu1_site.py --with-shipped
```

| 看什么 | 期望 |
|--------|------|
| 订柜 N0 | ≈2（重量主导） |
| 3D 用柜 | 合理 can_fit（常与 N0 同或接近） |
| 产物 | `output/demo_package/latest/` |

**口述：** 有效体积订柜，外廓不进订舱分子；对比原先虚高。

---

## 演示 B · Agent + API（智能体）

```bash
# 终端 1
powershell -File scripts/start_gateway.ps1
# 或: python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000

# 终端 2
python scripts/demo_nine_agents_trace.py --via-api
# 本地无服务时自动可改不带 --via-api
python scripts/demo_nine_agents_trace.py
```

### 手工 curl（写进说明文档「测试问题」）

```bash
# 1) 健康检查
curl -s http://127.0.0.1:8000/api/health

# 2) 九智能体逐步 trace（推荐给评委）
curl -s -X POST http://127.0.0.1:8000/api/pipeline/trace ^
  -H "Content-Type: application/json" ^
  -d "{\"user_input\":\"演示\",\"container_type\":\"40HQ\",\"session_id\":\"judge1\"}"

# 3) 闸门流：团队A → 确认 → 团队B
curl -s -X POST http://127.0.0.1:8000/api/team-a ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"s1\",\"user_input\":\"演示材料清单\"}"

curl -s -X POST http://127.0.0.1:8000/api/confirm ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"s1\",\"action\":\"confirm\",\"container_type\":\"40HQ\",\"max_containers\":0}"
```

| 看什么 | 期望 |
|--------|------|
| steps[] 每步 message | 主控→…→finalize 都有输出 |
| 确认闸门 | team-a 后需 confirm 才拼柜 |
| 风险 | 可出现 can_fit 仍 REJECT（装得下≠可出运） |
| N0 / can_fit | 仍来自同一套 tools |

浏览器：`http://127.0.0.1:8000`（前端） / `http://127.0.0.1:8000/docs`（Swagger）

---

## 文档里固定两句

> **订舱与 Agent 共用 tools 算数**（有效体积订柜，外廓只 3D）。  
> **API 用于完整闭环与确认闸门**，不是第二套柜数公式。

---

## 说明文档「访问方式」可粘贴

```text
访问方式：本地启动网关（无需公网，除非主办方要求）
  pip install -r requirements.txt
  python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
访问地址：http://127.0.0.1:8000
API 文档：http://127.0.0.1:8000/docs
测试问题 1：POST /api/pipeline/trace 查看 9 智能体 steps
测试问题 2：POST /api/team-a 后 POST /api/confirm 完成拼柜
测试问题 3：python scripts/demo_vmu1_site.py 复现订舱 N0≈2
账号：无需登录（本地演示）
```

公网：若官方 PDF 写明「必须可访问 URL」，再部署同一 `gateway.app` 到云主机，路径不变。
