# 项目上下文包

跨会话真相在 `<job>/.civil-buddy/project.md`，不是 `AGENTS.md`，也不用 Grok Memory。

同目录可选 `codes.md`：三列 `全名 | 年份 | 相对PDF或UNAVAILABLE`。

## `project.md` YAML

```markdown
---
schema: civil-buddy-project/v1
name: "示例市政道路维修（虚构）"
short_name: "示例路"
jurisdiction: CN
language: zh-CN
code_family_primary: "GB / GB/T / CJJ / JGJ"
code_family_secondary: []
units: SI
client: ""
contractor: ""
designer: ""
site_location: "虚构市虚构区"
unit_works:
  - id: edge-protect
    name: "临边与洞口防护（讨论提纲）"
    discipline: construction
status: draft
confidential: true
---

# 工程概况

只写事实。数字必须带来源文件名。无来源则不要写毫米级尺寸。

## 已知约束

- 本包为虚构验收场地，不是真实工程。
- 无地勘、无正式图纸、无综合单价。

## 规范体系

见同目录 codes.md。列为 UNAVAILABLE 的规范不得写入「编制依据（已核实）」。

## 单位工程

- edge-protect: 临边与洞口防护讨论提纲

## 明确不要做的事

- 不要当法定专项方案
- 不要编条款号与栏杆荷载
```

检入样例：`examples/sample-cn-project.md`。验收时拷到 `%TEMP%\civil-buddy-v1-验收\`，禁止写 `D:\layout`。
