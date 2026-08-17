# 专项施工方案讨论提纲（AI 草稿）

不可写「报审稿」。11 章不可删。`{{ASSUMPTIONS}}` 在第 2 章之后、第 3 章之前。

`draft.md` 用二级标题 `## 3 工程概况` 这种「编号+空格+章名」方便 `fill_scheme_template.py` 抽取。第 2 章与第 4 章由模板/citations 提供，draft 仍保留对应标题以免漏章。

1. 封面与文件控制 — `{{PROJECT_NAME}}` `{{STAMP}}` `{{JURISDICTION}}` `{{SHORT_NAME}}`
2. 草稿与责任声明 — 模板写死 `hard-rules.md` 固定声明，脚本不替换
3. 工程概况 — `{{SEC_OVERVIEW}}`（只引 project pack）
4. 编制依据 — `{{CITED_VERIFIED}}` / `{{CITED_UNVERIFIED}}`（纯文本，不是表 XML）
5. 施工部署与工艺 — `{{SEC_DEPLOY}}`（V1 中文）
6. 质量 — `{{SEC_QUALITY}}`
7. 安全与应急 — `{{SEC_SAFETY}}`（结论标草稿；无来源数字写待填）
8. 环保与文明施工 — `{{SEC_ENV}}`
9. 资源计划 — `{{SEC_RESOURCES}}`（无清单则只列待填表头）
10. 验收与资料 — `{{SEC_ACCEPTANCE}}`（不给合格结论）
11. 附录 — `{{SEC_APPENDIX}}`（计算摘录、图号清单）
