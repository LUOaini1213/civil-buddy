# Civil Buddy

土木企业工作台：**16 大类 / 66 岗** · Rust 工作台 + MCP · 成稿走 steps。  
装箱 / 拼柜是其中一岗（**pack-ship**）：硬数字只走本仓的 packing 引擎，模型不写 xyz、不拍柜数。  
投标主线 C：招标文本 → 条款级响应矩阵 → 装柜 tools 作交付证据 → 经营岗交接（bid-tech / bid-compliance）。P0 资格/★/废标须人确认，**不**自动判定可投标。

> 内部讨论草稿，不是法定专项方案、不是签认件。  
> 高风险写盘前确认句：`我明白，将由持证人员签认`。

原独立仓 packing-agent 与 civil-buddy 已并入本树：https://github.com/LUOaini1213/civil-buddy

---

## 两套入口

| 入口 | 地址 | 用途 |
|------|------|------|
| **Civil Buddy 工作台** | http://127.0.0.1:8765 | 召唤专家、投标/施工草稿、装箱作业单 |
| **主线 C · 投标应答 + 交付** | http://127.0.0.1:8000 | 招标要点 → 响应矩阵 → 装柜证据（草稿） |
| **工程装柜台** | http://127.0.0.1:8000/workbench | 成箱 → HITL → 拼柜 3D / CoG |

### 1) Civil Buddy 工作台

```powershell
cd workbench
# DeepSeek 写在 gitignored 的 demo/.env
cargo run --release --bin civil-workbench
```

Python 参考实现：`demo/`（`uvicorn app:app --host 127.0.0.1 --port 8765`）。

Grok skill（怎么起草）：`skills/civil-buddy`。MCP（能调什么）：`python demo/mcp_stdio.py --pack <大类>`。  
**全量产品规划书**：[docs/civil-buddy/product-plan.md](docs/civil-buddy/product-plan.md)。切片执行：[product-completion-plan.md](docs/civil-buddy/product-completion-plan.md)。

### 2) 装箱引擎（pack-ship 的计算器）

```powershell
pip install -r requirements.txt
python scripts/demo_one_shot.py              # 冒烟，无需 API Key
uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

工作台默认在同一仓库里找引擎：`PACKING_AGENT_ROOT` = 本仓根。也可另开网关：

```env
PACKING_AGENT_URL=http://127.0.0.1:8000
```

详见 [docs/civil-buddy/packing-agent.md](docs/civil-buddy/packing-agent.md)。

---

## 仓库结构

```
workbench/           # Civil Buddy Rust 工作台 + MCP
demo/                # 专家知识库 kb/ + Python 参考实现
skills/civil-buddy/  # Grok skill
packing_assistant/   # 装箱 harness（Team A 成箱 + Team B 拼柜）
gateway/ + frontend/ # 装箱 HTTP / UI
docs/civil-buddy/    # 工作台设计、专家名册
docs/                # 装箱架构与产品主线
```

**原则（两套入口共用）：** tools compute numbers; the model only routes.

---

## 装箱引擎（原 packing-agent）

架构：**大 Team ⊃ Team A（成箱）+ Team B（拼柜）** · Harness 0.6.4  
NL → IntentSpec → 白名单 tools → HITL → 影子评测。

```powershell
python scripts/demo_one_shot.py --all
python scripts/run_hard_fail_cases.py --smoke
```

文档：[docs/harness-design.md](docs/harness-design.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/product-mainline-tender-delivery.md](docs/product-mainline-tender-delivery.md)

---

## 环境变量

复制 `.env.example` / `demo/.env.example`，不要提交密钥。

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | Civil Buddy 成稿 / 装箱 llm_toolcall |
| `PACKING_AGENT_URL` | 装箱网关（可选） |
| `PACKING_AGENT_ROOT` | 默认本仓根，一般不用设 |
| `CIVIL_PORT` | 工作台端口，默认 8765 |

---

## 明确不做

桌面键鼠、微信/飞书、Rhino/Civil3D 改模、注册工程师签认、编造条款/单价/xyz。规范全文不进仓库。
