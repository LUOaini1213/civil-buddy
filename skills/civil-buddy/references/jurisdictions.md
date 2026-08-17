# 辖区

`jurisdiction` 只能是 `CN` | `SG` | `EU` | `DUAL`。切换必须写进路由块和 `manifest.json`。禁止静默混用两套规范当同一依据。

| 值 | 主规范族（只写族名，不写条款） | 语言（V1） |
|----|--------------------------------|------------|
| CN | GB / GB/T / JGJ / JTG / JTS / CJJ | 中文 |
| SG | SS EN / BCA / LTA | 中文正文（双语是 V2） |
| EU | EN / Eurocode（EC2 / EC3 等） | 中文正文 |
| DUAL | 必须同时列出 `code_family_primary` 与 `code_family_secondary`，并在正文标明哪条属于哪一族 | 中文 |

`confidential: true` 时禁止 `web_search`。搜索结果不得当编制依据。
