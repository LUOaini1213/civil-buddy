#!/usr/bin/env python3
"""ux(round2) 输入体验烟测：composer 关键函数/监听/占位符在三个界面资产中在场，
66 岗 @补全数据与 workbench/seed.json 完全一致，CI frontend 标记不丢。"""
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parents[1]
app = (R / "demo/static/app.js").read_text(encoding="utf-8")
demo_html = (R / "demo/static/index.html").read_text(encoding="utf-8")
css = (R / "demo/static/styles.css").read_text(encoding="utf-8")
wb = (R / "frontend/workbench.html").read_text(encoding="utf-8")
host = (R / "frontend/index.html").read_text(encoding="utf-8")
posts = (R / "demo/static/posts.js").read_text(encoding="utf-8")
seed = json.loads((R / "workbench/seed.json").read_text(encoding="utf-8"))

# 1) composer 核心函数三端在场（:8765 vanilla + workbench Vue + 宿主页 Vue）
for fn in ["cbAtQuery", "cbAtFilter", "cbAtApply", "cbComposeGuard", "compositionstart"]:
    assert fn in app and fn in wb and fn in host, ("composer fn", fn)
assert "cbAutosize" in app and "cbAutosize" in wb, "cbAutosize"
assert "cbComposerInit()" in app and 'addEventListener("input"' in app, "app.js wiring"

# 2) @补全浮层与 Enter 语义绑定在场
assert 'id="atMenu"' in demo_html and "cb-at-menu" in css and "cb-at-menu" in wb and "cb-at-menu" in host
assert "composerKeydown" in wb and "composerInput" in wb and "tenderKeydown" in host and "tenderInput" in host
assert "posts.js" in demo_html and "window.CB_POSTS" in wb, "posts 数据加载/内嵌"

# 3) 规范中文话术 placeholder + 运行中态 + 空态禁用
for html in (demo_html, wb, host):
    assert "Enter 发送" in html, ("placeholder", html[:30])
assert "运行中…" in app and "运行中…" in wb and "处理中…" in host
assert ":disabled=\"loading || !userInput.trim()\"" in wb

# 4) 66 岗数据：posts.js 与 seed.json 完全一致；workbench 内嵌块一致
m = re.search(r"window\.CB_POSTS = (\[.*\]);", posts, re.S)
gen = json.loads(m.group(1))
seed_rows = [{"id": e["id"], "name": e["name"], "aliases": e.get("aliases", []),
              "category": e.get("category", ""), "category_name": e.get("category_name", "")}
             for e in seed["experts"]]
assert len(gen) == 66 == len(seed_rows), (len(gen), len(seed_rows))
assert gen == seed_rows, "posts.js 与 seed.json 漂移"
blk = re.search(r"/\* === CB_POSTS BEGIN.*?/\* === CB_POSTS END === \*/", wb, re.S).group(0)
m2 = re.search(r"window\.CB_POSTS = (\[.*\]);", blk, re.S)
assert json.loads(m2.group(1)) == gen, "workbench 内嵌 CB_POSTS 与 posts.js 漂移"

# 5) 生成产物零外链（硬红线）
assert "http://" not in posts and "https://" not in posts and "<script" not in posts

# 6) CI frontend 标记不丢（ci.yml 两段断言）
for k in ["大 Team", "org-chart", "/api/pipeline", "consumeSse", "hitl_summary", "draw3d",
          "TEAM_ROSTER", "/api/whatif", "What-if", "订柜 N0", "3D 用柜", "perCabinCog",
          "secureWorkOrder", "big_team_a_b", "/api/whatif/apply", "/api/profiles",
          "POR 装柜单", "应用为当前方案"]:
    assert k in wb, ("ci marker", k)
for k in ["Civil Buddy", "/workbench"]:
    assert k in host, ("ci marker", k)

print(f"ux(round2) composer smoke OK: 66 posts, 3 surfaces, {len(gen)} aliases-total="
      f"{sum(len(p['aliases']) for p in gen)}")
