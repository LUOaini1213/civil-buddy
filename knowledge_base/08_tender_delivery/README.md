---
category: tender_delivery
subcategory: overview
priority: high
type: protocol
tags: [tender, delivery, facade, mainline]
source: internal
updated: "2026-08-06"
harness: ">=0.6.4"
status: active
---
# 08 · 投标应答 + 交付链路

产品主线见：`docs/product-mainline-tender-delivery.md`。

| 子目录 | 内容 |
|--------|------|
| `rules/` | 响应红线、运输包装条款、废标关注（实务备忘，非法务） |
| `strategies/` | 幕墙投标应答策略 |
| `trajectories/` | T-D1 happy path 等 |

**分工**：本目录管「投什么、怎么应」；`01_rules`+装柜 tools 管「怎么装、能不能出运」。

矩阵行通过 `knowledge_ref` 绑到本目录（M4 轻量）；`tender.handoff.v1` 把评分点交给 bid-tech、★/废标交给 bid-compliance。P0 不自动关闭。电子标加密/CA 锁只摘原文，不编平台或锁号。
