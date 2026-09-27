/* 中文 | English switch for the workbench page (index.html and every script it loads).

   Messages are written in Chinese in the source and looked up as they are: tr("停止") is "Stop" in English and
   "停止" in Chinese. {0} {1} … are filled from the extra arguments. The English table is window.CB_I18N_EN
   (i18n/en.js); scripts/test_workbench_i18n.py keeps it and the source in step (every message has an English
   entry, no entry is stale, no Chinese literal outside tr() except the allow-listed data).

   The choice: localStorage cb_lang_v1 (read and written in try/catch; a private window just falls back), else the
   browser language (zh* is Chinese, anything else English). It is also sent to the server — a cookie cb_lang,
   so downloads, uploads and resumed streams carry it, and an X-Civil-Lang header on the page's fetch calls —
   so notices, errors and the sign-off prompt the server writes come back in the same language.

   Static markup opts in with data-i18n (its text is the message) and data-i18n-attr="title aria-label …" (those
   attributes are messages). Switching re-applies both and fires a "cb:lang" event for the page to repaint what
   it drew itself. What the switch never touches: the sentences that approve a high-risk turn, what the server
   checks, and the content of drafts (post templates are Chinese; the page says so instead of translating them). */
(function (global) {
  "use strict";

  var KEY = "cb_lang_v1";
  var COOKIE = "cb_lang";
  var LANGS = ["zh", "en"];
  var originals = typeof WeakMap === "function" ? new WeakMap() : null;

  function read() { try { return global.localStorage ? global.localStorage.getItem(KEY) : null; } catch (e) { return null; } }
  function write(value) { try { if (global.localStorage) global.localStorage.setItem(KEY, value); } catch (e) { /* 存储不可用：本次有效 */ } }

  function browserLang() {
    var nav = global.navigator || {};
    var first = (nav.languages && nav.languages[0]) || nav.language || "";
    return /^zh\b/i.test(String(first)) ? "zh" : "en";
  }

  function normalize(value) { return LANGS.indexOf(value) >= 0 ? value : null; }

  var current = normalize(read()) || browserLang();

  function format(message, args) {
    return String(message).replace(/\{(\d+)\}/g, function (whole, index) {
      var i = Number(index);
      return i < args.length && args[i] !== undefined && args[i] !== null ? String(args[i]) : (i < args.length ? "" : whole);
    });
  }

  function t(message) {
    var args = Array.prototype.slice.call(arguments, 1);
    var table = current === "en" ? global.CB_I18N_EN : null;
    var text = table && Object.prototype.hasOwnProperty.call(table, message) ? table[message] : message;
    return format(text, args);
  }

  function sendToServer() {
    var doc = global.document;
    if (doc) {
      try { doc.cookie = COOKIE + "=" + current + "; path=/; max-age=31536000; SameSite=Lax"; } catch (e) { /* 无 cookie：请求头仍带 */ }
      if (doc.documentElement) doc.documentElement.setAttribute("lang", current === "en" ? "en" : "zh-CN");
    }
  }

  function remember(el, name, value) {
    if (!originals) return value;
    var saved = originals.get(el);
    if (!saved) { saved = {}; originals.set(el, saved); }
    if (!Object.prototype.hasOwnProperty.call(saved, name)) saved[name] = value;
    return saved[name];
  }

  /* Static markup: the Chinese written in index.html is the message; it is kept the first time it is seen, so
     switching back and forth always starts from it. */
  function apply(root) {
    var scope = root || global.document;
    if (!scope || typeof scope.querySelectorAll !== "function") return;
    var nodes = scope.querySelectorAll("[data-i18n]");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var mode = el.getAttribute("data-i18n");
      if (mode === "html") {
        var html = remember(el, "#html", el.innerHTML.trim());
        el.innerHTML = current === "en" ? t(html) : html;   /* trusted: the table is the page's own static file */
      } else {
        var text = remember(el, "#text", el.textContent.replace(/\s+/g, " ").trim());
        el.textContent = t(text);
      }
    }
    var withAttrs = scope.querySelectorAll("[data-i18n-attr]");
    for (var j = 0; j < withAttrs.length; j++) {
      var node = withAttrs[j];
      var names = (node.getAttribute("data-i18n-attr") || "").split(/\s+/);
      for (var k = 0; k < names.length; k++) {
        var name = names[k];
        if (!name || !node.hasAttribute(name)) continue;
        node.setAttribute(name, t(remember(node, name, node.getAttribute(name))));
      }
    }
    var buttons = scope.querySelectorAll("[data-cb-lang]");
    for (var b = 0; b < buttons.length; b++) {
      buttons[b].setAttribute("aria-pressed", buttons[b].getAttribute("data-cb-lang") === current ? "true" : "false");
    }
  }

  var listeners = [];

  function set(lang) {
    var next = normalize(lang);
    if (!next) return current;
    var changed = next !== current;
    current = next;
    write(next);
    sendToServer();
    apply(global.document);
    if (changed) {
      for (var i = 0; i < listeners.length; i++) {
        try { listeners[i](current); } catch (e) { if (global.console) global.console.error(e); }
      }
      try {
        if (typeof global.dispatchEvent === "function" && typeof global.CustomEvent === "function") {
          global.dispatchEvent(new global.CustomEvent("cb:lang", { detail: { lang: current } }));
        }
      } catch (e) { /* 旧浏览器：listeners 已通知 */ }
    }
    return current;
  }

  function onChange(fn) { if (typeof fn === "function") listeners.push(fn); }

  /* The header's 中文 | English buttons (any element with data-cb-lang). */
  function bindButtons(root) {
    var scope = root || global.document;
    if (!scope || typeof scope.querySelectorAll !== "function") return;
    var buttons = scope.querySelectorAll("[data-cb-lang]");
    for (var i = 0; i < buttons.length; i++) {
      if (buttons[i].__cbLangBound) continue;
      buttons[i].__cbLangBound = true;
      buttons[i].addEventListener("click", function (ev) { set(ev.currentTarget.getAttribute("data-cb-lang")); });
    }
  }

  /* Headers for the page's own API calls: the server picks the language from X-Civil-Lang first, then the cookie. */
  function headers(extra) {
    var out = {};
    if (extra) for (var k in extra) if (Object.prototype.hasOwnProperty.call(extra, k)) out[k] = extra[k];
    out["X-Civil-Lang"] = current;
    return out;
  }

  /* The page's own /api/ calls carry the header; anything else (other origins, Request objects) is left alone. */
  function installFetchHeader() {
    if (typeof global.fetch !== "function" || global.fetch.cbLang || typeof global.Headers !== "function") return false;
    var raw = global.fetch;
    var wrapped = function (input, init) {
      if (typeof input === "string" && input.indexOf("/api/") === 0) {
        var options = {};
        if (init) for (var k in init) if (Object.prototype.hasOwnProperty.call(init, k)) options[k] = init[k];
        var h = new global.Headers(options.headers || {});
        if (!h.has("X-Civil-Lang")) h.set("X-Civil-Lang", current);
        options.headers = h;
        return raw.call(this, input, options);
      }
      return raw.apply(this, arguments);
    };
    wrapped.cbLang = true;
    global.fetch = wrapped;
    return true;
  }

  sendToServer();
  installFetchHeader();

  global.CB_I18N = {
    t: t,
    format: format,
    lang: function () { return current; },
    set: set,
    apply: apply,
    bindButtons: bindButtons,
    onChange: onChange,
    headers: headers,
    browserLang: browserLang,
    KEY: KEY,
    COOKIE: COOKIE,
  };
})(typeof window !== "undefined" ? window : globalThis);
