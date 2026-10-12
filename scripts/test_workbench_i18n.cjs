#!/usr/bin/env node
/* 中文 | English, the page side on its own (no server): the workbench markup with /static/i18n/en.js and
   /static/i18n.js, in jsdom.
   - the first visit follows the browser language (zh* is Chinese, anything else English); a saved choice wins;
   - a browser whose storage throws (private window, blocked site data) still gets a working switch;
   - switching re-applies the markup both ways from the Chinese written in index.html, marks the pressed button,
     sets <html lang>, the cb_lang cookie and the X-Civil-Lang header on the page's /api/ calls, and tells listeners;
   - tr() fills {0} {1} and falls back to the Chinese message when a message has no English entry.
   The whole page against the real backend (post list, server notices) is scripts/e2e/ui_dom.cjs; the catalogue
   (every message has English, nothing stale) is scripts/test_workbench_i18n.py.
     node --test scripts/test_workbench_i18n.cjs    (registered in scripts/check_project.py as workbench-i18n-ui) */
"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const STATIC = path.join(__dirname, "..", "demo", "static");
const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const dictionary = fs.readFileSync(path.join(STATIC, "i18n", "en.js"), "utf8");
const runtime = fs.readFileSync(path.join(STATIC, "i18n.js"), "utf8");

/* index.html with only its own inline scripts and the two language files inlined (no app, no network). */
function page({ language = "en-US", saved = null, storageThrows = false } = {}) {
  const markup = html
    .replace(/<script src="\/static\/i18n\/en\.js[^"]*"><\/script>/, () => `<script>${dictionary}</script>`)
    .replace(/<script src="\/static\/i18n\.js[^"]*"><\/script>/, () => `<script>${runtime}</script>`)
    .replace(/<script\b[^>]*\bsrc="[^"]*"[^>]*><\/script>/g, "")
    .replace(/<script type="module"[^>]*><\/script>/g, "");
  const calls = [];
  const dom = new JSDOM(markup, {
    url: "http://127.0.0.1:8765/",
    runScripts: "dangerously",
    beforeParse(win) {
      Object.defineProperty(win.navigator, "language", { value: language, configurable: true });
      Object.defineProperty(win.navigator, "languages", { value: [language], configurable: true });
      if (storageThrows) {
        Object.defineProperty(win, "localStorage", { get() { throw new Error("SecurityError: storage is blocked"); } });
      } else if (saved) {
        win.localStorage.setItem("cb_lang_v1", saved);
      }
      win.Headers = globalThis.Headers;
      win.fetch = async (input, init) => { calls.push({ input, headers: new globalThis.Headers((init || {}).headers || {}) }); return { ok: true }; };
    },
  });
  return { window: dom.window, document: dom.window.document, calls };
}

const text = (doc, selector) => doc.querySelector(selector).textContent;

test("the first visit follows the browser language; a saved choice wins", () => {
  const zh = page({ language: "zh-CN" });
  assert.equal(zh.window.CB_I18N.lang(), "zh");
  assert.equal(zh.document.documentElement.getAttribute("lang"), "zh-CN");
  assert.equal(text(zh.document, ".brand small"), "内部讨论草稿 · 不是签认件");
  assert.equal(zh.document.querySelector('[data-cb-lang="zh"]').getAttribute("aria-pressed"), "true");

  for (const language of ["en-US", "en-GB", "fr-FR", "de", ""]) {
    const other = page({ language });
    assert.equal(other.window.CB_I18N.lang(), "en", language);
    assert.equal(text(other.document, ".brand small"), "Internal discussion draft · not a sign-off document");
    assert.equal(other.document.querySelector('[data-cb-lang="en"]').getAttribute("aria-pressed"), "true");
  }
  assert.equal(page({ language: "zh-TW" }).window.CB_I18N.lang(), "zh");
  assert.equal(page({ language: "en-US", saved: "zh" }).window.CB_I18N.lang(), "zh");
  assert.equal(page({ language: "zh-CN", saved: "en" }).window.CB_I18N.lang(), "en");
  assert.equal(page({ language: "zh-CN", saved: "klingon" }).window.CB_I18N.lang(), "zh");
});

test("switching re-applies text and attributes both ways and tells the server and the page", () => {
  const { window, document, calls } = page({ language: "zh-CN" });
  const heard = [];
  window.CB_I18N.onChange((lang) => heard.push(lang));
  window.addEventListener("cb:lang", (ev) => heard.push("event:" + ev.detail.lang));
  const input = document.getElementById("input");
  const zhPlaceholder = input.getAttribute("placeholder");

  document.querySelector('[data-cb-lang="en"]').click();
  assert.equal(window.CB_I18N.lang(), "en");
  assert.deepEqual(heard, ["en", "event:en"]);
  assert.equal(document.documentElement.getAttribute("lang"), "en");
  assert.match(document.cookie, /(^|; )cb_lang=en/);
  assert.equal(window.localStorage.getItem("cb_lang_v1"), "en");
  assert.equal(document.querySelector('[data-cb-lang="en"]').getAttribute("aria-pressed"), "true");
  assert.equal(document.querySelector('[data-cb-lang="zh"]').getAttribute("aria-pressed"), "false");
  assert.equal(text(document, ".cb-empty-title"), "Civil Codex: a 66-post workbench");
  assert.equal(document.getElementById("btnNewThread").getAttribute("title"), "Clear the current session and go back to the start card");
  assert.equal(input.getAttribute("placeholder"), "Describe the task, or /command · @post; Enter to send / Shift+Enter for a new line");
  assert.equal(document.querySelector(".cb-empty-hint code").textContent, "@"); // html-mode keeps its markup
  const signoff = text(document, "label.confirm span");
  assert.ok(signoff.includes("I understand; a licensed person will sign this off.") && signoff.includes("我明白，将由持证人员签认"), signoff);
  assert.ok(document.getElementById("confirmOk"), "the confirmation box itself is untouched");
  // Chinese left anywhere visible in the markup is a miss (the 中文 button and the Chinese sentence it quotes aside)
  const leftover = [...document.body.querySelectorAll("*")]
    .filter((el) => !el.children.length && !el.closest("script,style,[data-cb-lang]"))
    .map((el) => el.textContent.replace("我明白，将由持证人员签认", ""))
    .filter((t) => /[\u3400-\u9fff]/.test(t));
  assert.deepEqual(leftover, []);

  window.fetch("/api/health");
  window.fetch("https://example.invalid/x");
  assert.equal(calls[0].headers.get("X-Civil-Lang"), "en");
  assert.equal(calls[1].headers.get("X-Civil-Lang"), null, "other origins are left alone");

  document.querySelector('[data-cb-lang="zh"]').click();
  assert.equal(text(document, ".cb-empty-title"), "土木版 Codex：66 岗工作台");
  assert.equal(input.getAttribute("placeholder"), zhPlaceholder);
  assert.equal(document.documentElement.getAttribute("lang"), "zh-CN");
  assert.match(document.cookie, /(^|; )cb_lang=zh/);
  window.fetch("/api/health");
  assert.equal(calls[2].headers.get("X-Civil-Lang"), "zh");
  document.querySelector('[data-cb-lang="zh"]').click(); // same language: no second notice
  assert.deepEqual(heard, ["en", "event:en", "zh", "event:zh"]);
});

test("storage that throws does not break the page or the switch", () => {
  const { window, document } = page({ language: "zh-CN", storageThrows: true });
  assert.equal(window.CB_I18N.lang(), "zh");
  document.querySelector('[data-cb-lang="en"]').click();
  assert.equal(window.CB_I18N.lang(), "en");
  assert.equal(text(document, ".brand small"), "Internal discussion draft · not a sign-off document");
});

test("tr fills fields and falls back to the Chinese message", () => {
  const { window } = page({ language: "en-US" });
  const t = window.CB_I18N.t;
  assert.equal(t("同一会话最多 {0} 个附件", 12), "At most 12 attachments per session");
  assert.equal(t("上下文 {0} / {1} · {2}%", "1,000", "32,768", 3), "Context 1,000 / 32,768 · 3%");
  assert.equal(t("没有这条消息 {0}", "x"), "没有这条消息 x");
  window.CB_I18N.set("zh");
  assert.equal(t("同一会话最多 {0} 个附件", 12), "同一会话最多 12 个附件");
  assert.equal(window.CB_I18N.set("fr"), "zh", "an unknown language is ignored");
});

test("modules without the runtime keep the Chinese as written", () => {
  const { tr, cbLang } = require("../demo/static/modules/i18n.js");
  assert.equal(cbLang(), "zh");
  assert.equal(tr("同一会话最多 {0} 个附件", 12), "同一会话最多 12 个附件");
  assert.equal(tr("{0}：同一会话最多 {1} 个附件", "a.pdf"), "a.pdf：同一会话最多 {1} 个附件");
});
