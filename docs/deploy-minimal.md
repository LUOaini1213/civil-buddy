# 云部署最小步骤（packing-agent）

目标：固定 HTTPS 公网地址，不依赖本机 localtunnel。

默认 **不需要** skjolber Java；3D 用 Python bin3d。LLM Key 可选（steps 主路径可无 Key）。

---

## 方案 A · Render（推荐，免费档够演示）

### 0. 准备
- GitHub 已推代码：`https://github.com/LUOaini1213/packing-agent`
- 仓库根目录有可用 `Dockerfile`（已支持 `$PORT`）

### 1. 创建服务
1. 打开 [https://render.com](https://render.com) 登录（可用 GitHub）
2. **New → Web Service**
3. 连接仓库 `LUOaini1213/packing-agent`，分支 `main`
4. 设置：
   - **Runtime**: Docker
   - **Region**: 选近的（如 Singapore）
   - **Instance**: Free / Starter
5. **Environment**（可选）：
   | Key | 示例 | 说明 |
   |-----|------|------|
   | `PACKING_SKIP_SKJOLBER` | `1` | 默认即可 |
   | `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` | 你的 Key | 不要也可跑 steps |
   | `OPENAI_BASE_URL` | DeepSeek 时填对应 base | 可选 |
6. **Create Web Service** → 等 Build / Deploy 变绿

### 2. 访问
- 公网：`https://<你的服务名>.onrender.com`
- 健康：`https://<你的服务名>.onrender.com/api/health`  
  期望：`gateway: UP`、`agent_count: 13`

### 3. 注意（Free）
- 一段时间无人访问会**休眠**，下次打开要等 30～60 秒冷启动
- 要常亮：升付费档，或用方案 B 小机

---

## 方案 B · 任意 Linux 云主机（2 核 2G 够演示）

```bash
# 1. 装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 拉代码
git clone https://github.com/LUOaini1213/packing-agent.git
cd packing-agent

# 3. 构建并后台跑
docker compose up -d --build

# 4. 本机/安全组放行 8000
# 访问 http://<公网IP>:8000
# 建议前面加 Nginx + HTTPS（或 Cloudflare 橙云代理）
```

可选环境变量（写 `.env` 或 `docker compose` 的 environment）：

```env
PACKING_SKIP_SKJOLBER=1
DEEPSEEK_API_KEY=sk-xxx
```

---

## 方案 C · Railway（同类，界面更简单）

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub  
2. 选本仓库 → 自动识别 Dockerfile  
3. Variables 同上（Key 可选）  
4. Generate Domain → 得到 `https://xxx.up.railway.app`

---

## 验收清单

- [ ] `GET /api/health` → UP  
- [ ] 打开首页 → 能看到「满载演示」  
- [ ] 点满载 → HITL 确认 → 拼柜有结果  
- [ ] 手机 4G 也能打开（不是局域网）

---

## 不需要做的

- 不必部署 skjolber（可选 3D 服务）  
- 不必再开 localtunnel（云地址即长期入口）  
- 不必把 `.env` / `deepseek api.txt` 提交进 Git  

---

## 本机对照

```bash
# 仍可本机跑
pip install -r requirements.txt
uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

云上是同一套 `gateway.app:app`，只是 `--host 0.0.0.0` + 公网域名。
