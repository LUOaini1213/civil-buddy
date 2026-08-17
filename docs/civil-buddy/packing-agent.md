# pack-ship × 本仓装箱引擎

Civil Buddy 与装箱引擎已在**同一仓库**。`pack-ship` 只抄工具回传的 N0 / used / can_fit；不编 xyz。

## 接通

默认同仓：工作台在 `workbench/`，引擎在仓库根的 `packing_assistant/`。一般**不用设** `PACKING_AGENT_ROOT`。

可选：另开网关（HITL / 3D UI）：

```env
PACKING_AGENT_URL=http://127.0.0.1:8000
```

装箱引擎：

```powershell
pip install -r requirements.txt
uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

工作台：

```powershell
cd workbench
cargo run --release --bin civil-workbench
```

打开 http://127.0.0.1:8765 ，召唤 **装箱拼柜 / pack-ship**，贴物料表，出《装箱作业单》。

`GET /api/health` 里有 `packing_agent` 探测。MCP：`--pack plant` 或召唤 `pack-ship` 时带 `pack-ship__plan` / `pack-ship__health`。

招标解析与装箱共用 sidecar：`workbench/scripts/run_packing_sidecar.py` 的 stdin 若为 `{"mode":"tender_parse","tender_text":"..."}`，走同一套 `run_tender_pipeline`（handoff / P0 / 技术标目录），不另写一套抽取。

## 边界

| 谁 | 做什么 |
|----|--------|
| packing-agent | `run_agent_pipeline`：成箱、N0*、3D、can_fit |
| Civil Buddy pack-ship | 作业单、CTU/CSC **标题**、把工具数字抄进 md |
| 模型 | 只编排，不写坐标、不拍柜数 |

未接通时作业单仍出，数字写 **UNSPECIFIED**。

## 不要做

- 不要把 packing-agent 的 `.env` / API Key 提交进 civil-buddy
- 不要把 `output/runs` 整目录拷进本仓
- HITL：sidecar 用 `enable_auto_confirm=true`（Civil Buddy 侧 pack-ship 风险为 low）；要人确认柜方案请直接开 packing-agent UI
