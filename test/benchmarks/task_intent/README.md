# 任务意图基准：这句话是要东西，还是在提问

给 `packing_assistant/runtime/task_router.py` 的意图判定打分（`steps` 模式和网页工作台共用它；`--mode model` 由模型自己判断，不走这里）。全部句子为本基准编写。

```bash
python scripts/eval_task_intent.py --variant all              # 开发集：每组词带来什么、放进来什么
python scripts/eval_task_intent.py --variant all --heldout 2  # 没见过的那一轮
python scripts/eval_task_intent.py --show                     # 现行规则错在哪几句
python scripts/eval_task_intent.py --check                    # CI 下限（npm run check 里的 task-intent-bench）
```

三个数：总准确率；**请求召回**（漏掉一个请求 = 用户要文件、得到一段解释，便宜）；**误执行数**（把提问或拒绝当成请求 = 写了不该写的文件，贵）。CI 下限：开发集准确率 ≥ 0.95 且误执行 0；第二轮留出集准确率 ≥ 0.90 且误执行 0。

## 三个文件，三种身份

| 文件 | 身份 | 现行规则 |
| --- | --- | --- |
| `cases.json`（85 句） | 开发集：边写规则边写的，读 1.000 是必然，不要引用这个数 | 1.000 / 1.000 / 0 |
| `heldout.json`（26 句） | 第一轮留出：第一版词表冻结之后、运行之前写的。**冻结的第一版**在上面是 0.885 / 0.846 / 误执行 1。三句错的已并入开发集并据此改了规则，所以它不再是「没见过」 | 1.000 / 1.000 / 0 |
| `heldout2.json`（18 句） | 第二轮留出：第一轮的修正冻结之后、运行之前写的。**现行规则没见过它** | 1.000 / 1.000 / 0 |
| `heldout_en.json`（28 句，英文） | 英文第一轮：英文规则写出来之前写的，但写句子和写规则是同一个人，**不算盲测**。改动前 0.429 / 0.000 / 0、选岗 0.062 | 1.000 / 1.000 / 0，选岗 1.000 |
| `heldout_en2.json`（28 句，英文） | 英文第二轮：英文规则冻结之后、运行之前写的，带本地说法（do up、MOS、pls）和中英夹杂。改动前 0.393 / 0.056 / 0、选岗 0.111 | 0.786 / 0.667 / 0，选岗 0.889 |
| `heldout_en3.json`（29 句，英文，三分之二是陈述） | 英文第三轮：评审发现第一版英文规则把状态消息当请求之后、修正写出来之前写的；修正也是同一个人写的，**不算盲测**。改动前 0.724 / 0.000 / 0、选岗 0.000；第一版英文规则 0.759 / 1.000 / **误执行 7**、选岗 0.750 | 1.000 / 1.000 / 0，选岗 1.000 |

英文三轮由 `python scripts/test_english_intents.py` 打分（多报一个「选岗」：run/both 句最终用的岗位对不对）。第二轮漏的 6 句都是漏成提问（便宜的方向）：「do up」「Need a …」「Do the …」「Site diary 26/9: …」「go through」「… notes for」；选岗漏 MOS、lifting plan。按上面的流程，要修就先把句子钉进 `scripts/test_english_intents.py`，再写第三轮。

第一版英文规则的毛病（评审 2026-09-26，句子钉在 `STATEMENTS` / `GOVERNED`）：句首动词不看宾语（「Plan B is …」「Update on the tender: …」「Review comments are …」都成了请求）、交付物名词后接 for/on 就算请求（「Daily report for yesterday was wrong」）、契约里 `you review` / `Draft a` 这类子串命中「you reviewed」「Draft approved」；选岗取原文最早的英文短语，于是「For the tender, draft a method statement」选成招标解析、「2 containers arrived, write the daily report」选成装柜。现行：动词后要跟限定词 / 交付物 / 文件名；交付物名词后要么是冒号，要么整句没有 was/is/approved 这类状态词和星期、钟点；选岗取请求动词之后的第一个英文短语；有中文岗位词时英文短语不参与；契约删掉裸 `container`，改收 `containers for` / `container for` / `how many containers`。最后这个是为第二轮「Work out how many containers we need …」加的（删掉裸 container 后它选不到岗），所以第二轮这一句已不算没见过。仍错的已知一句：「Check the tender closes on Friday」会执行（动词 + the，句中的 closes 认不出来）。

改动前（只有 13 个书面动词）：开发集 0.718 / 0.436 / 误执行 2，第一轮留出 0.500 / 0.077 / 1，第二轮留出 0.556 / 0.111 / 0。也就是说，工地上常见的说法（「编一份」「给我一份」「出个」「弄一下」）十句里有八九句被当成了提问。

## 消融（开发集）

| variant | 准确率 | 请求召回 | 误执行 |
| --- | --- | --- | --- |
| core（改动前） | 0.718 | 0.436 | 2 |
| + 起草类口语动词 | 0.824 | 0.692 | 3 |
| + 「给我一份 / 来个 / 出个」 | 0.941 | 0.949 | 3 |
| + 疑问标记（谁、多久、多少、要不要、还是、句末吗/？） | 0.976 | 0.949 | 0 |
| + 「讲讲 / 说明」算阅读请求 | 1.000 | 1.000 | 0 |
| + 英文（现行；中文三个集合的每一句都不变） | 1.000 | 1.000 | 0 |
| 现行但去掉新增疑问标记 | 0.965 | 1.000 | 3 |

读法：动词表和疑问标记必须一起加。只放宽动词，「台账多久更新一次」「出一份方案要多久」就会被执行掉；改动前的规则其实已经在执行「出一份方案要多久」「要不要做专家论证」这两句，是新增的疑问标记把它们收了回来。

## 加用例

规则是词表，词表永远不全。流程固定：

1. 发现漏判或误判，**先**把句子加进 `cases.json`（带上同一个词的反例：是请求的和不是请求的各一句），跑 `--variant all`。
2. 改 `task_router.ACTION_VERBS / QUESTION_MARKS / READ_VERBS`，单字动词必须带量词或「一下」的前瞻，不要裸加。
3. 规则定稿后，**不看结果**另写一轮留出用例（`heldoutN.json`），报那一轮的数。留出集上发现的错并入开发集再改，并在该文件的 `note` 里写明它已经被看过。

已知取舍：「还是」算疑问标记，所以「还是出一份吧」会被漏成提问（便宜的方向）。
