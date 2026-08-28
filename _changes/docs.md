# 文档与 Skills 质量整理记录（2026-08-25）

## 失效引用修复

- `docs/overall-architecture.md`：`./phase2-agent2-packer-api.md` → `./archive/phase2-agent2-packer-api.md`（文件已归档）。
- `docs/archive/phase2-architecture.md`：`./overall-architecture.md` → `../overall-architecture.md`（archive 目录内相对路径错误）。
- `docs/civil-buddy/enterprise-experts.md`：`docs/yibiao-mcp-map.md` → `docs/civil-buddy/yibiao-mcp-map.md`。
- `docs/civil-buddy/live-eval-2026-08-17.md`：`docs/live-eval-2026-08-17.json` → `docs/civil-buddy/live-eval-2026-08-17.json`。
- `docs/volume-algorithm.md`：`docs/architecture-update-plan.md` → `docs/archive/architecture-update-plan.md`。
- `docs/CHANGELOG-v0.4.md`：`docs/competitive-landscape.md` → `docs/research/competitive-landscape.md`。
- `skills/civil-buddy/SKILL.md`：`docs/packing-agent.md` → `docs/civil-buddy/packing-agent.md`。

## 结构统一（.agents/skills，66 岗 SKILL.md）

统一后 66 份全部为同一节序：何时上场 / 必问输入 / 交付骨架 / 额外禁令 / 独有工具 / 知识分层 / 硬规则（摘要）；frontmatter（name/description/metadata 七字段）与硬规则 7 条本已一致，未改动。

- `pm-daily/SKILL.md`：删除重复的「## 何时上场」「## 必问输入（缺则 [Axxx]）」两节，将其中手写的触发场景与必问输入条目并入模板对应小节；交付骨架段落分段修正。内容只做合并，未新增断言。
- `quality/SKILL.md`：补「## 额外禁令」，内容取自本文件已有表述（不给合格结论、不替代专项方案 11 章）。
- `supervision/SKILL.md`：补「## 额外禁令」，内容取自本文件已有表述（非监理指令、回复须附通知原文）。
- `survey/SKILL.md`：补「## 额外禁令」，内容取自本文件已有表述（无用户坐标不编点号、数字须注来源）。

## 表述修正

- `docs/civil-buddy/github-wheels-eval-2026-08-17.md`：第二轮深挖表 marker / IfcOpenShell 两行缺列（星数与协议挤在同一格），拆回 4 列与表头对齐。
- `docs/civil-buddy/product-improvement-handbook.md`：P2 表表头 3 列而各行仅 2 列，表头改为「做什么 / 明确不做」两列（行内容未动）。
- `docs/research/research-triad-papers-github-industry-2026-07.md`：3.3 节两行多出一列（2 列表头），将第三格并入「含义」列，内容不变。
- `docs/README.md`：CHANGELOG-v0.5 条目说明由「含 0.6.2」改为「至 0.6.4」（该文件实际记至 v0.6.4+，与 `packing_assistant/config.py` 的 HARNESS_VERSION=0.6.4 一致）。
- `README.md` / `AGENTS.md`：`civil app` / `civil mcp ...` 写法改为明确的子命令表述并注明 `python scripts/civil.py` 同义简写（仓库无已安装的 `civil` 命令入口，原写法直接敲会找不到命令）。

## 清理

- 无删除。链接自检脚本为临时件，检查通过后已删除（未入仓）。

## 核对但未改（结论记录）

- README / CONTRIBUTING / AGENTS / GOOD_FIRST_ISSUES / 给试用的人 / ide/README / docs/civil-buddy/GETTING-STARTED 引用的全部文件路径与脚本（含 19 个 `scripts/test_*.py`、`workbench/run.ps1`、`ide/*/mcp.json`、`.env.example` 等）均存在；命令片段与现仓一致。
- 「16 大类 / 66 岗」口径核对属实：66 个专家目录 + 1 路由器，metadata category 恰 16 类；路由器名册 66 行与目录、各岗 H1、大类名全部一一对应。
- 66 份 SKILL.md 引用的 `demo/kb/<category>/<id>/` 及其列出的 kb 文件全部存在。
- `skills/civil-buddy/` 内 references/examples/scripts 相对引用（按 skill 根目录约定）全部可解析；`bundled validate.py` 指宿主自带 docx 技能脚本，属外部件，保留原文。
- 全部自有 markdown（196 个文件）相对链接复检 0 失效。
