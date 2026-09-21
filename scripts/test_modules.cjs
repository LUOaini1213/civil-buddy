#!/usr/bin/env node
/* The page's modules, tested on their own: no DOM, no server, no source slicing.
 *   node --test scripts/test_modules.cjs   (registered in scripts/check_project.py as ui-modules) */
"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");

const { createAuth, TOKEN_COOKIE } = require("../demo/static/modules/auth.js");
const { createToast } = require("../demo/static/modules/toast.js");
const { createDrafts, DRAFT_PREFIX } = require("../demo/static/modules/drafts.js");
const { createUploads, precheck, accept, UPLOAD_LIMITS } = require("../demo/static/modules/uploads.js");

function element(tag) {
  const el = { tagName: tag, children: [], listeners: {}, hidden: false, textContent: "", style: {},
    appendChild(c) { this.children.push(c); c.parentElement = this; return c; },
    setAttribute(k, v) { this[k] = v; }, addEventListener(n, f) { this.listeners[n] = f; } };
  Object.defineProperty(el, "innerHTML", { set(v) { if (v === "") el.children = []; }, get() { return ""; } });
  el.querySelector = () => null;
  return el;
}
function fakeDoc() {
  const byId = new Map();
  const body = element("body");
  return { body, cookie: "",
    getElementById: (id) => byId.get(id) || null,
    createElement: (tag) => { const el = element(tag); Object.defineProperty(el, "id", { set(v) { byId.set(v, el); }, get() { return el._id; } }); return el; },
    querySelector: () => null };
}
const storage = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), map: m }; };

test("auth: cookie round trip, one prompt at a time, empty answers do nothing", async () => {
  const doc = { cookie: "" };
  const answers = ["", "s3cret"];
  const auth = createAuth({ doc, win: {}, prompt: () => answers.shift() });
  assert.equal(auth.hasToken(), false);
  assert.equal(await auth.askToken("需要口令"), false);
  assert.equal(doc.cookie, "");
  assert.equal(await auth.askToken("需要口令"), true);
  assert.match(doc.cookie, new RegExp(`^${TOKEN_COOKIE}=s3cret; path=/; max-age=\\d+; SameSite=Lax$`));
  assert.equal(auth.hasToken(), true);
  auth.setToken("空格 和/斜杠");
  assert.ok(doc.cookie.startsWith(`${TOKEN_COOKIE}=${encodeURIComponent("空格 和/斜杠")};`));
});

test("auth: the fetch guard retries an /api/ 401 exactly once after a successful prompt", async () => {
  const calls = [];
  const win = { fetch: async (url, init) => { calls.push([url, init && init.cbRetried]); return { status: calls.length === 1 ? 401 : 200 }; } };
  const auth = createAuth({ doc: { cookie: "" }, win, prompt: () => "tok" });
  assert.equal(auth.installFetchGuard(), true);
  assert.equal(auth.installFetchGuard(), false, "installed once");
  const res = await win.fetch("/api/catalog", { method: "GET" });
  assert.equal(res.status, 200);
  assert.deepEqual(calls, [["/api/catalog", undefined], ["/api/catalog", true]]);
  // a refused prompt leaves the 401 as it is, without a second request
  let count = 0;
  const win2 = { fetch: async () => { count += 1; return { status: 401 }; } };
  createAuth({ doc: { cookie: "" }, win: win2, prompt: () => "" }).installFetchGuard();
  assert.equal((await win2.fetch("/api/catalog")).status, 401);
  assert.equal(count, 1);
});

test("toast: one box, replaced text, action button hides it, announce mirrors it", () => {
  const doc = fakeDoc();
  const announced = [];
  const toast = createToast({ doc, announce: (t) => announced.push(t), ttl: 10 });
  let clicked = 0;
  const box = toast("第一条", { action: "查看", onAction: () => { clicked += 1; } });
  assert.equal(doc.body.children.length, 1);
  assert.equal(box.children.length, 2);
  assert.equal(box.children[0].textContent, "第一条");
  assert.equal(box.children[1].textContent, "查看");
  box.children[1].listeners.click();
  assert.equal(clicked, 1);
  assert.equal(box.hidden, true);
  const again = toast("第二条");
  assert.equal(again, box, "the same box is reused");
  assert.equal(box.hidden, false);
  assert.equal(box.children.length, 1);
  assert.deepEqual(announced, ["第一条", "第二条"]);
});

test("drafts: saved per session as you type, restored on return, cleared on send", () => {
  const st = storage();
  const ta = { value: "" };
  let sid = "a";
  const restored = [];
  const drafts = createDrafts({ storage: st, input: () => ta, session: () => sid, afterRestore: (el) => restored.push(el.value) });
  ta.value = "写到一半";
  drafts.save();
  assert.equal(st.getItem(DRAFT_PREFIX + "a"), "写到一半");
  sid = "b";
  assert.equal(drafts.restore(), "");
  assert.equal(ta.value, "");
  ta.value = "   ";
  drafts.save();
  assert.equal(st.getItem(DRAFT_PREFIX + "b"), null, "blank drafts are not kept");
  sid = "a";
  assert.equal(drafts.restore(), "写到一半");
  assert.deepEqual(restored, ["", "写到一半"]);
  drafts.clear();
  assert.equal(st.getItem(DRAFT_PREFIX + "a"), null);
  drafts.clear("zzz"); // unknown session: no error
});

test("uploads: precheck mirrors the server's rules; accept reads the wrapped response once", () => {
  const fmt = (n) => `${Math.round(n / 1024 / 1024)} MB`;
  assert.equal(precheck({ name: "投标.pdf", size: 10 }), "");
  assert.match(precheck({ name: "幻灯片.pptx", size: 10 }), /不支持 \.pptx，只收 \.pdf/);
  assert.match(precheck({ name: "noext", size: 10 }), /不支持 \.\?/);
  assert.match(precheck({ name: "大.pdf", size: UPLOAD_LIMITS.maxBytes + 1 }, UPLOAD_LIMITS, fmt), /单文件不能超过 20 MB（这个 20 MB）/);
  const attachments = [{ id: "old" }];
  assert.equal(accept({ ok: true, files: [{ id: "a", name: "a.txt" }, { id: "old" }] }, attachments), "");
  assert.deepEqual(attachments.map((a) => a.id), ["old", "a"]);
  assert.equal(accept({ id: "bare", name: "b" }, attachments), "");
  assert.equal(attachments.length, 3);
  assert.match(accept({ ok: true, files: [] }, attachments), /未返回附件信息/);
});

test("uploads: the queue runs two at a time over fetch, refuses beyond the session limit, and settles failures", async () => {
  const state = { session: "s1", attachments: Array.from({ length: 9 }, (_, i) => ({ id: "have" + i })) };
  const log = [];
  let inflight = 0, peak = 0;
  const gates = [];
  const deps = {
    state, capability: () => true, addStatus: (t) => log.push(t), render: () => {}, apiError: async (r) => r.detail, askToken: async () => false,
    fmtBytes: (n) => `${n} B`, XMLHttpRequest: null, doc: null,
    fetch: (url, init) => new Promise((resolve) => {
      inflight += 1; peak = Math.max(peak, inflight);
      const name = init.body.get("file").name;
      gates.push(() => { inflight -= 1; resolve(name.includes("bad") ? { ok: false, status: 400, detail: "扫描件需要 OCR" } : { ok: true, json: async () => ({ files: [{ id: "id-" + name, name }] }) }); });
    }),
  };
  const uploads = createUploads(deps);
  const files = ["one.txt", "two.txt", "bad.pdf", "four.txt"].map((name) => new File(["x"], name));
  const run = uploads.upload(files);
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(peak, 2, "concurrency 2");
  assert.equal(uploads.pending.length, 3, "9 existing + 3 queued = the 12 limit; the fourth is refused");
  assert.ok(log.some((t) => t.includes("four.txt") && t.includes("同一会话最多 12 个附件")), log.join("\n"));
  // release requests as they appear: the third only starts once one of the first two finished
  const done = run.then(() => true);
  let finished = false;
  done.then(() => { finished = true; });
  while (!finished) {
    while (gates.length) gates.shift()();
    await new Promise((r) => setTimeout(r, 0));
  }
  await run;
  assert.deepEqual(state.attachments.slice(9).map((a) => a.id).sort(), ["id-one.txt", "id-two.txt"]);
  assert.ok(uploads.pending.length <= 1 && uploads.pending.every((u) => u.error), "only the failed upload stays, marked");
  assert.ok(log.some((t) => t.includes("bad.pdf") && t.includes("OCR")), log.join("\n"));
});

test("uploads: a session switch mid-upload drops the result instead of attaching it elsewhere", async () => {
  const state = { session: "s1", attachments: [] };
  let finish;
  const deps = { state, capability: () => true, addStatus: () => {}, render: () => {}, apiError: async () => "", askToken: async () => false,
    XMLHttpRequest: null, doc: null, fetch: () => new Promise((resolve) => { finish = resolve; }) };
  const uploads = createUploads(deps);
  const run = uploads.upload([{ name: "plan.csv", size: 1 }]);
  await new Promise((r) => setTimeout(r, 0));
  state.session = "s2";
  uploads.abortAll("s2");
  finish({ ok: true, json: async () => ({ files: [{ id: "late", name: "plan.csv" }] }) });
  await run;
  assert.deepEqual(state.attachments, []);
  assert.equal(uploads.pending.length, 0);
});

/* ---- turn-stream: the handler and the resume loop, with every dependency faked ---- */
const { createTurnStream } = require("../demo/static/modules/turn-stream.js");
const CB_CHAT_STREAM = require("../demo/static/chat-stream.js");

function turnDeps(overrides = {}) {
  const log = element("div");
  const msgs = [];
  const status = [];
  let active = null;
  const state = { session: "s1", history: [], summoned: [], attachments: [], attachmentRoles: {} };
  const deps = {
    state,
    run: { active: () => active, setActive: (r) => { active = r; }, paint() {}, releaseWatch() {}, watch: (sid, opts) => status.push("watch:" + sid), background: new Set() },
    ui: { log: () => log, addMsg: (role, who, text) => { const b = element("div"); b.textContent = text; const m = element("div"); m.appendChild(b); msgs.push({ role, who, body: b }); return b; },
      addStatus: (t) => status.push(t), announce() {}, doc: { createElement: element } },
    hitl: { confirmed: () => false, clear() {}, enable() {}, pending: () => false },
    turnUi: { tlCreate: () => ({ status() {}, finish() {}, error() {} }), routePaint() {}, collaborationPaint() {}, obStep() {}, paintContext() {},
      estimateLocalContext: () => ({}), renderCites() {}, appendDocCards() {}, fixMount() {}, classifyMissing: () => null, refreshAuditSoon() {},
      skillWho: (id) => id || "岗位", namesOrPlain: () => "岗位", setLastDeliverables() {} },
    projectId: () => "", loadThreads: async () => {}, apiError: async (r) => r.statusText || "", capability: () => true,
    stream: CB_CHAT_STREAM, fetch: async () => { throw new Error("no fetch in this test"); }, AbortController,
    ...overrides,
  };
  const turns = createTurnStream(deps);
  return { turns, state, msgs, status, log, setActive: (r) => { active = r; }, deps };
}
const sse = (frames) => new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode(frames)); c.close(); } });
const idFrame = (id, ev, data) => `id: ${id}\nevent: ${ev}\ndata: ${JSON.stringify(data)}\n\n`;

test("turn-stream: the handler paints tokens, records the answer once on done, and skips repeated ids", () => {
  const t = turnDeps();
  const run = { controller: new AbortController(), session: "s1", bodyEl: null, lastSeq: 0 };
  t.setActive(run);
  const v = t.turns.turnView("问题", null, run);
  const h = t.turns.turnHandler(v);
  h("context", "{}", "1");
  h("token", JSON.stringify({ text: "已生成" }), "2");
  h("token", JSON.stringify({ text: "已生成" }), "2");       // a replayed frame: ignored
  h("token", JSON.stringify({ text: "的一部分" }), "3");
  assert.equal(v.bodyEl.textContent, "已生成的一部分");
  assert.equal(t.msgs.length, 1, "the bubble was created on the first token");
  assert.equal(v.lastSeq, 3);
  h("done", JSON.stringify({ text: "已生成的一部分，完", deliverables: [] }), "4");
  assert.equal(v.complete, true);
  assert.deepEqual(t.state.history, [{ role: "assistant", content: "已生成的一部分，完" }]);
  assert.throws(() => h("error", JSON.stringify({ text: "模型说不行" }), "5"), (e) => e.name === "TurnError" && /模型说不行/.test(e.message));
  assert.throws(() => h("done", "not-json", "6"), (e) => e.name === "TurnError");
  t.setActive(null);
  h("token", JSON.stringify({ text: "晚到的" }), "7");
  assert.equal(v.bodyEl.textContent, "已生成的一部分，完", "nothing paints after the run is no longer active");
});

test("turn-stream: resume replays from the last id and completes; a 404 hands over to polling", async () => {
  const calls = [];
  const t = turnDeps({ fetch: async (url) => {
    calls.push(url);
    if (url.includes("/events?after=2")) return new Response(sse(idFrame(2, "token", { text: "x" }) + idFrame(3, "token", { text: "，剩下的" }) + idFrame(4, "done", { text: "一半，剩下的" })), { status: 200 });
    return new Response("", { status: 404 });
  } });
  const run = { controller: new AbortController(), session: "s1", bodyEl: null, lastSeq: 0 };
  t.setActive(run);
  const v = t.turns.turnView("问题", null, run);
  t.turns.turnHandler(v)("token", JSON.stringify({ text: "一半" }), "2");
  await t.turns.resumeTurn(v);
  assert.equal(v.complete, true);
  assert.equal(v.bodyEl.textContent, "一半，剩下的");
  assert.deepEqual(calls, ["/api/sessions/s1/events?after=2"]);

  // attach to a running session on a backend without the event log: polling recovery instead
  const t2 = turnDeps({ capability: (n) => (n === "event_log" ? false : true) });
  await t2.turns.attachToTurn("s1", "回来；");
  assert.deepEqual(t2.status, ["watch:s1"]);
});
