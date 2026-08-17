# 引用与假设格式

规范性引用一行：`全名 | 年份 | 条款 | 状态`。

- 状态只能是 `verified` / `unverified` / `unspecified_clause`。
- `verified` 仅当 `scripts/verify_clause.py` 在用户提供的 PDF 文本中抽到条款词。扫描件且无 OCR → `unspecified_clause`。
- `codes.md` 列为 `UNAVAILABLE` 的规范不得写入「编制依据（已核实）」。
- 正文若写「第 x.x.x 条」，同一字符串必须出现在 `citations.md`。

最终假设号由主会话（或以后 Rhai）顺序分配，从 `A001` 起。禁止成品出现 `ASSUMPTION-012`。正文受影响处写 `[A001]`。

```markdown
> A001
> 内容: 临边高度未由用户或图纸给出
> 原因: project pack 与用户消息均无高度
> Owner: user
> 影响: 栏杆选型与验算整节保持待填
```
