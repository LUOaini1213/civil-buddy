# 招标要求 ↔ 投标响应对照基准

`cases.json` 是给 `packing_assistant/tools/tender_response_match.py` 打分用的人工标注集。全部句子为本基准编写，不含任何客户资料。

```bash
python scripts/eval_tender_response_match.py --variant all    # 消融表：每个机制贡献了什么
python scripts/eval_tender_response_match.py --show           # 列出漏掉的和多连的
python scripts/eval_tender_response_match.py --check          # CI 下限（npm run check 里的 tender-response-bench）
```

## 标注口径

每个 case 有 `tender`（招标句子）和 `response`（投标响应句子）两个数组，下标从 0 起。

- `links`：`[招标句下标, 响应句下标]`。标准是「审标的人应该被带去看这一句」——响应在回应同一条要求，**不管回应得合不合格**。「工期60日历天」对「供应商自述工期999日历天」是一条 link。
- `conflicts`：`links` 的子集，响应写的数没有满足招标写的数。方向以招标原文的比较词为准（不少于 / 不超过 / within / not less than），原文没写时按主题：工期、交货期、货载取上限，质保期、有效期、业绩取下限，保证金取相等。满足要求的数（90 天的工期报 85 天）**不算**冲突。
- 解析器抽不出来的招标句（目前如「项目经理须具备一级注册建造师资格」「投标有效期90天」不带 ★ 时）没法被对照。可以写进 case，评测会把落在这种句子上的 link 计入 `gold_on_lines_with_no_row`，召回率照样按全部 link 算，不美化。

## 加用例

先加用例、跑 `--variant all` 看数字，再决定要不要动匹配规则。重点补两类：

1. **干扰项**：只和招标句共享套话的响应句（「近三年无重大安全事故」对「近三年类似项目业绩」）。精确率只有在有干扰项时才测得出来——这个基准最初没有干扰项时，「共享 2 个二字组」看上去是满分。
2. **真实写法**：数值换了单位、一句里两个数、英文条款、日期（「2026年12月31日前完工」不是工期）。

改了规则之后如果某个机制的数字变了，同步更新模块 docstring 里的表和 `ABLATIONS` 旁的注释。
