# Agent Middleware · 一页架构 + 3 分钟演示

赛道 1：中间件跑在 **Runtime**，不在 prompt。Host = Civil Buddy。  
`submit_blocked=true`。不判定可以投标 / 可以开工。密钥不进 git。

## 一页架构

```text
                    用户 / Host（TUI · app · MCP）
                              │
                              v
                 Agent Runtime  `run_agent`
                              │
         ┌──────── middleware onion (civil.middleware.v1) ────────┐
         │  permission → sandbox → hitl → tool → audit → cost     │
         └────────────────────────┬───────────────────────────────┘
                                  │
                    ToolEngine.execute  （写盘才过沙箱）
                                  │
              ┌───────────────────┼───────────────────┐
              v                   v                   v
         岗 exclusive        tender.parse         pack-ship 投影
         未确认 0 份稿       只抄 exact_text      断线四字段 UNSPECIFIED
```

| 层 | 代码 | 行为 |
|----|------|------|
| permission | `civil_config.decide_gate` | chat 放行；`read-only` 不成稿；无 `danger-full-access` |
| sandbox | `sandbox.py` + ToolEngine | 只许作业根；拒 `.env` / 密钥路径；拒 generic spawn。**不是** Seatbelt |
| hitl | `high_risk_unconfirmed` | 高风险写盘须确认句；未打 → 0 份稿 |
| tool | ToolEngine | 数字只走工具；模型只路由 |
| audit | Bus + `run_id` + `middleware.decisions` | 每层可回放 |
| cost | `max_steps` · `duration_ms` | 超步失败，不空转 |

评委口播一句：闸在后端，prompt 改不掉。

## 3 分钟现场演示

不需要 API Key。仓库根：

```powershell
python scripts/demo_agent_middleware.py
npm run check
```

| 分钟 | 动作 | 必须看见 |
|------|------|----------|
| 0:00–1:00 | 正常：问 GST | `intent=chat` `wrote=false` 回复含 **9%** · `middleware.chain` 五层 |
| 1:00–2:00 | 拒绝：写专项方案、不勾确认 | `hitl_pending=true` **0 份稿** · 确认句原文 |
| 2:00–3:00 | 恢复：装箱无 solver | `can_fit` / `mid50` 字面 **UNSPECIFIED** · 密钥探测 `permission_denied` 且 `.env` 不存在 |

口播禁句：可以投标、可以开工、中标率、GeBIZ 代交。

## 复现

```powershell
git clone https://github.com/LUOaini1213/civil-buddy.git
cd civil-buddy
pip install -r requirements.txt
npm run check
```

验收脚本：`scripts/test_agent_middleware.py`（`npm run check` 已包含）。
