# 岗位交付物：把用户说的话，放进该放的栏位

> 2026-09-20。相关代码：`packing_assistant/post_facts.py`、`scripts/eval_post_content.py`、
> `scripts/test_post_content.py`、`test/benchmarks/post_content/`。

## 1 问题

66 个岗位的 `SKILL.md` 和 `demo/kb/` 知识库是齐的，章节骨架也是齐的。缺的是中间那一步：**把用户这一
句话拆开，放进表格的列里**。

工地上的人是这么打字的：

```
螺纹钢 HRB400 Φ20 本周入库 35 吨，领用 12 吨，盘点差 0.3 吨，仓管员张伟
```

改造前，仓管岗的交付物是这样的：

| 物资 | 入库 | 出库 | 结存 | 备注 |
| --- | --- | --- | --- | --- |
| 帮我写一份仓库收发存台账口径：螺纹钢 HRB400 Φ20 本周 ，领用 12 吨，差 0.3 吨，仓管员张伟 | 35吨 | TBD | TBD | 待填 |

整句话被粘进了「物资」格，「领用 12 吨」原地留在句子里没进「出库」列，张伟不知去向。
两类写法各有各的塌法：

- `expert_turn.py` 一族：按 `；`／换行切块，每块取**一个**数字 → 整句进一格，其余 TBD。
- `post_drafts/*.py` 一族（30 个岗）：只认 `标签：值` 行或 Markdown 表 → 一句连贯的话什么也匹配不上，
  交付物是一张**全 UNSPECIFIED** 的漂亮骨架，连用户原文都没回显。

已有的 `eval_post_scorecard.py` 量的是「该有的栏在不在、占位符留没留住」——上面这两种草稿都能全过。

## 2 量法

`test/benchmarks/post_content/` 是新基准。一条用例 = 一句真人会打的话 + 这句话里的事实 + 每个事实**该进
的栏位**（写成正则备选，描述的是「一份称职的交付物该放哪」，不绑当前实现的列头措辞）。判定见该目录
README。关键是 `misplaced`：值进了短栏位但挂在**别的对象**名下——这比留个 TBD 更糟，所以门禁单独拦它。

每岗三条，覆盖三种写法：整句、分行、以及一句里**两个对象**且缺字段的「messy」——后者专门抓
「甲材料的数被安到乙材料行上」。

```bash
python scripts/eval_post_content.py                  # 按岗位一行
python scripts/eval_post_content.py --post cost -v   # 每个未落位事实一行
python scripts/eval_post_content.py --show cost-02   # 打印该用例的交付物
python scripts/test_post_content.py                  # 门禁：对着 floor.json 卡回退
```

## 3 共用层 `post_facts`

写岗位的人不该各写一遍「数字后面跟不跟单位」。`packing_assistant/post_facts.py` 提供的全是**只做切分、
不做解释**的原语：

| 函数 | 给你 |
| --- | --- |
| `clauses` / `items` | 逗号级 / 句行级切块（千分位逗号不切） |
| `quantities` | 数字 + 单位，**原样**。`HRB400`、`C35`、`Φ20`、`3#楼`、`GB 50010`、`K3+200`、日期里的数字都不算量 |
| `column_quantities` | 一个子句里「哪个数属于哪一列」。长关键词优先（`盘点差` 不是 `盘点`），一个数只用一次 |
| `object_rows` | 一句话里几个对象 → 几行。不带新名字的子句归**前一个**对象，绝不归下一个 |
| `labelled` | `标签：值`、`标签 值`、`标签为值`，行首标签保留其后的逗号；三字以上的标签还认 `责任人刘洋` 这种紧挨着的写法 |
| `person_for` | 带职务的人名（`仓管员张伟`、`王建国（质检员）`）。必须以常见姓氏开头，所以「仓管员今天请假」不会被当成人名 |
| `dates` / `periods` / `deadline` / `clock_times` | 日期、`本周`、`要求 2026-09-26 前` 里的期限、`14:30` |
| `places` / `specs` / `versions` / `doc_codes` | `3#楼`、`B1层`、`5-7轴交C轴`、`K3+200`；`HRB400`、`600×300`；`V2.3`；`CL-017` |
| `table_cell` | 用户的话进表格前的转义（换行、`|`、HTML） |

**铁律**：这一层返回的每个值都是用户原文里的一段**字面文本**。不求和、不换算、不推断、不填默认值。
用户没说的，写手继续留 `TBD` / `待填` / `[A001]` / `UNSPECIFIED`。这条铁律让
`tools/number_provenance` 的数字溯源守卫继续成立——草稿里的每个数都能指回原文。

## 4 改一个岗位

以仓管为参考（`_WH_COLUMNS` / `_parse_wh_rows` / `_warehouse_md`）：

1. 先量：`python scripts/eval_post_content.py --post <岗位> -v`，记下改造前的数。
2. 声明这个岗的**列关键词**（`入库 / 进场 / 到货`…）和**行级标签**（单据号、批次、供应商…），
   用行业词汇，不要抄基准里的句子。
3. `object_rows(text, 列关键词)` 拿到行；每行的 `source` 是它来自的那段原文，用来在行内查标签和人名。
4. 填表时，用户没给的列保持原来的占位符**不变**。
5. 再量一遍；`scripts/test_expert_turn.py` 必须 PASS；空输入和乱输入都要出完整骨架且不崩。

不要做的事：改 `post_facts.py`、改 `_SIMPLE_DRAFTS` 注册表、删改已有的列和免责声明、
在源码里写基准用例的字面量（留出集会专门抓这个）。
