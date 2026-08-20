const state = {
  experts: [],
  catalog: null,
  summoned: new Set(),
  history: [],
  session: crypto.randomUUID().slice(0, 12),
  modelName: "",
  attachments: [],
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
  wall.innerHTML = "";
  for (const c of cat.categories) {
    const h = document.createElement("div");
    h.className = "cat";
    h.textContent = c.name;
    wall.appendChild(h);
    for (const e of cat.experts.filter((x) => x.category === c.id)) {
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
    ? `当前召唤：<em>${names.join(" · ")}</em>（先理解 · 能聊能跑 · 各自独立收工）`
    : "当前：<em>未召唤 · 普通对话</em>（点左侧专家才能按岗位库聊或出稿）";
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
  addMsg("user", "你", message);
  state.history.push({ role: "user", content: message });
  paintContext(estimateLocalContext());
  const bodyEl = addMsg("assistant", namesOrPlain(), "");
  $("send").disabled = true;
  try {
    await streamChat(message, bodyEl);
  } catch (err) {
    bodyEl.classList.add("err");
    bodyEl.textContent = String(err.message || err);
  } finally {
    $("send").disabled = false;
  }
});

function namesOrPlain() {
  if (!state.summoned.size) return state.modelName || "模型";
  return [...state.summoned]
    .map((id) => state.experts.find((e) => e.id === id)?.name || id)
    .join(" / ");
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
        addStatus(data.text || "");
        if (data.phase === "summon" && acc) {
          state.history.push({ role: "assistant", content: acc });
          acc = "";
          bodyEl = addMsg("assistant", data.expert || "专家", "");
        }
      }
      if (eventName === "token") {
        acc += data.text || "";
        bodyEl.textContent = acc;
        $("log").scrollTop = $("log").scrollHeight;
      }
      if (eventName === "error") throw new Error(data.text || "error");
      if (eventName === "done") {
        acc = data.text || acc;
        bodyEl.textContent = acc;
        if (acc) state.history.push({ role: "assistant", content: acc });
        if (data.context) paintContext(data.context);
        else paintContext(estimateLocalContext());
        renderCites(data.citations || []);
        renderFiles(data.deliverables || []);
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
    a.href = `/api/file?path=${encodeURIComponent(f.path)}`;
    a.textContent = `${f.expert} · ${f.name}`;
    li.appendChild(a);
    box.prepend(li);
  }
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

boot();
