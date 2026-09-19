# 插件：把你们公司自己的岗位装进来

内置 66 个岗位是通用的。你们公司的周报格式、联系单抬头、内部口径，写成一个插件装进来，它就和内置岗位一样用：进技能目录、`$id` 或中文名点名、模型模式下按 SOP 办、出 Markdown / Word / Excel。

Codex 的插件是「技能 + MCP 服务器」，也就是带程序的。这里的插件**故意不带代码**：全是声明——SOP、表单模板、知识摘录。装一个插件不会运行任何东西，因为里面没有可运行的东西。

```bash
civil plugin validate examples/plugins/site-forms     # 只检查，不安装
civil plugin install  examples/plugins/site-forms     # 装到 ~/.civil-buddy/plugins（目录或 .zip 都行）
civil plugin install --job <目录>                      # 装进当前作业文件夹，随文件夹走
civil plugin list                                     # 装了什么、是否受信任、带来哪些岗位、有什么警告
civil plugin trust site-forms                         # 看过内容之后：按它自己标的风险级别执行
civil plugin untrust site-forms · civil plugin remove site-forms
civil "出一份项目周报，周次：第 12 周，部位：东桥3号墩，资料见 现场记录.txt"
```

## 一个插件长什么样

```text
site-forms/
  plugin.json                          {"schema": "civil.plugin.v1", "name": "site-forms", "version", "title", "description", "publisher"}
  skills/site-weekly/SKILL.md          岗位 SOP（Agent Skills 格式）
  skills/site-weekly/form.json         可选：表单字段
  skills/site-weekly/template.md       可选：成稿模板，{{key}} 是槽
  skills/site-weekly/knowledge.md      可选：知识摘录，search_kb 和问答会读
```

`SKILL.md` 的 frontmatter：`name`（必须等于目录名）、`description`（必填，进技能目录，模型和路由靠它选岗）、`title`（中文显示名）、`delivers`、`risk`（`low` | `high`，默认 `high`）、`aliases`（逗号分隔；4 个字以上的别名可直接路由）。

`form.json`：`{"fields": [{"key": "week", "label": "周次", "aliases": ["周期"], "required": true}]}`。

**填槽只有一种方式**：在用户这一轮的原话、以及任务里点名的资料文件里找 `标签：值`（到下一个逗号、分号、句号或换行为止）。没有表达式，没有计算，没有推断。找不到就是「待填」；必填而没给的栏，在稿子开头点名。内置槽：`{{project}}`、`{{jurisdiction}}`（来自 CIVIL.md）、`{{user_text}}`。

仓库里的 `examples/plugins/site-forms`（项目周报 + 工程联系单）可以直接装，也可以拿来改。

## 它不会变成后门，因为

| | |
| --- | --- |
| 不能顶替 | 技能 id 和内置岗位或已装插件重名，拒绝。手工丢进插件目录也不加载，`civil plugin list` 会写明原因。内置岗位的 SOP 永远读内置的那份 |
| 风险级别不由插件说了算 | **未受信任的插件，岗位一律按高风险**：每次写盘都要确认句，不管它的 SKILL.md 怎么标。`civil plugin trust` 之后才按它自己的标注 |
| 信任是你的，不是文件夹的 | 信任记在**你本人**的 `~/.civil-buddy/plugins.json` 里，键是插件内容的 SHA-256。别人给你的作业文件夹自带插件，它没法给自己授信；已信任的插件内容一改，信任自动失效 |
| 模板不能下结论 | 模板里写「可以开工」「验收合格」这类结论，校验不过（用的是模型回复那一道结论护栏；「本稿不判定可以开工」这种否认不拦） |
| 模板里的数字要亮明 | 模板作者写进去的数字（「保存期 24 个月」）不是这一轮的资料：安装时报出来，每份成稿末尾逐个注明出自哪个插件的模板 |
| 只认文档 | 只读取、只复制 `.md` 和 `.json`。别的文件（脚本、可执行文件）一律不读不装，并点名。zip 里往外爬的路径，拒绝 |
| 其余照旧 | 出稿走和内置岗位同一条流水线：应用层沙箱、`--sandbox-backend os` 的系统级沙箱、`submit_blocked=true`、Office 导出、`civil review` 都一样管着它 |

还要知道的：模型模式下，被选中的插件 SOP 会进模型的上下文。一个不怀好意的 SOP 可以试图带偏模型——但模型写的字本来就进不了成稿（`run_skill` 没有自由文本参数），回复还要过数字和结论两道护栏。这是结构上的限制，不是对 SOP 内容的审查；装之前请自己看一遍，信任之前更要看。

## 限制

- 没有代码，也就没有自定义计算、自定义解析。要算东西的岗位不是插件能做的，那是内置工具的事。
- 填槽是 `标签：值` 的字面匹配，不理解同义说法；别名写全一点。表格类的多行数据填不了，只能整段抄进一个槽。
- 不带 MCP 服务器。Civil Buddy 自己是 MCP 服务端（给 IDE 用），不是 MCP 客户端。
- 没有商店、没有自动更新、没有签名。分发就是发目录或 zip。

复验：`python scripts/test_plugins.py`（11 项）。
