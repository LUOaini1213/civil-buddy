/* Attachment uploads for one page.
 *
 * The limits demo/uploads.py enforces are checked here first (type list, bytes per file,
 * files per session) so a 20 MB .pptx is refused before a byte leaves the phone. Two
 * uploads run at a time, the rest queue; XHR gives progress, and where there is no
 * XMLHttpRequest (automated tests) the same queue runs over fetch without progress. A
 * failed upload stays in the row with the server's reason until retried or removed.
 *
 * Dependencies are handed in, nothing global is read:
 *   state        { session, attachments }        the page's state object
 *   capability   (name) => true | false | undefined
 *   addStatus    (text)                           a line in the conversation log
 *   render       ()                               redraw the attachment row
 *   apiError     async (res) => text              server error text from a Response
 *   askToken     async (reason) => bool           token prompt (401)
 *   fmtBytes     (n) => "1.2 MB"
 *   fetch, XMLHttpRequest, doc                    the environment (XMLHttpRequest may be null)
 */
export const UPLOAD_LIMITS = Object.freeze({
  maxBytes: 20 * 1024 * 1024,
  maxFiles: 12,
  ext: Object.freeze(["pdf", "docx", "xlsx", "txt", "md", "csv", "json", "log"]),
});
export const UPLOAD_CONCURRENCY = 2;

export function precheck(file, limits = UPLOAD_LIMITS, fmtBytes = (n) => `${n} B`) {
  const name = String(file.name || "");
  const ext = (name.match(/\.([A-Za-z0-9]+)$/) || [, ""])[1].toLowerCase();
  if (!limits.ext.includes(ext)) return `不支持 .${ext || "?"}，只收 ${limits.ext.map((e) => "." + e).join(" ")}`;
  if (file.size > limits.maxBytes) return `单文件不能超过 ${fmtBytes(limits.maxBytes)}（这个 ${fmtBytes(file.size)}）`;
  return "";
}

/* /api/upload answers {ok, files:[{id,name,bytes,...}]}, not a bare record. */
export function accept(meta, attachments) {
  const items = Array.isArray(meta && meta.files) ? meta.files : (meta && meta.id ? [meta] : []);
  if (!items.length) return "工作台未返回附件信息，请重试上传。";
  for (const item of items) {
    if (item && item.id && !attachments.some((a) => a.id === item.id)) attachments.push(item);
  }
  return "";
}

export function createUploads(deps) {
  const { state, capability, addStatus, render, apiError, askToken, doc } = deps;
  const fmtBytes = deps.fmtBytes || ((n) => `${n} B`);
  const limits = deps.limits || UPLOAD_LIMITS;
  const concurrency = deps.concurrency || UPLOAD_CONCURRENCY;
  const XHR = deps.XMLHttpRequest || null;
  const doFetch = deps.fetch;
  /* In flight: { key, session, name, bytes, loaded, xhr, file, error, done, settled, resolve } */
  const pending = [];
  let counter = 0;

  function slotsLeft(session) {
    const have = state.attachments.filter((a) => !String(a.id || "").startsWith("job:")).length
      + pending.filter((u) => u.session === session && !u.error).length;
    return limits.maxFiles - have;
  }

  function drop(u) {
    const i = pending.indexOf(u);
    if (i >= 0) pending.splice(i, 1);
    if (u.resolve) u.resolve();
  }

  function abortAll(exceptSession) {
    for (const u of pending.slice()) {
      if (exceptSession && u.session === exceptSession) continue;
      if (u.xhr) { u.xhr.abort(); u.xhr = null; }
      drop(u);
    }
  }

  function pump() {
    for (const u of pending) {
      if (pending.filter((v) => v.xhr).length >= concurrency) break;
      if (u.xhr || u.error || u.done) continue;
      start(u);
    }
    render();
  }

  function finish(u, err) {
    u.xhr = null;
    if (err) {
      u.error = err;
      addStatus("附件上传失败（" + u.name + "）：" + err);
      if (u.resolve) u.resolve(); // the caller does not wait for 重试
    } else {
      u.done = true;
      drop(u);
    }
    render();
    pump();
  }

  function paintProgress(u) {
    if (!doc || typeof doc.querySelector !== "function") return;
    const bar = doc.querySelector(`[data-upload="${u.key}"] .cb-att-bar > i`);
    const pct = doc.querySelector(`[data-upload="${u.key}"] .cb-att-pct`);
    const ratio = u.bytes ? Math.min(1, u.loaded / u.bytes) : 0;
    if (bar) bar.style.width = Math.round(ratio * 100) + "%";
    if (pct) pct.textContent = Math.round(ratio * 100) + "%";
  }

  function start(u, retried) {
    if (!u.settled) u.settled = new Promise((resolve) => { u.resolve = resolve; });
    if (typeof XHR !== "function") { startFetch(u); return; }
    const xhr = new XHR();
    u.xhr = xhr; u.loaded = 0; u.error = "";
    const fd = new FormData();
    fd.append("session_id", u.session);
    fd.append("file", u.file);
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) u.loaded = ev.loaded;
      paintProgress(u);
    };
    xhr.onload = async () => {
      if (state.session !== u.session) { drop(u); render(); pump(); return; }
      if (xhr.status === 401 && !retried) {
        if (await askToken("上传需要口令，填好后再传一次")) { start(u, true); return; }
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        let msg = "HTTP " + xhr.status;
        try { const j = JSON.parse(xhr.responseText); if (typeof j.detail === "string") msg = j.detail; } catch (e) { /* not JSON */ }
        finish(u, msg); return;
      }
      let meta = null;
      try { meta = JSON.parse(xhr.responseText); } catch (e) { finish(u, "工作台未返回附件信息，请重试上传。"); return; }
      finish(u, accept(meta, state.attachments));
    };
    xhr.onerror = () => finish(u, "网络错误，可点「重试」");
    xhr.onabort = () => { u.xhr = null; render(); pump(); };
    xhr.open("POST", "/api/upload");
    xhr.send(fd);
    render();
  }

  async function startFetch(u) {
    u.xhr = { abort() {} };
    const fd = new FormData();
    fd.append("session_id", u.session);
    fd.append("file", u.file);
    try {
      const r = await doFetch("/api/upload", { method: "POST", body: fd });
      if (state.session !== u.session) { drop(u); render(); pump(); return; }
      if (!r.ok) throw new Error(await apiError(r) || "HTTP " + r.status);
      finish(u, accept(await r.json(), state.attachments));
    } catch (e) {
      if (state.session !== u.session) { drop(u); render(); pump(); return; }
      finish(u, (e && e.message) || String(e));
    }
  }

  /* Queue every acceptable file and resolve when this batch has settled (done, failed or removed). */
  async function upload(fileList) {
    if (capability("attachments") === false) {
      addStatus("当前工作台未提供附件上传，可以将材料要点粘贴到输入框。");
      return;
    }
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const session = state.session;
    let slots = slotsLeft(session);
    const refused = [];
    const queued = [];
    for (const file of files) {
      const why = precheck(file, limits, fmtBytes);
      if (why) { refused.push(`${file.name}：${why}`); continue; }
      if (slots <= 0) { refused.push(`${file.name}：同一会话最多 ${limits.maxFiles} 个附件`); continue; }
      slots -= 1;
      counter += 1;
      const u = { key: "up" + counter, session, name: file.name, bytes: file.size || 0, loaded: 0, xhr: null, file, error: "", done: false };
      u.settled = new Promise((resolve) => { u.resolve = resolve; }); // queued files count too, not only started ones
      pending.push(u);
      queued.push(u);
    }
    if (refused.length) addStatus("未上传：" + refused.join("；"));
    pump();
    await Promise.all(queued.map((u) => u.settled || Promise.resolve()));
  }

  function retry(u) { u.error = ""; pump(); }
  function cancel(u) { if (u.xhr) u.xhr.abort(); drop(u); render(); pump(); }

  return { pending, upload, abortAll, pump, drop, retry, cancel, paintProgress, slotsLeft, limits };
}
