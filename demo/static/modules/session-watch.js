/* Watching a session from the page's side, without a stream of its own.
 *
 * - detachActiveRun: leaving a running task keeps it running on the server and remembers it
 *   as a background session.
 * - bgObserve / bgSchedule / bgTick: while any other session is running, poll the list every
 *   5 s and announce the one that finished (toast with 查看).
 * - watchSession / paintLive / paintRecovered: a running turn on a backend without an event
 *   log is polled until it ends, its live text painted meanwhile, and the stored result
 *   painted into the view when it is over. runState.watched is that watched turn.
 *
 * Dependencies come in as deps; nothing global is read:
 *   state, runState, sessionRequest()          page state; the navigation counter
 *   runPaint(bool), announce(text), addMsg(role, who, text), addStatus(text), toast(text, opts)
 *   openSession(row), loadThreads()            navigation and the list
 *   appendDocCards(files, bodyEl, opts), setLastDeliverables(files), refreshAuditSoon()
 *   capability(name), fetch, doc, log(), setTimeout / clearTimeout / now()   the environment
 */
export function createSessionWatch(deps) {
  const { state, runState, sessionRequest, runPaint, announce, addMsg, addStatus, toast, openSession,
    loadThreads, appendDocCards, setLastDeliverables, refreshAuditSoon, capability, doc, log } = deps;
  const doFetch = deps.fetch;
  const now = deps.now || (() => Date.now());
  /* Timers are injected so a test can hold the 1.5 s / 5 s polls in its hand. */
  const timers = { set: deps.setTimeout || ((fn, ms) => setTimeout(fn, ms)), clear: deps.clearTimeout || ((t) => clearTimeout(t)) };

  function detachActiveRun() {
    releaseWatch();
    if (!runState.active) return;
    const run = runState.active;
    run.detached = true;
    run.controller.abort();
    runState.active = null;
    runPaint(false);
    runState.background.add(run.session);
    announce("任务继续在后台运行，回到该任务可查看结果");
    loadThreads().catch(() => {});
    bgSchedule();
  }

  let watchTimer = null;

  /* 切走的任务跑完了要有人说一声：只要列表里还有「运行中」的会话，就每 5 s 拉一次
     /api/sessions，从运行中变成不运行的那一个弹一条可点的提示，点了就切过去。
     当前会话由 watchSession 自己盯着，这里只管别的。 */
  let bgTimer = null;
  let bgKnownRunning = new Set();
  let bgRows = new Map();

  function bgObserve(rows) {
    const nowRunning = new Set();
    for (const s of rows || []) {
      if (!s || !s.session_id) continue;
      bgRows.set(s.session_id, s);
      if (s.running === true) nowRunning.add(s.session_id);
    }
    for (const sid of new Set([...bgKnownRunning, ...runState.background])) {
      if (nowRunning.has(sid) || sid === state.session) continue;
      runState.background.delete(sid);
      const row = bgRows.get(sid);
      if (!row) continue; /* 列表里已经没有它了：不猜结果 */
      toast(`「${row.title || sid}」已在后台完成`, { action: "查看", onAction: () => openSession(row) });
    }
    bgKnownRunning = nowRunning;
    bgSchedule();
  }

  function bgSchedule() {
    if (bgTimer) { timers.clear(bgTimer); bgTimer = null; }
    const others = [...new Set([...bgKnownRunning, ...runState.background])].filter((sid) => sid !== state.session);
    if (!others.length) return;
    bgTimer = timers.set(bgTick, 5000);
  }

  async function bgTick() {
    bgTimer = null;
    let rows = null;
    try {
      const r = await doFetch("/api/sessions?limit=100");
      if (r.ok) rows = (await r.json()).sessions;
    } catch (_) { /* 网络抖动：下一拍再试 */ }
    if (!Array.isArray(rows)) { bgSchedule(); return; }
    const before = new Set(bgKnownRunning);
    bgObserve(rows);
    const changed = before.size !== bgKnownRunning.size || [...before].some((sid) => !bgKnownRunning.has(sid));
    if (changed) loadThreads().catch(() => {});
  }


  /* 旁观中的后台轮次：页面上没有流，但服务端这一轮还在跑，会话因此是忙的（再发消息只会 409）。
     所以它要按「运行中」来画，也要能被停止——否则回到任务的人只能干等到完成或服务端超时。
     形状和 runState.active 一样（session / cancelRequested），停止按钮因此不用区分两者。 */
  function releaseWatch() {
    if (watchTimer) { timers.clear(watchTimer); watchTimer = null; }
    if (!runState.watched) return;
    runState.watched = null;
    if (!runState.active) runPaint(false);
  }


  /* 轮询 /api/sessions/{sid}，直到服务端这一轮结束；若仍停留在该任务，则把留存的结果补画出来。 */
  async function watchSession(sid, opts) {
    const options = opts || {};
    const request = sessionRequest();
    const started = now();
    const maxMs = Number(options.maxMs) || 10 * 60 * 1000;
    if (watchTimer) { timers.clear(watchTimer); watchTimer = null; }
    if (runState.watched && runState.watched.session !== sid) releaseWatch();
    const superseded = () => state.session !== sid || request !== sessionRequest() || !!runState.active;
    const tick = async () => {
      if (superseded()) { if (runState.watched && runState.watched.session === sid) releaseWatch(); return; }
      let d = null;
      try {
        const r = await doFetch("/api/sessions/" + encodeURIComponent(sid));
        if (r.ok) d = await r.json();
      } catch (_) { /* 网络抖动：下一拍再试 */ }
      if (superseded()) { if (runState.watched && runState.watched.session === sid) releaseWatch(); return; }
      const active = !!(d && d.turn_state && d.turn_state.active);
      if (active && now() - started < maxMs) {
        if (!runState.watched || runState.watched.session !== sid) {
          runState.watched = { session: sid, cancelRequested: false };
          runPaint(true);
          /* 没有取消能力的后端上，停止按钮什么也做不了：不要摆一个假的。 */
          const stop = doc.getElementById("stop");
          if (stop && capability("cancel") !== true) stop.hidden = true;
        }
        await paintLive(sid, options);
        if (superseded()) { if (runState.watched && runState.watched.session === sid) releaseWatch(); return; }
        watchTimer = timers.set(tick, 1500);
        return;
      }
      releaseWatch();
      if (active) {
        /* 超过了本页愿意等的时长，但它确实还在跑：别把它说成「已完成」。 */
        addStatus("这个任务仍在后台运行，稍后回到该任务查看结果。");
        return;
      }
      runState.background.delete(sid);
      if (d) paintRecovered(d, options);
      loadThreads().catch(() => {});
    };
    tick();
  }

  /* 旁观时也要看得见它跑到哪：服务端把这一轮已产出的正文和最近一条状态留在内存里
     （GET /api/sessions/{sid}/live），每一拍拉一次，有变化就画。没有气泡的（切回来的会话）先补一个。 */
  async function paintLive(sid, options) {
    if (capability("live_progress") !== true) return;
    let live = null;
    try {
      const r = await doFetch("/api/sessions/" + encodeURIComponent(sid) + "/live");
      if (r.ok) live = await r.json();
    } catch (_) { /* 下一拍再试 */ }
    if (!live || state.session !== sid || runState.active) return;
    if (options.liveSeq === live.seq) return;
    options.liveSeq = live.seq;
    if (!live.text && !live.status) return;
    let bodyEl = options.bodyEl && options.bodyEl.isConnected ? options.bodyEl : null;
    if (!bodyEl && live.text) {
      bodyEl = addMsg("assistant", "岗位", "");
      options.bodyEl = bodyEl;
    }
    if (bodyEl && live.text && bodyEl.textContent !== live.text) {
      bodyEl.textContent = live.text;
      log().scrollTop = log().scrollHeight;
    }
    if (live.status && !live.done) {
      let line = options.liveStatusEl && options.liveStatusEl.isConnected ? options.liveStatusEl : null;
      if (!line) {
        line = doc.createElement("p");
        line.className = "status-line";
        line.dataset.live = "1";
        const host = bodyEl ? bodyEl.parentElement : log();
        if (host) host.appendChild(line);
        options.liveStatusEl = line;
      }
      line.textContent = "后台进行中 · " + live.status;
    }
  }

  /* 把服务端留存的最后一条助手回复 + 交付物补画到当前视图（断流恢复 / 后台任务完成）。 */
  function paintRecovered(d, options) {
    if (options.liveStatusEl && options.liveStatusEl.isConnected) options.liveStatusEl.remove();
    const transcript = Array.isArray(d.transcript) ? d.transcript : [];
    const last = transcript.filter((t) => t && t.role === "assistant").slice(-1)[0];
    const text = last ? String(last.text || "") : "";
    const bodyEl = options.bodyEl && options.bodyEl.isConnected ? options.bodyEl : null;
    if (bodyEl) {
      if (text) { if (typeof deps.markdown === "function") deps.markdown(bodyEl, text); else bodyEl.textContent = text; }
      const known = state.history.filter((h) => h.role === "assistant").slice(-1)[0];
      if (text && (!known || known.content !== text)) state.history.push({ role: "assistant", content: text });
    } else if (text && !state.history.some((h) => h.role === "assistant" && h.content === text)) {
      const el = addMsg("assistant", "岗位", text);
      if (typeof deps.markdown === "function") deps.markdown(el, text);
      state.history.push({ role: "assistant", content: text });
      options.bodyEl = el;
    }
    const files = Array.isArray(d.deliverables) ? d.deliverables.filter((f) => f && typeof f.path === "string" && f.path) : [];
    const target = options.bodyEl && options.bodyEl.isConnected ? options.bodyEl : null;
    if (files.length && target) {
      setLastDeliverables(files);
      const runs = Array.isArray(d.deliverable_runs) ? d.deliverable_runs.slice(0, 1) : [];
      appendDocCards(files, target, { runs });
    }
    const st = d.turn_state && d.turn_state.state;
    /* 怎么结束的就怎么说：被停止（人点的，或无人值守超时由服务端停的）和没跑成，都不是「已完成」。 */
    const outcome = st === "cancelled" ? "该任务已被停止，已有内容已保留。"
      : st === "failed" ? "该任务没有跑完，已有内容已保留，可重试。"
      : "任务已在后台完成，结果已恢复。";
    addStatus((options.reason || "") + outcome);
    refreshAuditSoon();
  }

  return { detachActiveRun, bgObserve, bgSchedule, bgTick, releaseWatch, watchSession, paintLive, paintRecovered };
}
