# 本地研究工具演示

这是 Civil Buddy 的小型本地集成入口。四个只读工具加入原 `tool_registry`、`default_engine` 和版本化工具契约；执行仍经过原权限策略、预算、超时和审计。原产品的写盘、专属岗位与人工签认门禁没有修改。

## 启动和依赖

先启动 JPJ 项目 `127.0.0.1:8777` 及技术资料项目 `127.0.0.1:8778`。合入本地主仓后运行：

```powershell
Set-Location 'C:/Users/LW/civil-buddy'
$env:PYTHON_DOTENV_DISABLED = '1'
& 'C:/Users/LW/civil-buddy/.venv/Scripts/python.exe' -m packing_assistant.runtime.research_demo
```

打开 `http://127.0.0.1:8779`。可换成已安装项目依赖的 Python；源码及输出来自命令执行时所在的 checkout。

确定性模式不调用模型。可选的本地模型模式仅连接 `127.0.0.1:11434/api/chat`，使用已安装的 Ollama `qwen2.5:3b`，不下载模型、不使用外部 API key。最多 3 轮、4 次工具调用；模型选错工具或缺参数时真实记录失败，不生成替代数据。

## API

- `GET /health`：入口状态；不声称两个来源服务已就绪。
- `GET /api/tools`：原注册工具的输入、输出 schema。
- `POST /api/run`：`{"tool":"jpj.query","arguments":{"query_id":"brand_compare","parameters":{"start_month":"2026-01","end_month":"2026-08","makers":["BYD","TESLA"],"metric":"registrations"}}}`。
- `POST /api/model`：`{"prompt":"对比2026年1月至8月BYD和TESLA的汽车登记量，给出数据来源"}`。
- `GET /api/trace/<run_id>`：本进程保留的最近 100 次完整事件；所有 run 的归档在 `output/runs/<run_id>/trace.jsonl`。

四个注册工具为 `jpj.catalog`、`jpj.query`、`literature.catalog`、`literature.search`。JPJ 使用固定 SQL 模板；工具参数不能提交 SQL、URL、文件路径或命令。模型端将每个固定查询拆成更简单的扁平函数 schema，再通过可信适配层将原参数完整嵌套为 `jpj.query` 参数；不补日期、不丢字段，原始 `tool_calls` 和映射均进入 trace。

## 数据边界与证据

JPJ 是汽车注册量，不能称销量、批发 TIV、进口量或库存。冻结的 MySQL 数据为边际聚合，不能回答品牌 × 燃料交叉查询。参数需显式月份（可接收自然语言中的 YYYY-MM、YYYY年M月至N月）；返回值保留实际 SQL、绑定值、规范化业务参数、来源版本与哈希。

技术资料返回真实原文、来源 URL、归档全文 SHA-256、语料版本、原文位置、实体和候选关系。候选关系是规则抽取结果，需要人工核对，不是科学因果结论。段落哈希、字符长度、quote 与 end-exclusive 字符位置均在接入层校验。

来源内容在模型请求中仅作为 `tool` 消息。UI 使用文本节点渲染原文、模型文本和错误；不将外部内容写入 HTML。调用只允许固定 loopback 端点，禁用代理与重定向；服务校验 Host/Origin，不提供任意 URL 转发。

模型路由支持限定的中英文模板，不是通用 NLU。输入守卫先通过注册的目录工具取得来源品牌与燃料词表，再将原问句中的有序月份区间、品牌集合、燃料与排行条件逐项绑定到查询类型和参数；模型增加、删除、改变筛选条件均拒绝。未知品牌、限定、否定或含混范围要求追问。销量/TIV 和品牌 × 燃料交叉查询拒绝。守卫是确定性代码，不能计作模型理解正确。

## 验证与真实日志

```powershell
& 'C:/Users/LW/civil-buddy/.venv/Scripts/python.exe' scripts/test_readonly_sources.py
$env:PYTHON = 'C:/Users/LW/civil-buddy/.venv/Scripts/python.exe'
npm run check
```

新增测试覆盖缺参、错口径、品牌 × 燃料、额外字段、类型与边界、上游拒绝、坏响应、超时、重定向、代理隔离、逐字引用、模型映射和原有权限门禁。它们使用显式 fixture，不作为真实数据结果。

两个来源服务启动后可执行 `scripts/verify_research_tools_live.py`，追加真实调用到 `output/research-live-evidence.json`；加 `--model` 会依次执行四条真实中文模型任务，并追加到 `output/research-model-evidence.json`。该脚本是证据采集器，须检查各 case 的 status、参数和原文；不能把脚本退出视为任务全部成功。`--cases` 可选择部分 case，失败尝试保留。

浏览器交互验收与源数据独立 oracle 核对由集成验收另行记录。
