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
    python scripts/eval_post_content.py --set heldout_bid    # 留出集：文件名去掉 .json

## 基线（2026-09-20，改造前）

65 岗 193 例 1529 个事实：

| placed | micro | macro | misplaced | dumped | echo_only | missing |
| --- | --- | --- | --- | --- | --- | --- |
| 287 | 0.188 | 0.197 | 114 | 334 | 175 | 619 |

`warehouse` 是参考改法（5/5）。未改的岗位最高 0.42，最低 0。`misplaced` 114 是最刺眼的一项：
值进了短栏位，却挂在**另一个对象**名下——一句话里两种材料，甲的数被写进了乙的行。

门禁底线记在 `floor.json`；每完成一批岗位就上调，并在提交信息里写清新测得的数。

## 留出集

开发集满分不是成绩：规则是对着它调的。一个岗位改完、规则冻结之后，另写一份留出集，**写完才跑、只跑一次**，
对外引用那个首跑数。字段正则沿用 `cases.json` 里同类事实的模式，不迎合改造后的列头；写完做同样的机械校验
（value 恰好出现一次）。一份留出集的漏项一旦驱动了改动，它就算「见过」，只留在 `floor.json` 里当回归，
要新的成绩就再写一轮。

| 文件 | 岗位 | 首跑 | 现在 |
| --- | --- | --- | --- |
| `heldout_bid.json` | bid-parse / bid-tech / bid-compliance | 72/78 = 0.923 | 78/78，已见过 |
| `heldout_bid2.json` | 同上，换了一批轴 | 67/70 = 0.957 | 70/70，已见过 |
| `heldout_bid3.json` | 同上；「恰好出现一次」的校验写进了生成脚本 | 83/84 = 0.988 | 84/84，已见过 |
| `heldout_bid4.json` | 同上；量 2026-09-21 补的英文条款、不带标签的项目名、workhead、项目经理之外点了名的人 | 68/86 = 0.791 | 85/86，已见过 |

计分器读单元格时会 `html.unescape`：`post_facts.table_cell()` 把用户写的 `&` 转成 `&amp;`，Excel 导出和
Markdown 阅读器都会还原，事实是 `Housing & Development Board`，不是它的转义形式。

全岗位的留出集还没有写（此前这里写的 `--set heldout` 指向一个不存在的文件）。
