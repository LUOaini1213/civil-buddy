const state = {
  experts: [],
  catalog: null,
  summoned: new Set(),
  history: [],
  session: crypto.randomUUID().slice(0, 12),
  modelName: "",
  attachments: [],
  threadId: "",
  policy: { sandbox: "workspace-write", approval: "on-request" },
  context: {
    limit: 1000000,
    reserve: 16384,
    compress_pct: 70,
    warn_pct: 50,
    keep_recent: 4,
    compress_at: 86732,
  },
};

const $ = (id) => document.getElementById(id);

async function boot() {
  const health = await fetch("/api/health").then((r) => r.json());
  const badge = $("keyBadge");
  if (health.has_key || health.deepseek) {
    badge.textContent = "已配置 API Key";
    badge.className = "pill ok";
  } else {
    badge.textContent = "缺少 API Key";
    badge.className = "pill warn";
  }
  if (health.model) {
    state.modelName = health.model;
  }
  if (health.model && $("modelBadge")) {
    const lim = health.context && health.context.limit;
    $("modelBadge").textContent = lim
      ? `模型 ${health.model} · 上下文 ${lim}`
      : `模型 ${health.model}`;
  }
  if (health.harness && $("harnessBadge")) {
    $("harnessBadge").textContent =
      health.harness.summoned_default === "chat"
        ? "Harness 能聊能跑"
        : `Harness ${health.harness.default_mode || "steps"}`;
  }
  if (health.context) {
    state.context = { ...state.context, ...health.context };
  }
  paintContext(estimateLocalContext());
  await reloadCatalog();
  await loadJobRoot();
  await loadPolicy();
  await loadThreads();
}

async function loadPolicy() {
  try {
    const cfg = await fetch("/api/config").then((r) => r.json());
    state.policy = cfg;
    if ($("sandboxBadge")) $("sandboxBadge").textContent = `sandbox ${cfg.sandbox || ""}`;
    if ($("approvalBadge")) $("approvalBadge").textContent = `approval ${cfg.approval || ""}`;
  } catch (e) {
    addStatus(String(e));
  }
}

async function loadThreads() {
  const box = $("threadList");
  if (!box) return;
  try {
    const data = await fetch("/api/threads").then((r) => r.json());
    box.innerHTML = "";
    for (const t of data.threads || []) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "thread-row" + (t.thread_id === state.threadId ? " on" : "");
      b.textContent = `${t.thread_id} · ${t.state} · ${t.title || ""}`;
      b.addEventListener("click", () => {
        state.threadId = t.thread_id;
        state.session = t.session_id || t.thread_id;
        loadThreads();
        addStatus(`thread ${t.thread_id}`);
      });
      box.appendChild(b);
    }
  } catch (e) {
    box.textContent = "";
  }
}

if ($("btnNewThread")) {
  $("btnNewThread").addEventListener("click", async () => {
    const data = await fetch("/api/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "新对话" }),
    }).then((r) => r.json());
    state.threadId = data.thread_id;
    state.session = data.session_id || data.thread_id;
    await loadThreads();
    addStatus(`/new ${data.thread_id}`);
  });
}
if ($("btnBg")) {
  $("btnBg").addEventListener("click", async () => {
    const text = $("input").value.trim();
    if (!text) {
      addStatus("/bg 先在输入框写任务");
      return;
    }
    $("input").value = "";
    const data = await fetch("/api/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, background: true, confirm_ok: $("confirmOk").checked }),
    }).then((r) => r.json());
    addStatus(`并行 thread ${data.thread_id} ${data.state || "running"}`);
    await loadThreads();
  });
}

async function handleSlash(message) {
  const parts = message.slice(1).split(/\s+/);
  const cmd = (parts[0] || "").toLowerCase();
  const arg = parts.slice(1).join(" ");
  if (cmd === "skills") {
    const data = await fetch("/api/skills").then((r) => r.json());
    const q = arg.toLowerCase();
    const rows = (data.skills || []).filter((s) => !q || `${s.name} ${s.description}`.toLowerCase().includes(q));
    addStatus(`${rows.length} skills`);
    addMsg("assistant", "skills", rows.slice(0, 20).map((s) => `$${s.name}  ${s.description}`).join("\n"));
    return true;
  }
  if (cmd === "new") {
    $("btnNewThread") && $("btnNewThread").click();
    return true;
  }
  if (cmd === "bg") {
    $("input").value = arg;
    $("btnBg") && $("btnBg").click();
    return true;
  }
  if (cmd === "sandbox" || cmd === "approvals" || cmd === "approval") {
    const body = cmd === "sandbox" ? { sandbox: arg } : { approval: arg };
    if (arg) {
      await fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    }
    await loadPolicy();
    addStatus(`${cmd} ${arg || (cmd === "sandbox" ? state.policy.sandbox : state.policy.approval)}`);
    return true;
  }
  if (cmd === "threads") {
    await loadThreads();
    addStatus("threads 已刷新");
    return true;
  }
  if (cmd === "help") {
    addMsg("assistant", "help", "/skills /new /bg /threads /sandbox /approvals\n全企业可问任意专家。确认句：我明白，将由持证人员签认");
    return true;
  }
  return false;
}

async function loadJobRoot() {
  try {
    const job = await fetch("/api/job").then((r) => r.json());
    const box = $("attaches");
    if (!box) return;
    if (!job.granted) {
      addStatus(job.hint || "未授权作业根。设 CIVIL_JOB_ROOT 后可直接读本机文件。");
      return;
    }
    addStatus(`作业根 ${job.root} · 已看到 ${(job.files || []).length} 个文件，说「写一份」会自动抄，不必再上传。`);
    for (const f of job.files || []) {
      if (state.attachments.some((a) => a.id === `job:${f.name}`)) continue;
      state.attachments.push({ id: `job:${f.name}`, name: f.name, layer: "job" });
    }
    renderAttaches();
  } catch (e) {
    addStatus(String(e));
  }
}

async function reloadCatalog() {
  const cat = await fetch("/api/catalog").then((r) => r.json());
  state.catalog = cat;
  state.experts = cat.experts;
  renderWall(cat);
  renderSummon();
  if (window.studioOnCatalog) window.studioOnCatalog(cat);
}

window.reloadCatalog = reloadCatalog;

function renderWall(cat) {
  const wall = $("wall");
  if (!wall || !cat) return;
  const q = (($("skillQ") && $("skillQ").value) || "").trim().toLowerCase();
  wall.innerHTML = "";
  for (const c of cat.categories) {
    const experts = cat.experts.filter((x) => {
      if (x.category !== c.id) return false;
      if (!q) return true;
      const blob = `${x.name} ${x.id} ${(x.aliases || []).join(" ")} ${x.delivers || ""}`.toLowerCase();
      return blob.includes(q);
    });
    if (!experts.length) continue;
    const h = document.createElement("div");
    h.className = "cat";
    h.textContent = c.name;
    wall.appendChild(h);
    for (const e of experts) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "exp";
      b.dataset.id = e.id;
      const size = e.kb_label ? ` · 本岗 ${e.kb_label}` : "";
      const mark = e.over_limit ? " over" : "";
      b.innerHTML = `<b>${e.name}</b><span class="${mark}">${e.delivers}${size}</span>`;
      b.addEventListener("click", () => toggle(e.id));
      wall.appendChild(b);
    }
  }
  renderSummon();
}

function toggle(id) {
  if (state.summoned.has(id)) state.summoned.delete(id);
  else state.summoned.add(id);
  renderSummon();
  refreshKb();
}

function renderSummon() {
  document.querySelectorAll(".exp").forEach((el) => {
    el.classList.toggle("on", state.summoned.has(el.dataset.id));
  });
  const names = [...state.summoned].map((id) => {
    const e = state.experts.find((x) => x.id === id);
    return e ? `${e.category_name}/${e.name}` : id;
  });
  $("summonBar").innerHTML = names.length
    ? `当前：<em>${names.join(" · ")}</em>`
    : "当前：<em>未点名岗位</em> · 直接下任务即可";
}

if ($("skillQ")) {
  $("skillQ").addEventListener("input", () => {
    if (state.catalog) renderWall(state.catalog);
  });
}

$("clearExperts").addEventListener("click", () => {
  state.summoned.clear();
  renderSummon();
  $("kblist").innerHTML = "";
});

document.querySelectorAll("[data-fill]").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("input").value = btn.dataset.fill;
    $("input").focus();
  });
});

async function refreshKb() {
  const box = $("kblist");
  box.innerHTML = "";
  for (const id of state.summoned) {
    const data = await fetch(`/api/kb/${id}`).then((r) => r.json());
    for (const f of data.files) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "kb-link";
      const label = f.display || f.title || (f.path || "").split("/").pop();
      const layer = f.layer_label || layerName(f.layer);
      const sz = f.bytes != null ? ` · ${fmtBytes(f.bytes)}` : "";
      btn.innerHTML = `<span class="layer ${f.layer}">${escapeHtml(layer)}</span>${escapeHtml(label)}<span class="kb-size">${sz}</span>`;
      btn.title = f.path || "";
      btn.addEventListener("click", () => window.openStudio && window.openStudio(f.path, f.layer === "expert" ? id : null));
      li.appendChild(btn);
      box.appendChild(li);
    }
  }
}

function layerName(layer) {
  if (layer === "expert") return "本岗知识";
  if (layer === "category") return "大类共享";
  if (layer === "web") return "网上检索";
  if (layer === "upload") return "用户上传";
  if (layer === "job") return "作业根";
  return "公司规则";
}

function fmtBytes(n) {
  const x = Number(n) || 0;
  if (x < 1024) return `${x} B`;
  if (x < 1024 * 1024) return `${(x / 1024).toFixed(1)} KB`;
  return `${(x / (1024 * 1024)).toFixed(2)} MB`;
}

function fmtNum(n) {
  return Number(n || 0).toLocaleString("zh-CN");
}

function isCjk(ch) {
  const c = ch.codePointAt(0);
  return (c >= 0x4e00 && c <= 0x9fff) || (c >= 0x3400 && c <= 0x4dbf) || (c >= 0xf900 && c <= 0xfaff);
}

function estimateTokens(text) {
  let cjk = 0;
  let other = 0;
  for (const ch of String(text || "")) {
    if (/\s/.test(ch)) continue;
    if (isCjk(ch)) cjk += 1;
    else other += 1;
  }
  return cjk + Math.ceil(other / 4);
}

function estimateLocalContext() {
  const policy = state.context;
  const limit = policy.limit || 1000000;
  const reserve = policy.reserve || 4096;
  const usable = Math.max(1, limit - reserve);
  let used = 0;
  for (const m of state.history) {
    used += estimateTokens(m.role) + estimateTokens(m.content) + 4;
  }
  const draft = $("input") ? $("input").value : "";
  if (draft) used += estimateTokens(draft) + 8;
  const pct = Math.min(100, Math.round((Math.min(used, usable) * 100) / usable));
  const compressAt = policy.compress_at || Math.floor((usable * (policy.compress_pct || 70)) / 100);
  const keep = policy.keep_recent || 4;
  let zone = "room";
  if (pct >= 90) zone = "full";
  else if (pct >= (policy.compress_pct || 70)) zone = "compact";
  else if (pct >= (policy.warn_pct || 50)) zone = "warn";
  let note;
  if (pct >= 90) {
    note = `上下文快满（约 ${fmtNum(used)} / ${fmtNum(limit)}，${pct}%）。再发可能只留最近 ${keep} 条原文。`;
  } else if (pct >= (policy.warn_pct || 50)) {
    note = `已过半（约 ${fmtNum(used)} / ${fmtNum(limit)}，${pct}%）。用到 ${fmtNum(compressAt)} token（${policy.compress_pct || 70}%）会把更早对话压成摘要，近 ${keep} 条原文保留。`;
  } else {
    note = `还很宽裕（约 ${fmtNum(used)} / ${fmtNum(limit)}，${pct}%）。用到 ${fmtNum(compressAt)} token（${policy.compress_pct || 70}%）会压缩更早对话，近 ${keep} 条原文保留。`;
  }
  return { used, limit, usable, pct, zone, note, estimated: true, compress_at: compressAt, keep_recent: keep };
}

function paintContext(ctx) {
  if (!ctx) return;
  const bar = $("ctxBar");
  const fill = $("ctxFill");
  const text = $("ctxText");
  if (!bar || !fill || !text) return;
  const pct = Math.max(0, Math.min(100, Number(ctx.pct) || 0));
  fill.style.width = `${Math.max(pct, pct > 0 ? 2 : 0)}%`;
  bar.dataset.zone = ctx.zone || "room";
  if (ctx.note) {
    text.textContent = ctx.note;
  } else {
    text.textContent = `上下文 ${fmtNum(ctx.used)} / ${fmtNum(ctx.limit)} · ${pct}%`;
  }
}

function addMsg(role, who, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<div class="who">${who}</div><div class="body"></div>`;
  div.querySelector(".body").textContent = text;
  $("log").appendChild(div);
  $("log").scrollTop = $("log").scrollHeight;
  return div.querySelector(".body");
}

function addStatus(text) {
  const p = document.createElement("p");
  p.className = "status-line";
  p.textContent = text;
  $("log").appendChild(p);
  $("log").scrollTop = $("log").scrollHeight;
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const message = $("input").value.trim();
  if (!message) return;
  $("input").value = "";
  cbAutosize($("input"));
  cbSyncSend();
  cbAtClose();
  if (message.startsWith("/")) {
    const welcome = document.querySelector(".welcome");
    if (welcome) welcome.remove();
    addMsg("user", "你", message);
    try {
      const ok = await handleSlash(message);
      if (!ok) addStatus(`未知命令 ${message}。/help`);
    } catch (err) {
      addStatus(String(err.message || err));
    }
    return;
  }
  const welcome = document.querySelector(".welcome");
  if (welcome) welcome.remove();
  addMsg("user", "你", message);
  state.history.push({ role: "user", content: message });
  paintContext(estimateLocalContext());
  const bodyEl = addMsg("assistant", namesOrPlain(), "");
  const sendBtn = $("send");
  sendBtn.disabled = true;
  sendBtn.dataset.running = "1";
  sendBtn.textContent = "运行中…";
  try {
    await streamChat(message, bodyEl);
  } catch (err) {
    bodyEl.classList.add("err");
    bodyEl.textContent = String(err.message || err);
  } finally {
    sendBtn.textContent = "发送";
    delete sendBtn.dataset.running;
    cbSyncSend();
  }
});

function skillWho(id, source) {
  if (!id) return "未点名岗位";
  const name = (state.experts.find((e) => e.id === id) || {}).name || id;
  const how = source === "given" ? "显式" : source === "matched" ? "规则选用" : "未点名";
  return `$${id} · ${name} · ${how}`;
}

function namesOrPlain() {
  if (!state.summoned.size) return "未点名岗位";
  return [...state.summoned].map((id) => skillWho(id, "given")).join(" / ");
}

async function streamChat(message, bodyEl) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history: state.history.slice(0, -1),
      expert_ids: [...state.summoned],
      confirm_ok: $("confirmOk").checked,
      session_id: state.session,
      attachments: state.attachments
        .filter((a) => !String(a.id || "").startsWith("job:"))
        .map((a) => a.id),
    }),
  });
  if (!res.ok) {
    throw new Error(await apiError(res));
  }
  /* ux(round3)：本条消息挂一条阶段时间线（完成后折叠为一行摘要）；ux(round5)：消息原文供审批卡「确认并重提」 */
  const tl = cbTlCreate(bodyEl, message);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let acc = "";
  let eventName = "message";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const block of parts) {
      let dataLine = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) eventName = line.slice(7).trim();
        if (line.startsWith("data: ")) dataLine += line.slice(6);
      }
      if (!dataLine) continue;
      const data = JSON.parse(dataLine);
      if (eventName === "context") {
        paintContext(data);
      }
      if (eventName === "status") {
        if (tl) tl.status(data);
        if (data.phase === "summon" && acc) {
          state.history.push({ role: "assistant", content: acc });
          acc = "";
          bodyEl = addMsg("assistant", skillWho(data.expert || "", "given"), "");
        }
      }
      if (eventName === "token") {
        acc += data.text || "";
        bodyEl.textContent = acc;
        $("log").scrollTop = $("log").scrollHeight;
      }
      if (eventName === "error") {
        if (tl) tl.error(data.text || "error");
        throw new Error(data.text || "error");
      }
      if (eventName === "done") {
        if (tl) tl.finish(data);
        acc = data.text || acc;
        bodyEl.textContent = acc;
        const whoEl = bodyEl.parentElement && bodyEl.parentElement.querySelector(".who");
        if (whoEl) whoEl.textContent = skillWho(data.skill || data.expert || "", data.skill_source || "");
        if (acc) state.history.push({ role: "assistant", content: acc });
        if (data.context) paintContext(data.context);
        else paintContext(estimateLocalContext());
        renderCites(data.citations || []);
        renderFiles(data.deliverables || []);
        appendDocCards(data.deliverables || [], bodyEl);
        refreshAuditSoon(); /* ux(round6)：本轮完成 → 审计时间线增量刷新（含决策置顶） */
      }
      eventName = "message";
    }
  }
}

function renderCites(cites) {
  const box = $("cites");
  for (const c of cites) {
    const li = document.createElement("li");
    const title = c.display || c.title || (c.path || "").split("/").pop();
    const layer = c.layer_label || layerName(c.layer);
    li.title = c.path || "";
    li.innerHTML = `<span class="layer ${c.layer}">${escapeHtml(layer)}</span><b>${escapeHtml(title)}</b><br>${escapeHtml(c.snippet || c.path || "")}`;
    box.prepend(li);
  }
}

function renderFiles(files) {
  const box = $("files");
  for (const f of files) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = fileUrl(f.path);
    a.textContent = `${f.expert} · ${f.name}`;
    /* ux(round4)：markdown 交付物点开即文书预览（其余类型保持下载） */
    if (isDocMd(f)) {
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        openDeliverable(f);
      });
    }
    li.appendChild(a);
    box.prepend(li);
  }
}

/* ===== ux(round4) 交付物文书预览（cbDocOpen / docpreview.js）===== */

function fileUrl(p) {
  /* Rust canonicalize 返回 \\?\ verbatim 前缀；/api/file 对该形态 404——
     剥掉后端点自会 canonicalize（自测发现：此前侧栏下载链接全部 404）。 */
  return `/api/file?path=${encodeURIComponent(String(p || "").replace(/^\\\\\?\\/, ""))}`;
}

function isDocMd(f) {
  return /\.(md|markdown)$/i.test(String(f && (f.name || f.path) || ""));
}

async function openDeliverable(f) {
  try {
    await window.cbDocOpenUrl({
      url: fileUrl(f.path),
      title: f.name || f.title || "交付物文书",
      role: `岗位 · ${f.expert || "未指定"}`,
    });
  } catch (e) {
    addStatus(`预览失败 ${f.name || ""}：${(e && e.message) || e}`);
  }
}

/* 聊天流内交付物卡片：点开即预览，另留 .md 下载 */
function appendDocCards(files, bodyEl) {
  if (!files || !files.length) return;
  const host = bodyEl && bodyEl.parentElement ? bodyEl.parentElement : $("log");
  const card = document.createElement("div");
  card.className = "cb-doc-card";
  const tag = document.createElement("span");
  tag.className = "cb-doc-card-tag";
  tag.textContent = "交付物文书";
  card.appendChild(tag);
  for (const f of files) {
    const t = document.createElement("span");
    t.className = "cb-doc-card-t";
    t.textContent = `${f.expert || ""} · ${f.name || f.path || "文书"}`.replace(/^ · /, "");
    card.appendChild(t);
    if (isDocMd(f)) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = "文书预览";
      b.addEventListener("click", () => openDeliverable(f));
      card.appendChild(b);
    }
    const a = document.createElement("a");
    a.className = "dl";
    a.href = fileUrl(f.path);
    a.setAttribute("download", f.name || "文书.md");
    a.textContent = "下载";
    card.appendChild(a);
  }
  const k = document.createElement("span");
  k.className = "cb-doc-card-k";
  k.textContent = "AI 草稿 · 不签认";
  card.appendChild(k);
  host.appendChild(card);
  $("log").scrollTop = $("log").scrollHeight;
}

async function apiError(res) {
  const t = await res.text();
  try {
    const j = JSON.parse(t);
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) return j.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  } catch (_) {}
  return t || res.statusText;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

if ($("input")) {
  $("input").addEventListener("input", () => paintContext(estimateLocalContext()));
}

function renderAttaches() {
  const box = $("attaches");
  if (!box) return;
  box.innerHTML = "";
  for (const f of state.attachments) {
    const chip = document.createElement("span");
    chip.className = "chip";
    const kb = f.bytes != null ? fmtBytes(f.bytes) : "";
    chip.textContent = `${f.name || f.id} · ${kb}`;
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.addEventListener("click", () => {
      state.attachments = state.attachments.filter((a) => a.id !== f.id);
      renderAttaches();
    });
    chip.appendChild(x);
    box.appendChild(chip);
  }
}

async function uploadFiles(fileList) {
  const files = [...fileList];
  if (!files.length) return;
  for (const file of files) {
    const fd = new FormData();
    fd.append("session_id", state.session);
    fd.append("file", file, file.name);
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    if (!res.ok) {
      addStatus(`上传失败 ${file.name}：${await apiError(res)}`);
      continue;
    }
    const data = await res.json();
    for (const f of data.files || []) {
      if (!state.attachments.some((a) => a.id === f.id)) state.attachments.push(f);
    }
  }
  renderAttaches();
}

async function importLocalPath() {
  const path = $("localPath") ? $("localPath").value.trim() : "";
  if (!path) {
    addStatus("请填写本机完整路径。不要填 D:\\layout。");
    return;
  }
  const res = await fetch("/api/local", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.session, path }),
  });
  if (!res.ok) {
    addStatus(`导入失败：${await apiError(res)}`);
    return;
  }
  const data = await res.json();
  for (const f of data.files || []) {
    if (!state.attachments.some((a) => a.id === f.id)) state.attachments.push(f);
  }
  renderAttaches();
  addStatus(`已导入本机 ${ (data.files || []).length } 个文件，可点成套投标。`);
}

async function runFirmBid() {
  const path = $("localPath") ? $("localPath").value.trim() : "";
  const brief = $("input") ? $("input").value.trim() : "";
  addStatus("Harness steps：parse → qa → outline → price …");
  const res = await fetch("/api/firm/bid", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: state.session,
      project_name: brief.slice(0, 40) || "未命名投标项目",
      path,
      brief,
      confirm_ok: $("confirmOk") ? $("confirmOk").checked : false,
      jurisdiction: "SG",
    }),
  });
  if (!res.ok) {
    addStatus(`成套失败：${await apiError(res)}`);
    return;
  }
  const data = await res.json();
  const body = addMsg("assistant", "一人公司", "");
  const hitl = data.hitl && data.hitl.pending ? "HITL 待确认（专项未出施工草稿）" : "HITL 未挡";
  const lines = [
    `mode=${data.mode || "steps"} · run ${data.run_id || ""} · ${hitl}`,
    `${data.project || "成套"} · 作业目录 ${data.job_dir || ""}`,
    `illegal_tool_calls=${data.illegal_tool_calls ?? 0}`,
    ...((data.steps || []).map((s) => `${s.name}: ${s.tool} legal=${s.legal} ok=${s.ok}`)),
    ...(data.notes || []),
    "右侧可下载各份草稿。这不是可提交标书。",
  ];
  body.textContent = lines.join("\n");
  renderFiles(data.files || []);
  addStatus("成套已落盘。");
}

if ($("btnLocal")) $("btnLocal").addEventListener("click", () => importLocalPath().catch((e) => addStatus(String(e))));
if ($("btnFirm")) $("btnFirm").addEventListener("click", () => runFirmBid().catch((e) => addStatus(String(e))));

if ($("btnUpload") && $("filePick")) {
  $("btnUpload").addEventListener("click", () => $("filePick").click());
  $("filePick").addEventListener("change", async (ev) => {
    await uploadFiles(ev.target.files);
    ev.target.value = "";
  });
}

const composer = document.querySelector(".composer");
if (composer) {
  composer.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    composer.classList.add("drop");
  });
  composer.addEventListener("dragleave", () => composer.classList.remove("drop"));
  composer.addEventListener("drop", async (ev) => {
    ev.preventDefault();
    composer.classList.remove("drop");
    if (ev.dataTransfer && ev.dataTransfer.files.length) {
      await uploadFiles(ev.dataTransfer.files);
    }
  });
}

/* === ux(round2) 输入体验（docs/ux/ux-design-spec.md R2：一个输入框） ============
   模式借鉴 pattern-only，不抄任何代码：
   - openai/codex codex-rs/tui/src/bottom_pane/chat_composer.rs（Apache-2.0）：
     单输入框按键先路由给活动浮层；补全=替换光标处 @token、尾部留一个空格；
     Esc 关闭浮层并记住被关闭的 token，编辑后才允许重开。
   - open-webui src/lib/components/chat/MessageInput.svelte（MIT）：
     compositionstart/end IME 守卫（中文输入法回车选词不误发，Safari 时序 200ms）；
     发送按钮随内容空态禁用；textarea autosize=height:auto→scrollHeight 钳制。
   - Discord/Slack @提及（pattern-only）：↑↓ 选择、Enter/Tab 确认、Esc 关闭、悬停即选中。 */
const CB_MAX_LINES = 8;

function cbAutosize(ta) {
  // 1→8 行伸缩，超长内部滚动
  if (!ta) return;
  ta.style.height = "auto";
  const cs = getComputedStyle(ta);
  const line = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4 || 20;
  const pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const max = line * CB_MAX_LINES + pad;
  ta.style.height = Math.min(ta.scrollHeight, max) + "px";
  ta.style.overflowY = ta.scrollHeight > max ? "auto" : "hidden";
}

function cbAtQuery(text, cursor) {
  // 光标左侧 @token：行首/空白起头，@ 后可跟中文/字母/数字/连字符/下划线
  const before = String(text || "").slice(0, cursor);
  const m = before.match(/(^|\s)@([\u4e00-\u9fa5A-Za-z0-9_-]*)$/);
  if (!m) return null;
  return { start: before.length - m[2].length - 1, query: m[2] };
}

function cbAtFilter(posts, query, limit) {
  // 66 岗按 name/aliases/id 过滤：前缀命中优先于包含命中，默认最多 8 条
  const q = String(query || "").trim().toLowerCase();
  const scored = [];
  for (const p of posts || []) {
    const names = [p.name].concat(p.aliases || [], [p.id]).filter(Boolean).map((n) => String(n).toLowerCase());
    let score = -1;
    if (!q) score = 2;
    else if (names.some((n) => n.indexOf(q) === 0)) score = 0;
    else if (names.some((n) => n.includes(q))) score = 1;
    if (score >= 0) scored.push([score, p]);
  }
  scored.sort((a, b) => a[0] - b[0]);
  return scored.slice(0, limit || 8).map((x) => x[1]);
}

function cbAtApply(ta, start, post) {
  // codex token 替换模式：@token → 「@岗位名 」，光标落在尾部空格之后
  const insert = "@" + post.name + " ";
  const tail = ta.value.slice(ta.selectionEnd);
  ta.value = ta.value.slice(0, start) + insert + tail;
  const pos = start + insert.length;
  ta.focus();
  ta.setSelectionRange(pos, pos);
}

function cbComposeGuard(el) {
  // IME 守卫：组合输入中的 Enter=选词不发送；结束后 200ms 内的 Enter 也忽略
  const st = { on: false, endedAt: 0 };
  el.addEventListener("compositionstart", () => { st.on = true; });
  el.addEventListener("compositionend", () => { st.on = false; st.endedAt = Date.now(); });
  st.block = function (ev) {
    return st.on || (ev && (ev.isComposing || ev.keyCode === 229)) || Date.now() - st.endedAt < 200;
  };
  return st;
}

/* ---- :8765 实例接线：@岗位补全 + Enter 语义 + 空态禁用 ---- */
const cbAt = { open: false, items: [], idx: 0, start: -1, query: "", dismissed: "", dismissedAt: -1 };
let cbSyncSend = () => {};

function cbPostsSource() {
  return state.experts && state.experts.length ? state.experts : window.CB_POSTS || [];
}

function cbAtClose() {
  cbAt.open = false;
  const menu = $("atMenu");
  if (menu) menu.hidden = true;
}

function cbAtRender() {
  const menu = $("atMenu");
  if (!menu) return;
  menu.innerHTML = "";
  cbAt.items.forEach((p, i) => {
    const row = document.createElement("div");
    row.className = "cb-at-item" + (i === cbAt.idx ? " on" : "");
    row.setAttribute("role", "option");
    row.setAttribute("aria-selected", i === cbAt.idx ? "true" : "false");
    const name = document.createElement("span");
    name.className = "cb-at-name";
    name.textContent = "@" + p.name;
    const cat = document.createElement("span");
    cat.className = "cb-at-cat";
    cat.textContent = (p.category_name || "") + (p.id ? " · " + p.id : "");
    row.appendChild(name);
    row.appendChild(cat);
    row.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      cbAt.idx = i;
      cbAtConfirm();
    });
    row.addEventListener("mouseenter", () => {
      cbAt.idx = i;
      cbAtRender();
    });
    menu.appendChild(row);
  });
  menu.hidden = false;
}

function cbAtUpdate() {
  const ta = $("input");
  if (!ta) return cbAtClose();
  const tok = cbAtQuery(ta.value, ta.selectionStart);
  if (!tok || (cbAt.dismissed === tok.query && cbAt.dismissedAt === tok.start)) return cbAtClose();
  const items = cbAtFilter(cbPostsSource(), tok.query);
  if (!items.length) return cbAtClose();
  cbAt.open = true;
  cbAt.items = items;
  cbAt.idx = 0;
  cbAt.start = tok.start;
  cbAt.query = tok.query;
  cbAtRender();
}

function cbAtConfirm() {
  const ta = $("input");
  const post = cbAt.items[cbAt.idx];
  cbAtClose();
  if (!ta || !post) return;
  cbAtApply(ta, cbAt.start, post);
  cbAutosize(ta);
  cbSyncSend();
}

function cbAtMove(d) {
  if (!cbAt.items.length) return;
  cbAt.idx = (cbAt.idx + d + cbAt.items.length) % cbAt.items.length;
  cbAtRender();
}

function cbComposerInit() {
  const ta = $("input");
  const form = $("form");
  if (!ta || !form) return;
  const guard = cbComposeGuard(ta);
  cbSyncSend = () => {
    const btn = $("send");
    if (btn && !btn.dataset.running) btn.disabled = !ta.value.trim();
  };
  ta.addEventListener("input", () => {
    cbAutosize(ta);
    cbSyncSend();
    cbAtUpdate();
  });
  ta.addEventListener("keydown", (ev) => {
    if (cbAt.open) {
      if (ev.key === "ArrowDown") { ev.preventDefault(); cbAtMove(1); return; }
      if (ev.key === "ArrowUp") { ev.preventDefault(); cbAtMove(-1); return; }
      if (ev.key === "Enter" || ev.key === "Tab") { ev.preventDefault(); cbAtConfirm(); return; }
      if (ev.key === "Escape") {
        ev.preventDefault();
        cbAt.dismissed = cbAt.query;
        cbAt.dismissedAt = cbAt.start;
        cbAtClose();
        return;
      }
    }
    const send = ev.key === "Enter" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey && !guard.block(ev);
    if (send) {
      ev.preventDefault();
      if (form.requestSubmit) form.requestSubmit();
      else form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });
  cbAutosize(ta);
  cbSyncSend();
}
cbComposerInit();

boot();

/* === ux(round3) 阶段时间线 · 一条流水线（进度可见）· docs/ux/ux-design-spec.md 附录 B ===
   8 阶段轨道：理解任务→召唤岗位→成箱→人工确认→拼柜→合规校核→落盘→收口。
   事件→阶段映射（SSE event=status.phase，按 workbench/src/api.rs + agent.rs 实际事件名）：
   understand/compress/import→理解任务 · summon/queue/plain→召唤岗位 · harness/scheme_gate→成箱
   hitl_gate/confirm→人工确认 · plan_load_eval/pack→拼柜 · risk→合规校核 · price/deliver→落盘 · done→收口。
   未列出的工具名 phase（search_kb/read_kb/web_search 等）→ 附在当前阶段子行，不进「未知」桶。
   借鉴 pattern-only：aider waiting.Spinner（Apache-2.0）单行进行中+降级渲染；
   openai/codex history_cell（Apache-2.0）追加式会话流、完成后折叠为一行摘要；
   VS Code Tasks presentation（文档 pattern-only）长输出默认折叠、可展开。 */
const CB_TL_STAGES = [
  ["understand", "理解任务"],
  ["summon", "召唤岗位"],
  ["box", "成箱"],
  ["hitl", "人工确认"],
  ["pack", "拼柜"],
  ["risk", "合规校核"],
  ["write", "落盘"],
  ["finalize", "收口"],
];
/* ux(round5) 全局 Esc=驳回永不放行：等待中的审批卡登记于此（Codex approval_overlay 契约） */
const CB_APR_WAITING = new Set();
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape" || !CB_APR_WAITING.size) return;
  const cards = [...CB_APR_WAITING];
  const card = cards[cards.length - 1];
  if (card && typeof card.onEsc === "function") {
    ev.preventDefault();
    card.onEsc();
  }
});
const CB_PHASE_STAGE = {
  understand: "understand",
  compress: "understand",
  import: "understand",
  summon: "summon",
  queue: "summon",
  plain: "summon",
  harness: "box",
  scheme_gate: "box",
  scheme: "box",
  hitl_gate: "hitl",
  hitl: "hitl",
  confirm: "hitl",
  plan_load_eval: "pack",
  pack: "pack",
  risk: "risk",
  exclusive: "write",
  write: "write",
  price: "write",
  doc: "write",
  deliver: "write",
  done: "finalize",
};

function cbTlCreate(bodyEl, sourceMessage) {
  const STAGE_ORDER = CB_TL_STAGES.map((s) => s[0]);
  const stages = {};
  for (const [key, label] of CB_TL_STAGES) stages[key] = { state: "idle", label, note: "" };
  let activeKey = "";
  let hitlWait = false;
  let doneFolded = false;

  const root = document.createElement("div");
  root.className = "cb-tl";
  root.setAttribute("data-cb-timeline", "true");
  root.innerHTML =
    '<div class="cb-tl-head"><span class="cb-tl-title">阶段时间线</span>' +
    '<span class="cb-tl-badge tl-badge"></span>' +
    '<button type="button" class="cb-tl-fold" hidden>展开时间线</button></div>' +
    '<div class="cb-tl-summary tl-summary" hidden></div>' +
    '<div class="cb-tl-track"></div>' +
    '<div class="cb-tl-hitl tl-hitl" data-r5-approval-slot="true" hidden></div>' +
    '<div class="cb-tl-lines tl-lines"></div>' +
    '<div class="cb-tl-audit tl-audit" data-cb-audit="true" hidden></div>';
  const badge = root.querySelector(".tl-badge");
  const foldBtn = root.querySelector(".cb-tl-fold");
  const summaryEl = root.querySelector(".tl-summary");
  const trackEl = root.querySelector(".cb-tl-track");
  const hitlEl = root.querySelector(".tl-hitl");
  const linesEl = root.querySelector(".tl-lines");
  const auditEl = root.querySelector(".tl-audit");

  const chips = [];
  for (const [key, label] of CB_TL_STAGES) {
    if (chips.length) {
      const arrow = document.createElement("span");
      arrow.className = "cb-tl-arrow";
      arrow.textContent = "→";
      arrow.setAttribute("aria-hidden", "true");
      trackEl.appendChild(arrow);
    }
    const chip = document.createElement("span");
    chip.className = "cb-tl-stage idle";
    chip.setAttribute("data-cb-stage", key);
    chip.innerHTML = '<span class="cb-tl-st">·</span>' + label;
    chip.title = label;
    trackEl.appendChild(chip);
    stages[key].el = chip;
  }

  function paintStage(key) {
    const st = stages[key];
    if (!st || !st.el) return;
    st.el.className = "cb-tl-stage " + st.state;
    if (st.state === "run") {
      st.el.innerHTML = '<span class="cb-tl-spin" aria-hidden="true"></span>' + st.label;
    } else {
      const icon = st.state === "done" ? "✓" : st.state === "warn" ? "⚠" : st.state === "err" ? "⛔" : "·";
      st.el.innerHTML = '<span class="cb-tl-st">' + icon + "</span>" + st.label;
    }
  }

  function setStage(key, stateName, note) {
    const st = stages[key];
    if (!st) return;
    if (st.state === "run" && stateName === "run") return;
    if (st.state === "done" && stateName === "run") st.note = "打回重做";
    st.state = stateName;
    if (note) st.note = String(note).slice(0, 200);
    paintStage(key);
  }

  function settleActive() {
    if (activeKey && stages[activeKey] && stages[activeKey].state === "run") {
      stages[activeKey].state = "done";
      paintStage(activeKey);
    }
  }

  function addLine(stageKey, tool, text, status) {
    const row = document.createElement("div");
    row.className = "cb-tl-line is-" + (status === "running" ? "running" : status === "error" ? "err" : status === "warn" ? "warn" : "ok");
    row.setAttribute("data-cb-stage", stageKey || activeKey || "understand");
    const t = String(text || "");
    const toolEl = document.createElement("span");
    toolEl.className = "tl-tool";
    toolEl.textContent = tool || "·";
    const textEl = document.createElement("span");
    textEl.className = "tl-text";
    textEl.textContent = t.length > 96 ? t.slice(0, 96) + "…" : t;
    row.appendChild(toolEl);
    row.appendChild(textEl);
    if (t.length > 96) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "cb-tl-more";
      more.textContent = "展开";
      let open = false;
      more.addEventListener("click", () => {
        open = !open;
        textEl.textContent = open ? t : t.slice(0, 96) + "…";
        more.textContent = open ? "收起" : "展开";
      });
      row.appendChild(more);
    }
    linesEl.appendChild(row);
    linesEl.scrollTop = linesEl.scrollHeight;
  }

  function setBadge(text, cls) {
    badge.textContent = text || "";
    badge.className = "cb-tl-badge tl-badge" + (cls ? " " + cls : "");
  }

  /* ===== ux(round5) HITL 审批卡（docs/ux/ux-design-spec.md 附录 D）=====
     显式决策事件 + Esc/关闭=驳回永不放行 + 决策写审计行。卡片只抄事件字段（gate/expert/run_id），不编数字。 */
  function aprNow() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }

  function aprAudit(decision, reason) {
    const rowEl = document.createElement("div");
    rowEl.className = "cb-tl-audit-row";
    rowEl.textContent = "审计 · " + decision + (reason ? "（" + reason + "）" : "") + " · " + aprNow() + " · 操作者=本地用户 · 未静默放行";
    auditEl.appendChild(rowEl);
    auditEl.hidden = false;
  }

  function addAuditRow(text) {
    aprAudit(text, "");
  }

  function gateLabel(gate) {
    if (gate === "scheme") return "成箱方案闸门（scheme）";
    if (gate === "exclusive_write") return "高风险写盘闸门（exclusive_write）";
    return gate ? "闸门 " + gate : "HITL 闸门";
  }

  function mountApproval(info) {
    if (!hitlEl) return;
    const state = { decided: "", open: true };
    hitlEl.hidden = false;
    hitlEl.textContent = "";
    const card = document.createElement("div");
    card.className = "cb-apr";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", "HITL 人工确认审批卡");
    card.setAttribute("data-cb-approval", "true");
    card.innerHTML =
      '<div class="cb-apr-bar" aria-hidden="true"></div>' +
      '<div class="cb-apr-head">' +
      '<span class="cb-apr-title">人工确认 · ' + gateLabel(info.gate) + "</span>" +
      '<span class="cb-apr-risk is-high">风险 · 高</span>' +
      '<span class="cb-apr-state apr-state" hidden></span>' +
      '<button type="button" class="cb-apr-x" title="关闭 = 驳回，永不放行" aria-label="关闭审批卡（等同驳回，不放行）">✕</button>' +
      "</div>" +
      '<div class="cb-apr-body apr-waiting">' +
      '<div class="cb-apr-chips" data-cb-approval-summary="true">' +
      (info.expert ? '<span class="cb-apr-chip">岗位 <b>' + escapeHtml(String(info.expert)) + "</b></span>" : "") +
      (info.runId ? '<span class="cb-apr-chip">run <b>' + escapeHtml(String(info.runId)) + "</b></span>" : "") +
      '<span class="cb-apr-chip is-warn">签认 <b>未确认</b> · 本岗未出稿</span>' +
      "</div>" +
      '<div class="cb-apr-block" data-cb-approval-blockers="true">高风险动作须人工确认后才会写盘/出稿；流程层已强制 confirm_ok 门禁（未确认不出施工草稿）。</div>' +
      '<div class="cb-apr-actions" data-cb-approval-actions="true">' +
      '<button type="button" class="cb-apr-confirm">确认并重提</button>' +
      '<button type="button" class="cb-apr-reject">驳回</button>' +
      '<button type="button" class="cb-apr-later">稍后</button>' +
      "</div>" +
      '<div class="cb-apr-foot">确认 = 勾选确认句「我明白，将由持证人员签认」并重新提交本条任务 · ' +
      "<b>Esc、关闭 = 驳回，永不放行</b> · 决策写入下方审计行</div>" +
      "</div>" +
      '<div class="cb-apr-body apr-decided" hidden></div>';
    const stateChip = card.querySelector(".apr-state");
    const waitingBody = card.querySelector(".apr-waiting");
    const decidedBody = card.querySelector(".apr-decided");

    function settle(kind, reason) {
      if (state.decided) return;
      state.decided = kind;
      CB_APR_WAITING.delete(api);
      waitingBody.hidden = true;
      decidedBody.hidden = false;
      decidedBody.innerHTML = "";
      card.querySelector(".cb-apr-x").hidden = true;
      if (kind === "approved") {
        card.classList.add("is-approved");
        stateChip.hidden = false;
        stateChip.textContent = "已确认 · 已重新提交";
        setStage("hitl", "done", "已确认 · 已重新提交（续跑见新时间线）");
        addLine("hitl", "hitl.confirm", "用户确认 · 勾选签认句并重新提交", "ok");
        decidedBody.textContent = "已确认 · 已重新提交本条任务（confirm_ok=true）。本时间线定格为历史，续跑进度见新时间线。";
      } else {
        card.classList.add("is-rejected");
        stateChip.hidden = false;
        stateChip.classList.add("is-rejected");
        stateChip.textContent = "已驳回 · 未放行";
        setStage("hitl", "warn", "已驳回（未放行）· 请修改输入后重跑");
        addLine("hitl", "hitl.reject", "用户驳回（" + (reason || "") + "）· 未放行 · 未出稿", "warn");
        const note = document.createElement("div");
        note.className = "cb-apr-reject-note";
        note.textContent = "⚠ 已驳回（" + (reason || "驳回") + "）· 未放行，未出任何稿 · 请修改输入后重跑（补齐数据 / 更换岗位 / 调整任务描述）";
        decidedBody.appendChild(note);
      }
      aprAudit(kind === "approved" ? "确认 · 已重新提交" : "驳回 · 未放行", reason);
    }

    card.querySelector(".cb-apr-confirm").addEventListener("click", () => {
      /* 显式决策=确认：勾选确认句（流程层 confirm_ok 门禁）并重新提交原文 */
      const ok = $("confirmOk");
      if (ok) ok.checked = true;
      const input = $("input");
      const form = $("form");
      if (input && form && sourceMessage) {
        input.value = sourceMessage;
        if (form.requestSubmit) form.requestSubmit();
        else form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
      settle("approved", "");
    });
    card.querySelector(".cb-apr-reject").addEventListener("click", () => settle("rejected", "驳回按钮"));
    card.querySelector(".cb-apr-x").addEventListener("click", () => settle("rejected", "Esc/关闭"));
    card.querySelector(".cb-apr-later").addEventListener("click", () => {
      /* 稍后=折叠卡片继续等待；不做决策、不放行 */
      state.open = false;
      card.hidden = true;
      openSlot.hidden = false;
    });
    const api = { settle };
    api.onEsc = () => {
      if (state.open && !state.decided) settle("rejected", "Esc/关闭");
    };
    CB_APR_WAITING.delete(api);
    CB_APR_WAITING.add(api);

    /* 稍后折叠条：点击重新展开（仍等待，未放行） */
    const openSlot = document.createElement("div");
    openSlot.className = "cb-apr-open-slot";
    openSlot.setAttribute("role", "button");
    openSlot.tabIndex = 0;
    openSlot.hidden = true;
    openSlot.textContent = "等待人工确认 · 点此展开审批卡（确认 / 驳回须显式点击；Esc、关闭 = 驳回，永不放行）";
    const reopen = () => {
      if (state.decided) return;
      state.open = true;
      openSlot.hidden = true;
      card.hidden = false;
    };
    openSlot.addEventListener("click", reopen);
    openSlot.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); reopen(); }
    });

    hitlEl.appendChild(card);
    hitlEl.appendChild(openSlot);
    const log = $("log");
    if (log) log.scrollTop = log.scrollHeight;
    return api;
  }

  function finish(data) {
    settleActive();
    const hitlPending = !!(data && data.hitl && data.hitl.pending);
    if (hitlPending) {
      /* HITL 闸门未过：运行已结束但未出稿——时间线不定格为「完成」，审批卡保持等待 */
      if (activeKey && stages[activeKey] && stages[activeKey].state === "run") {
        stages[activeKey].state = "done";
        paintStage(activeKey);
      }
      setStage("hitl", "warn", "等待人工确认（闸门未过，本岗未出稿）");
      setBadge("HITL 等待中", "hitl");
      hitlEl.hidden = false;
      if (!hitlEl.querySelector(".cb-apr")) {
        mountApproval({ gate: (data.hitl || {}).gate, expert: (data && data.expert) || "", runId: (data && data.run_id) || "" });
      }
      return;
    }
    setStage("finalize", "done", "收口完成");
    if (hitlWait) hitlWait = false;
    hitlEl.hidden = true;
    setBadge("完成", "");
    doneFolded = true;
    /* 摘要数字只抄事件（deliverables / mode），不编造 */
    const files = Array.isArray(data && data.deliverables) ? data.deliverables : [];
    const head = document.createElement("span");
    head.textContent = "完成 · " + ((data && data.mode) === "firm" ? "一人公司成套" : (data && data.mode) === "expert" ? "岗位收工" : "回答完毕") + (files.length ? " · 文书 " + files.length + " 份" : "");
    summaryEl.textContent = "";
    summaryEl.appendChild(head);
    for (const f of files) {
      const chip = document.createElement("span");
      chip.className = "cb-tl-chip";
      chip.textContent = (f.name || f.title || String(f.path || "").split("/").pop() || "文书").slice(0, 24);
      summaryEl.appendChild(chip);
    }
    summaryEl.hidden = false;
    trackEl.hidden = true;
    linesEl.hidden = true;
    foldBtn.hidden = false;
    foldBtn.textContent = "展开时间线";
    foldBtn.onclick = () => {
      doneFolded = !doneFolded;
      trackEl.hidden = doneFolded;
      linesEl.hidden = doneFolded;
      summaryEl.hidden = !doneFolded;
      foldBtn.textContent = doneFolded ? "展开时间线" : "折叠为一行摘要";
    };
  }

  function status(data) {
    const phase = String((data && data.phase) || "");
    const text = String((data && data.text) || "");
    const stageKey = CB_PHASE_STAGE[phase] || "";
    if (stageKey === "hitl") {
      settleActive();
      setStage("hitl", "run", text || "等待人工确认（HITL 闸门）");
      activeKey = "hitl";
      hitlWait = true;
      setBadge("HITL 等待中", "hitl");
    } else if (stageKey) {
      settleActive();
      setStage(stageKey, "run", text || phase);
      activeKey = stageKey;
      setBadge(stageLabel(stageKey), "");
    } else {
      /* 工具名 phase / think 等未映射事件 → 当前阶段子行，不落「未知」
         （Rust 侧 status 事件=该动作已完成并带结果文本，故标 ok 不挂 running） */
      addLine(activeKey || "understand", phase, text || phase, "ok");
      return;
    }
    if (text) addLine(stageKey || activeKey, phase, text, "ok");
  }

  function stageLabel(key) {
    const found = CB_TL_STAGES.find((s) => s[0] === key);
    return found ? found[1] : key;
  }

  function error(text) {
    const key = activeKey || "finalize";
    setStage(key, "warn", String(text).slice(0, 200));
    addLine(key, "error", text, "error");
    setBadge("受阻 · 见子行", "hitl");
  }

  /* 挂载：插到本条助手消息上方（追加式会话流中的一格，完成后折叠定格） */
  const msgBox = bodyEl && bodyEl.parentElement;
  if (msgBox && msgBox.parentElement) msgBox.parentElement.insertBefore(root, msgBox);
  else if (msgBox) msgBox.insertBefore(root, bodyEl);
  const log = $("log");
  if (log) log.scrollTop = log.scrollHeight;

  return { status, error, finish, root };
}

/* ===== ux(round6) 跨运行审计时间线（docs/ux 附录 E）=====
   数据源 GET /api/harness/audit/<session>（只读聚合 demo/out/<session>/runs/*/trace.json）。
   节点四色：工具执行=蓝 · 人工决策=合规红 · 错误/重试=橙 · 写盘=绿；决策节点永久置顶不可折叠。 */
let auditTimer = 0;
let auditLast = null;
const AUDIT_KIND_LABEL = { run: "运行", tool: "工具", decision: "决策", error: "错误", write: "写盘" };

function auditNodeEl(n, ts) {
  const row = document.createElement("div");
  row.className = "cb-audit-node is-" + (n.kind || "tool");
  const dot = document.createElement("span");
  dot.className = "cb-audit-dot";
  dot.setAttribute("aria-hidden", "true");
  const k = document.createElement("span");
  k.className = "cb-audit-k";
  k.textContent = AUDIT_KIND_LABEL[n.kind] || n.kind || "·";
  const t = document.createElement("span");
  t.className = "cb-audit-t";
  t.textContent = String(n.title || "") + (n.detail ? " · " + n.detail : "");
  row.append(dot, k, t);
  if (ts) {
    const time = document.createElement("span");
    time.className = "cb-audit-time";
    time.textContent = String(ts);
    row.append(time);
  }
  if (n.operator) {
    const op = document.createElement("span");
    op.className = "cb-audit-op";
    op.textContent = String(n.operator) + " · 未静默放行";
    row.append(op);
  }
  if (n.raw != null) {
    const det = document.createElement("details");
    det.className = "cb-audit-raw";
    const sum = document.createElement("summary");
    sum.textContent = "原始";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(n.raw, null, 2);
    det.append(sum, pre);
    row.append(det);
  }
  return row;
}

async function loadAuditPanel() {
  const body = $("auditBody");
  if (!body) return;
  body.innerHTML = '<p class="cb-audit-none">加载中…</p>';
  const res = await fetch(`/api/harness/audit/${encodeURIComponent(state.session)}`);
  let j;
  try {
    j = await res.json();
  } catch (_) {
    j = {};
  }
  if (!res.ok || j.ok === false) {
    throw new Error(j.detail || j.error || "HTTP " + res.status);
  }
  auditLast = j;
  body.textContent = "";
  const head = document.createElement("p");
  head.className = "cb-audit-none";
  const c = j.counts || {};
  head.textContent = `session ${j.session_id} · ${c.runs || 0} run · 决策 ${c.decisions || 0} · 工具 ${c.tools || 0} · 写盘 ${c.writes || 0} · 错误 ${c.errors || 0}`;
  body.append(head);
  /* 决策节点：永久置顶，不可折叠（confirm/reject/waiting 全留痕） */
  const pin = document.createElement("div");
  pin.className = "cb-audit-pinned";
  const pinH = document.createElement("div");
  pinH.className = "cb-audit-pinned-h";
  pinH.textContent = "人工决策（永久置顶 · 不可折叠 · 操作者=本地用户）";
  pin.append(pinH);
  const decisions = j.decisions || [];
  if (!decisions.length) {
    const none = document.createElement("p");
    none.className = "cb-audit-none";
    none.textContent = "本会话无人工决策记录（未触发 HITL 闸门或未走到审批）";
    pin.append(none);
  } else {
    for (const d of decisions) {
      pin.append(auditNodeEl({ kind: "decision", title: d.title, detail: d.detail, operator: d.operator }, d.ts));
    }
  }
  body.append(pin);
  for (const run of [...(j.runs || [])].reverse()) {
    const box = document.createElement("div");
    box.className = "cb-audit-run";
    const h = document.createElement("div");
    h.className = "cb-audit-run-h";
    const rid = document.createElement("span");
    rid.className = "cb-audit-runid";
    rid.textContent = run.run_id || "";
    const tm = document.createElement("span");
    tm.className = "cb-audit-time";
    tm.textContent = run.mtime || "";
    h.append(rid, tm);
    box.append(h);
    for (const n of run.nodes || []) box.append(auditNodeEl(n, ""));
    body.append(box);
  }
  if ($("auditCopy")) $("auditCopy").hidden = false;
  if ($("auditDownload")) $("auditDownload").hidden = false;
}

function refreshAuditSoon() {
  clearTimeout(auditTimer);
  auditTimer = setTimeout(() => {
    loadAuditPanel().catch(() => {});
  }, 800);
}

function auditExportPayload() {
  return {
    schema: (auditLast && auditLast.schema) || "civil.audit.v1",
    exported_at: new Date().toISOString(),
    product: "Civil Buddy · 人机协同履历（AI 做了什么、人批了什么）",
    session_id: (auditLast && auditLast.session_id) || state.session,
    counts: (auditLast && auditLast.counts) || {},
    decisions: (auditLast && auditLast.decisions) || [],
    runs: (auditLast && auditLast.runs) || [],
  };
}

if ($("loadAudit")) {
  $("loadAudit").addEventListener("click", () => loadAuditPanel().catch((e) => addStatus("审计加载失败：" + String(e.message || e))));
}
if ($("auditCopy")) {
  $("auditCopy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(auditExportPayload(), null, 2));
      addStatus("审计 JSON 已复制到剪贴板");
    } catch (_) {
      addStatus("复制失败（浏览器限制），请改用下载 JSON");
    }
  });
}
if ($("auditDownload")) {
  $("auditDownload").addEventListener("click", () => {
    const text = JSON.stringify(auditExportPayload(), null, 2);
    const fname = "audit-" + String((auditLast && auditLast.session_id) || state.session).replace(/[^A-Za-z0-9._-]+/g, "_") + ".json";
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 400);
    addStatus("审计 JSON 已下载：" + fname);
  });
}
