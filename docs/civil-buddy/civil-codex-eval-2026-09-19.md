# 土木版 Codex 对位 · 2026-09-19（只评 CLI 这一面的变化）

接 [civil-codex-eval-2026-08-25.md](civil-codex-eval-2026-08-25.md)。那一页的总判是「有纪律的内部起草搭子 + Codex 骨架：部分合格」，并把 **H5 模型隐式选用** 列为延期。这一页只记 08-25 之后 CLI 这一面关掉了什么、还差什么。官方门户事实、行业总判句不在本页范围内，**不改**。

禁止写成产品能力的话照旧：中标率 +N%、可以投标、可以开工、代签、代交。

## 1. 08-25 的核心缺口：CLI 里没有模型

08-25 那页写的是「隐式选用：规则，不是 LLM」。更准确的说法是：`civil` 这条路径 **从头到尾不调模型**——`run_agent` 是规则路由 + 模板成稿，只有网页工作台用 LLM。Codex 的本体是「模型驱动的循环 + 沙箱/审批 + 事件流 + 在工作目录里干活」，所以缺的不是某个功能，是循环本身。

## 2. 现在的对位

| Codex | civil 现状 | 判定 |
| --- | --- | --- |
| 在仓库里工作，读 `AGENTS.md` | 在**工地文件夹**里工作：`civil init` 写 `CIVIL.md`，就近向上找、子文件夹覆盖、32 KiB 上限；会话与文书落在 `<工地>/.civil-buddy/out`；`-C <dir>` | **通过**（#35） |
| 模型驱动的循环：计划 → 工具 → 回答 | `--mode model`：`update_plan` / `load_skill` / `search_kb` / `list_job_files` / `read_job_file` / `run_skill` / `pack_plan` / `tender_compare`，步数上限、重复调用拒绝、端点不通即如实回答 | **通过**（脚本化模型 24 项测试 + 本机 Ollama 实跑） |
| 模型按 description 选 skill，选中才读 `SKILL.md` | 目录（≤ 8,000 字）进提示词，`load_skill` 读全文；`$id` / `--skill` 点名则直接给 SOP | **通过**（原 H5） |
| `codex exec --json` | `civil exec --jsonl`：`thread.started → turn.started → plan.updated / item.* / approval.required / guard.flagged → turn.completed`，带工具参数、用量、溯源结果；流程内部再跑的一轮标 `nested`，不重复报 turn | **通过** |
| 审批：危险命令前当场问 | 高风险岗位写盘前当场要确认句（TUI 内联；`exec` 不提示，如实返回 `approval_required`）；`read-only` 只读不写 | **通过**（应用层） |
| `resume` 带着对话继续 | thread 旁边存 rollout（`<thread>.rollout.jsonl`），`civil resume` 把尾部交给模型 | **通过** |
| 默认就是模型驱动 | 默认 `steps`，不调模型；环境里放着 Key 也不会自己切过去 | **有意不同**：内网、无 Key、可复现的 CI 都靠这条 |
| 模型自己写代码/文件 | **模型写的字进不了成稿**：`run_skill` 没有自由文本参数，交给确定性流程的只有用户原话和他文件夹里的资料 | **有意不同**：「数字只由工具算」是本产品的前提 |
| 系统级沙箱（Seatbelt / bwrap） | 仍是应用层写根 + 拒 `.env` + 拒 generic spawn | **部分**（未变，不装作有） |
| 全屏 TUI、原生 App、IDE 商店扩展、Plugins、Cloud | 无 | **不做 / 缺口**（未变） |

## 3. Codex 没有、土木必须有的一道：数字溯源

模型驱动以后，「模型不报数」只能靠提示词要求，所以加了一道确定性检查（`packing_assistant/tools/number_provenance.py`）：回复里的每个工程量和条款号，必须能在本轮看得见的东西里找到（用户原文、CIVIL.md、工具结果、读过的资料）。找不到的先让模型改写一次，改完还在的，原样点名给用户。

先有基准后有规则（`test/benchmarks/number_provenance`，34 例）：

| variant | P | R |
| --- | --- | --- |
| 只认一模一样的数 | 0.698 | 1.000 |
| + 四舍五入 | 0.732 | 1.000 |
| + 百分数 ↔ 小数 | 0.882 | 1.000 |
| + 同量纲单位换算（现行） | 1.000 | 1.000 |
| 去掉型号/标准号遮罩 | 1.000 | 0.967 |
| 去掉计数分族 | 1.000 | 0.900 |
| 去掉条款号检查 | 1.000 | 0.967 |

34 例是自编用例加本机小模型的真实输出，**不是**对任意模型、任意文体的保证；它能说明的是每个机制各管住了哪一类错，以及现在哪一类已经有用例盯着。

## 4. 实跑（本机 Ollama `qwen2.5:3b`，CPU）暴露并已修的

1. 工具结果是 JSON 文本，`\n` 后面紧跟的数左邻是字母 n，被当成型号的一部分读不出来 → 复现用例上精确率 1.000 → 0.871，修后回到 1.000。
2. `资料/packing.csv` 被模型写成 `packing.csv`，整轮放弃 → 文件名在文件夹里唯一时直接对上；有两个同名文件时不猜。
3. 裸键 `payload_kg`（柜体额定载重）被说成「货物总重」。**数字有出处、含义是错的，溯源查不出这种错** → `pack_plan` 只给模型带中文标签的报告行和含义不会读错的键。
4. 诱导它凭记忆报数：答了 `30MPa`、`1.2 米`，被点名并改写掉；已收进基准。
5. 模型把确认句抄进了回复 → 确认句只有用户亲手输入才算数，模型文字里的一律去掉。

小模型的局限如实记：3B 模型会选错工具（给日报调过 `pack_plan`），CPU 上带 8,000 字目录的首轮要几十秒。线束能兜住的是「选错了也写不出错数、读不到夹子外面、过不了审批」，兜不住的是它不够聪明——换大模型是配置问题（`CIVIL_API_BASE` / `CIVIL_MODEL`），不是代码问题。

## 5. 仍不合格 / 未做

1. `steps` 模式下 `civil exec "装箱 <文件>"` 仍不走真实装箱引擎（`_plan_calls` 只传文本）；招标解析同样不读点名的文件。模型模式已经走真引擎。
2. 模型模式只在 CLI / TUI / `civil serve`；网页工作台仍是它自己的 `run_expert` 循环，两套循环尚未合并。
3. 溯源只查数在不在，不查标签贴得对不对（见 §4.3 的处理方式）。
4. 系统级沙箱、原生 App、商店扩展、Plugins、Cloud：未做，多数明确不做。
5. 当「可投标 / 可开工」：不合格，且禁止这么宣传。

总判相对 08-25：**Codex 的循环这一块从「骨架」变为「通过」**；整体仍是「部分合格」，原因见 §5 与 08-25 页 §5 的第 3–6 条。

复验：

```bash
python scripts/test_model_loop.py
python scripts/eval_number_provenance.py --variant all
CIVIL_API_BASE=http://127.0.0.1:11434/v1 CIVIL_API_KEY=ollama CIVIL_MODEL=qwen2.5:3b \
  python -m packing_assistant.civil -C <工地文件夹> --mode model exec --jsonl "整理日报，…"
```
