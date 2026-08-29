/* Civil Buddy 交付物文书预览组件 · ux(round4)
 * canonical 源文件：demo/static/docpreview.js（:8000 侧同构复制于 frontend/vendor/cb-doc.js）。
 * 依赖：marked（demo/static/vendor/marked.min.js，MIT，vendored 同源）。
 * 红线：零 CDN、零外链字体（正文系统仿宋/宋体栈、标题黑体栈）；预览内容 = 交付物 markdown 本体。
 * 诚实元素（ux round1 spec §3.2）：UNSPECIFIED/[A001]/待填 → 安全橙徽章，不译、不藏、不伪填；
 * 「数字只抄工具」小节 → 浅蓝 tool-computed 标识；免责横幅常驻（合规红）。
 * 对外 API：cbDocOpen({title, role, project, text|url, time, version}) / cbDocClose()。
 */
(function (global) {
  "use strict";

  var DOC_VER = "ux(round4) 文书预览 v1";
  var UNSPEC_TITLE = "UNSPECIFIED · 数据哨兵，待人工补全（导出保留原文）";
  var ANCHOR_TITLE = "锚点 · 待人工补全编号（导出保留原文）";
  var PENDING_TITLE = "待填 · 须人工补全";
  var TOOL_SECTION_RE = /(工具计算|回传|只抄|非本岗编造)/;
  var DISCLAIM_RE = /(不构成|仅供内部讨论|不是签认)/;
  /* 诚实元素令牌：UNSPECIFIED 原文 / [A001] 锚点 / 中文待填词（词边界防误伤） */
  var TOKEN_RE = /(UNSPECIFIED)|\[(A\d{3})\]|(待填|待补|待定|待提供|未提供)/g;
  var TOKEN_TEST_RE = /UNSPECIFIED|\[(A\d{3})\]|待填|待补|待定|待提供|未提供/;

  function esc(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function fmtNow() {
    var d = new Date();
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
      " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  /* ---- 覆盖层（追加到 body，打印时可独占文档流） ---- */
  var overlay = null;

  function ensureOverlay() {
    if (overlay && document.body.contains(overlay)) return overlay;
    overlay = document.createElement("div");
    overlay.className = "cb-doc-overlay";
    overlay.hidden = true;
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "交付物文书预览");
    overlay.innerHTML =
      '<div class="cb-doc-backdrop" data-cb-doc-act="close"></div>' +
      '<div class="cb-doc-modal">' +
        '<div class="cb-doc-toolbar">' +
          '<span class="cb-doc-title"></span>' +
          '<span class="cb-doc-meta"></span>' +
          '<span class="cb-doc-actions">' +
            '<button type="button" class="cb-doc-btn" data-cb-doc-act="copy">复制 Markdown</button>' +
            '<button type="button" class="cb-doc-btn" data-cb-doc-act="download">下载 .md</button>' +
            '<button type="button" class="cb-doc-btn" data-cb-doc-act="print">打印 / 存 PDF</button>' +
            '<button type="button" class="cb-doc-btn cb-doc-close" data-cb-doc-act="close" aria-label="关闭预览">关闭</button>' +
          "</span>" +
        "</div>" +
        '<div class="cb-doc-scroll">' +
          '<article class="cb-doc-page">' +
            '<header class="cb-doc-head">' +
              '<span class="cb-doc-proj"></span>' +
              '<span class="cb-doc-role"></span>' +
            "</header>" +
            '<div class="cb-doc-body cb-doc-md"></div>' +
            '<footer class="cb-doc-foot">' +
              '<span class="cb-doc-time"></span>' +
              '<span class="cb-doc-ver">' + esc(DOC_VER) + "</span>" +
              '<span class="cb-doc-disclaim">内部讨论 AI 草稿 · 不签认</span>' +
            "</footer>" +
          "</article>" +
        "</div>" +
      "</div>";
    document.body.appendChild(overlay);
    overlay.addEventListener("click", function (ev) {
      var act = ev.target.closest && ev.target.closest("[data-cb-doc-act]");
      if (!act) return;
      var a = act.getAttribute("data-cb-doc-act");
      if (a === "close") cbDocClose();
      else if (a === "print") global.print();
      else if (a === "copy") copyMd();
      else if (a === "download") downloadMd();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && overlay && !overlay.hidden) cbDocClose();
    });
    return overlay;
  }

  var current = { text: "", filename: "文书.md" };

  function copyMd() {
    var t = current.text || "";
    var done = function () {
      var btn = overlay.querySelector('[data-cb-doc-act="copy"]');
      if (!btn) return;
      var old = btn.textContent;
      btn.textContent = "已复制";
      setTimeout(function () { btn.textContent = old; }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(done, function () { fallbackCopy(t); done(); });
    } else {
      fallbackCopy(t); done();
    }
  }

  function fallbackCopy(t) {
    var ta = document.createElement("textarea");
    ta.value = t;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* 忽略 */ }
    ta.remove();
  }

  function downloadMd() {
    if (typeof global.cbObStep === "function") global.cbObStep(3); /* ux(round10)：下载 .md → 引导第 3 步打勾 */
    var blob = new Blob([current.text || ""], { type: "text/markdown;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = current.filename || "文书.md";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 400);
  }

  /* ---- markdown → 结构化 DOM ---- */

  function sanitize(root) {
    var bad = root.querySelectorAll("script,iframe,object,embed,link,style");
    for (var i = 0; i < bad.length; i++) bad[i].remove();
    var all = root.querySelectorAll("*");
    for (var j = 0; j < all.length; j++) {
      var el = all[j];
      for (var k = el.attributes.length - 1; k >= 0; k--) {
        var n = el.attributes[k].name.toLowerCase();
        var v = String(el.attributes[k].value);
        if (n.indexOf("on") === 0 || (n === "href" && /^\s*javascript:/i.test(v)) ||
            (n === "src" && /^\s*javascript:/i.test(v))) {
          el.removeAttribute(el.attributes[k].name);
        }
      }
    }
    return root;
  }

  function renderMarkdown(md) {
    var wrap = document.createElement("div");
    var html;
    try {
      html = (global.marked && typeof global.marked.parse === "function")
        ? global.marked.parse(md, { breaks: false, gfm: true })
        : "<pre>" + esc(md) + "</pre>";
    } catch (e) {
      html = "<pre>" + esc(md) + "</pre>";
    }
    wrap.innerHTML = html;
    return sanitize(wrap);
  }

  /* ---- 诚实元素样式化 ---- */

  function makeBadge(kind, label, title) {
    var b = document.createElement("span");
    b.className = "cb-badge cb-badge-" + kind;
    b.setAttribute("title", title);
    b.textContent = label;
    return b;
  }

  function decorateText(node) {
    var data = node.data;
    TOKEN_RE.lastIndex = 0;
    if (!TOKEN_RE.test(data)) return;
    TOKEN_RE.lastIndex = 0;
    var frag = document.createDocumentFragment();
    var last = 0, m;
    while ((m = TOKEN_RE.exec(data))) {
      if (m.index > last) frag.appendChild(document.createTextNode(data.slice(last, m.index)));
      if (m[1]) frag.appendChild(makeBadge("unspec", "未提供", UNSPEC_TITLE));
      else if (m[2]) frag.appendChild(makeBadge("anchor", m[2], ANCHOR_TITLE));
      else frag.appendChild(makeBadge("unspec", m[3], PENDING_TITLE));
      last = m.index + m[0].length;
    }
    if (last < data.length) frag.appendChild(document.createTextNode(data.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }

  /* 遍历文本节点打徽章；pre/code 内同样可见（等宽底色），徽章内不再嵌套 */
  function decorateBadges(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.data || !n.data.trim()) return NodeFilter.FILTER_REJECT;
        var p = n.parentElement;
        if (!p || p.closest(".cb-badge")) return NodeFilter.FILTER_REJECT;
        return TOKEN_TEST_RE.test(n.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    var hits = [];
    while (walker.nextNode()) hits.push(walker.currentNode);
    for (var i = 0; i < hits.length; i++) decorateText(hits[i]);
  }

  /* 「数字只抄工具」小节 → 浅蓝底 tool-computed 标识 */
  function decorateToolSections(root) {
    var heads = root.querySelectorAll("h1, h2, h3, h4");
    for (var i = 0; i < heads.length; i++) {
      var h = heads[i];
      if (!TOOL_SECTION_RE.test(h.textContent || "")) continue;
      h.classList.add("cb-tool-h");
      var sib = h.nextElementSibling;
      while (sib) {
        var next = sib.nextElementSibling;
        var tag = (sib.tagName || "").toLowerCase();
        if (/^h[1-4]$/.test(tag)) break;
        sib.classList.add("cb-tool-comp");
        sib = next;
      }
    }
  }

  /* 正文里的免责段（文书自带的「不构成…」）→ 合规红横幅 */
  function decorateDisclaimer(root) {
    var ps = root.querySelectorAll("p");
    for (var i = 0; i < ps.length; i++) {
      if (DISCLAIM_RE.test(ps[i].textContent || "")) {
        ps[i].classList.add("cb-doc-disclaim-p");
        return;
      }
    }
  }

  function cbDocDecorate(rootEl) {
    if (!rootEl) return;
    decorateBadges(rootEl);
    decorateToolSections(rootEl);
    decorateDisclaimer(rootEl);
  }

  /* ---- 打开 / 关闭 ---- */

  function guessMeta(md) {
    var t = { title: "", project: "" };
    var h1 = md.match(/^\s*#\s+(.+)$/m);
    if (h1) t.title = h1[1].trim();
    var proj = md.match(/^\s*##\s+工程[\/／]批次\s*\n+\s*([^\n]+)/m);
    if (proj) t.project = proj[1].trim();
    return t;
  }

  function cbDocOpen(opts) {
    opts = opts || {};
    var ov = ensureOverlay();
    var md = opts.text || "";
    current.text = md;
    var guess = guessMeta(md);
    var title = opts.title || guess.title || "交付物文书";
    current.filename = String(title).replace(/[\\/:*?"<>|]/g, "_") + ".md";

    var body = ov.querySelector(".cb-doc-body");
    body.innerHTML = "";
    var dom = renderMarkdown(md);
    cbDocDecorate(dom);
    while (dom.firstChild) body.appendChild(dom.firstChild);

    ov.querySelector(".cb-doc-title").textContent = title;
    ov.querySelector(".cb-doc-proj").textContent = opts.project || guess.project || "Civil Buddy 交付物";
    ov.querySelector(".cb-doc-role").textContent = opts.role || "岗位 · 未指定";
    ov.querySelector(".cb-doc-time").textContent = "生成 " + (opts.time || fmtNow());
    var meta = [];
    if (md) meta.push(md.length + " 字符");
    ov.querySelector(".cb-doc-meta").textContent = meta.join(" · ");

    ov.hidden = false;
    document.body.classList.add("cb-doc-open");
    var sc = ov.querySelector(".cb-doc-scroll");
    if (sc) sc.scrollTop = 0;
    return ov;
  }

  async function cbDocOpenUrl(opts) {
    opts = opts || {};
    var res = await fetch(opts.url, { headers: { Accept: "text/markdown,text/plain,*/*" } });
    if (!res.ok) throw new Error("文书读取失败 HTTP " + res.status);
    var text = await res.text();
    return cbDocOpen(Object.assign({}, opts, { text: text }));
  }

  function cbDocClose() {
    if (overlay) {
      overlay.hidden = true;
      overlay.querySelector(".cb-doc-body").innerHTML = "";
    }
    document.body.classList.remove("cb-doc-open");
  }

  global.cbDocOpen = cbDocOpen;
  global.cbDocOpenUrl = cbDocOpenUrl;
  global.cbDocClose = cbDocClose;
  global.cbDocDecorate = cbDocDecorate;
  global.cbDocRenderMarkdown = renderMarkdown;
})(typeof window !== "undefined" ? window : globalThis);
