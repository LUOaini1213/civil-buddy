# 交付物管道

权威 CLI 与 token 表。脚本路径相对 skill 根；bundled docx 工具在 `%GROK_HOME%` 或 `~\.grok\bundled\skills\docx\scripts\`。

## scheme（V1）

复制 `references/templates/scheme-cn-a4.docx`，只做字符串替换。禁止 docx-js、禁止 markdown-to-docx、禁止改表 XML、禁止单 `{{BODY}}`。

```text
python <skill>/scripts/fill_scheme_template.py
  --template <skill>/references/templates/scheme-cn-a4.docx
  --draft      <out_dir>/draft.md
  --assumptions <out_dir>/assumptions.md
  --citations  <out_dir>/citations.md
  --jurisdiction CN
  --stamp      2026-08-13T15-04-05
  --project-name "示例工程"
  --short-name "示例"
  --out        <out_dir>/专项施工方案-AI草稿.docx
```

脚本写 `<out_dir>/replacements.json`（键含花括号），再调用：

```text
python <grok>/bundled/skills/docx/scripts/office/unpack.py
python <grok>/bundled/skills/docx/scripts/replace_text.py  --map … --all-files
python <grok>/bundled/skills/docx/scripts/office/pack.py
python <grok>/bundled/skills/docx/scripts/office/validate.py
```

`replace_text.py` 与 `unpack.py` 不在同一目录。`--all-files` 必开。Windows 上 `replace_text.py` 的 CLI 会因 `SIGPIPE` 退出；`fill_scheme_template.py` 改为同进程 import 其替换函数，不改 bundled 脚本。

## token

| token | 来源 |
|-------|------|
| `{{PROJECT_NAME}}` | `--project-name` |
| `{{SHORT_NAME}}` | `--short-name` |
| `{{STAMP}}` | `--stamp` |
| `{{JURISDICTION}}` | `--jurisdiction` |
| `{{ASSUMPTIONS}}` | `assumptions.md` 纯文本 |
| `{{SEC_OVERVIEW}}` | draft `## 3` |
| `{{CITED_VERIFIED}}` | citations 已核实；无行则「（无）」 |
| `{{CITED_UNVERIFIED}}` | citations 未核实；至少保留表头行 |
| `{{SEC_DEPLOY}}` | draft `## 5` |
| `{{SEC_QUALITY}}` | draft `## 6` |
| `{{SEC_SAFETY}}` | draft `## 7` |
| `{{SEC_ENV}}` | draft `## 8` |
| `{{SEC_RESOURCES}}` | draft `## 9` |
| `{{SEC_ACCEPTANCE}}` | draft `## 10` |
| `{{SEC_APPENDIX}}` | draft `## 11` |

模板写死、不进 map：页眉库存句、第 2 章固定声明、签认空栏。见 `hard-rules.md`。

## 写后必跑

```text
python <grok>/bundled/skills/docx/scripts/office/validate.py <docx>
python <skill>/scripts/scan_forbidden_inventions.py --draft <draft.md> --docx <docx> --citations <citations.md> --jurisdiction CN
python <skill>/scripts/assert_outdir_only.py --root <root> --out-dir <out_dir>
```

## 其它格式

- slides / pdf 水印 / xlsx：尚未实施。
- PDF 两条路径不同：`docx/scripts/convert_doc.py --to pdf` 与 `docx/scripts/office/soffice.py`。
- `checklist` / `cost` 目前只出 md。

## manifest.json

```json
{
  "schema": "civil-buddy-manifest/v1",
  "stamp": "2026-08-13T15-04-05",
  "jurisdiction": "CN",
  "deliverable": "scheme",
  "experts": ["construction"],
  "risk": "high",
  "confirm_gate": "accepted",
  "docx_pending": false,
  "rejected": false,
  "assert_ok": true,
  "scan_ok": true,
  "validate_ok": true,
  "files": {
    "draft_md": "draft.md",
    "assumptions": "assumptions.md",
    "citations": "citations.md",
    "replacements": "replacements.json",
    "docx": "专项施工方案-AI草稿.docx"
  }
}
```

无 docx 则省略 `files.docx` 且 `docx_pending: true`。
