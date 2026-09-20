# post_content —— 用户说的话，有没有落到该落的栏位

`scripts/eval_post_scorecard.py` 量的是「交付物有没有该有的栏、占位符有没有留住」。一份把用户整句话
粘进一个单元格、其余全填 TBD 的草稿，能全过。这个基准量的是另一半。

一条用例 = 一句工地上的人真会打的话 + 这句话里的**事实** + 每个事实该进的**栏位**。判定：

| 判定 | 含义 |
| --- | --- |
| `placed` | 出现在 ≤40 字的表格单元格或 `标签：值` 行里，且所属列头 / 行键 / 标签能匹配该事实的字段正则 |
| `misplaced` | 在短栏位里，但在错误的列头下（比一个 TBD 更糟：它把一个对象的数安到了另一个对象头上） |
| `dumped` | 只出现在长单元格或长行里——整句被粘进去了，没被解析 |
| `echo_only` | 只出现在「用户原文」回显段 |
| `missing` | 哪儿都没有 |

另外统计 `pasted_cells`（结构化栏位里装着请求原文片段的个数）和 `forbidden`（不该出现的结论词）。

用例由代理按每岗的 SKILL.md、KB README 字段表和行业词汇写成，再经机械校验：每个 `value` 必须是请求里
**恰好出现一次的字面子串**，`field` 必须能编译、不能宽到匹配任何列头。字段正则描述的是「一份称职的
交付物该把它放哪」，不依赖当前实现的列头措辞。

    python scripts/eval_post_content.py                  # cases.json，按岗位一行
    python scripts/eval_post_content.py --post cost -v   # 每个未落位事实一行
    python scripts/eval_post_content.py --show cost-02   # 打印该用例的交付物
    python scripts/eval_post_content.py --set heldout    # 规则冻结后另写的留出集

## 基线（2026-09-20，38 岗 112 例 886 个事实）

| | placed | micro | misplaced | dumped | echo_only | missing |
| --- | --- | --- | --- | --- | --- | --- |
| 改造前 | 165 | 0.186 | 18 | 140 | 37 | 526 |

其中 `warehouse` 是参考改法（5/5）；未改的岗位最高 0.33，有 3 个岗位为 0。
