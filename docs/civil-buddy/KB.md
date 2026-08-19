# 知识库

两套库，不要合并。

| 库 | 路径 | 谁读 | 谁写 |
|----|------|------|------|
| 岗库 | `demo/kb/<大类>/<岗id>/` | 被召唤岗：私库 + 大类 `_shared` + `company/` | 人改 Markdown；agent 不写规范全文。沙箱可写 `demo/kb` 但产品默认不自动写门户页 |
| 引擎库 | `knowledge_base/` | 装箱 harness / solver 检索 | 人维护规则与轨迹；**不是**岗起草私库 |

`pack-ship` 岗 KB 只放 CTU 等**官方标题** + 指向引擎。xyz / can_fit 不进岗库。

## 岗分层（MCP `kb://`）

```
expert     demo/kb/<cat>/<id>/*
category   demo/kb/<cat>/_shared/*
company    demo/kb/company/*
```

兄弟私库不可见。`kb://bid/bid-tech/outline.md` 在 bid-parse 会话 → 拒绝句，不是空 404。

目录契约（K1）：每岗 `README.md` `faq.md` `outline.md` `web-knowledge.md`。

## 门户单一来源（K2）

GST 9%、Fire Code 2023、CTU Code 2014、GeBIZ≠评分、APPBCA-2026-12 权威句在 `demo/kb/company/web-portals.md`。各岗可链或抄同一句，禁止各写一个税率。

抓 IRAS 失败不得删 KB 里的 9%，不得写「官方没写 9%」。

## 不可写进库

规范正文、密钥、中标率、可以开工当结论、编造条款号。缺数：`[A001]` / `UNSPECIFIED`。
