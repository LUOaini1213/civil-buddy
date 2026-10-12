(() => {
  /* 中文 | English (/static/i18n.js); without it, the Chinese message as written, {0} {1} … filled. */
  function tr(message) {
    var args = Array.prototype.slice.call(arguments, 1);
    var i18n = (typeof window !== "undefined" ? window : globalThis).CB_I18N;
    if (i18n && typeof i18n.t === "function") return i18n.t.apply(i18n, arguments);
    return String(message).replace(/\{(\d+)\}/g, function (whole, i) {
      i = Number(i);
      return i < args.length ? (args[i] == null ? "" : String(args[i])) : whole;
    });
  }

  const $ = (id) => document.getElementById(id);
  let tree = null;
  let currentPath = "";
  let dirty = false;
  let selectedExpert = "";

  async function apiError(res) {
    const t = await res.text();
    try {
      const j = JSON.parse(t);
      if (typeof j.detail === "string") return j.detail;
      if (Array.isArray(j.detail)) return j.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    } catch (_) {}
    return t || res.statusText;
  }

  $("openStudio").addEventListener("click", () => openStudio());
  $("closeStudio").addEventListener("click", () => closeStudio());

  window.openStudio = async (path, expertId) => {
    $("studio").classList.remove("hidden");
    $("studio").setAttribute("aria-hidden", "false");
    await loadTree();
    if (expertId) fillExpert(expertId);
    if (path) await openFile(path);
  };

  window.studioOnCatalog = (cat) => {
    fillCatSelect(cat);
    if ($("softLimit") && cat.kb_soft_limit_kb) $("softLimit").value = cat.kb_soft_limit_kb;
  };

  function closeStudio() {
    if (dirty && !confirm(tr("文件未保存，确定离开？"))) return;
    $("studio").classList.add("hidden");
    $("studio").setAttribute("aria-hidden", "true");
    if (window.reloadCatalog) window.reloadCatalog();
  }

  async function loadTree() {
    tree = await fetch("/api/studio/tree").then((r) => r.json());
    $("studioTotal").textContent = tr("总库 {0} · 软上限 {1} KB / 本岗知识", tree.total_label, tree.kb_soft_limit_kb);
    $("softLimit").value = tree.kb_soft_limit_kb;
    fillCatSelect({ categories: tree.categories });
    renderTree();
  }

  function fillCatSelect(cat) {
    const sel = $("expCat");
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = "";
    for (const c of cat.categories || []) {
      const o = document.createElement("option");
      o.value = c.id;
      o.textContent = c.name;
      o.title = c.id;
      sel.appendChild(o);
    }
    if (cur) sel.value = cur;
  }

  function renderTree() {
    const box = $("studioTree");
    box.innerHTML = "";
    box.appendChild(heading(tr("公司规则（所有专家都能读）")));
    for (const f of tree.company.files || []) box.appendChild(fileBtn(f));

    for (const cat of tree.categories) {
      box.appendChild(heading(tr("{0} · 大类共享 {1}", cat.name, cat.shared.label)));
      for (const f of cat.shared.files || []) box.appendChild(fileBtn(f));
      for (const exp of cat.experts) {
        const mark = exp.over_limit ? " over" : "";
        const h = document.createElement("button");
        h.type = "button";
        h.className = `tree-item${mark}`;
        h.textContent = tr("{0} · 本岗知识 {1} · {2} 篇", exp.name, exp.label, exp.count);
        h.addEventListener("click", () => fillExpert(exp.id));
        box.appendChild(h);
        for (const f of exp.files || []) box.appendChild(fileBtn(f, exp.id));
      }
    }
  }

  function heading(text) {
    const d = document.createElement("div");
    d.className = "tree-h";
    d.textContent = text;
    return d;
  }

  function fmtBytes(n) {
    const x = Number(n) || 0;
    if (x < 1024) return `${x} B`;
    if (x < 1024 * 1024) return `${(x / 1024).toFixed(1)} KB`;
    return `${(x / (1024 * 1024)).toFixed(2)} MB`;
  }

  function fileBtn(f, expertId) {
    const path = f.path || "";
    const name = f.display || f.title || path.split("/").pop() || path;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tree-item" + (path === currentPath ? " on" : "");
    b.textContent = tr("{0} · {1} · {2} 字", name, fmtBytes(f.bytes), f.chars || 0);
    b.title = path;
    b.addEventListener("click", () => {
      if (expertId) fillExpert(expertId);
      openFile(path);
    });
    return b;
  }

  function findExpert(id) {
    if (!tree) return null;
    for (const c of tree.categories) {
      const hit = (c.experts || []).find((e) => e.id === id);
      if (hit) return { ...hit, category: c.id };
    }
    return null;
  }

  function fillExpert(id) {
    const exp = findExpert(id);
    if (!exp) return;
    selectedExpert = id;
    const form = $("expertForm");
    form.id.value = exp.id;
    form.name.value = exp.name;
    form.category.value = exp.category;
    form.risk.value = exp.risk || "low";
    form.title.value = exp.title || "";
    form.delivers.value = exp.delivers || "";
    form.aliases.value = (exp.aliases || []).join(", ");
    form.id.readOnly = Boolean(exp.builtin);
  }

  async function openFile(path) {
    if (dirty && !confirm(tr("当前编辑未保存，丢弃吗？"))) return;
    const res = await fetch(`/api/studio/file?path=${encodeURIComponent(path)}`);
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    const data = await res.json();
    currentPath = data.path;
    $("editor").value = data.content;
    const shown = data.display || data.title || data.path;
    $("filePath").textContent = data.display && data.path !== shown ? `${shown}  ·  ${data.path}` : data.path;
    $("fileSize").textContent = tr("{0} 字节 · {1} 字 · {2} 行", data.bytes, data.chars, data.lines);
    $("saveFile").disabled = false;
    dirty = false;
    renderTree();
  }

  $("editor").addEventListener("input", () => {
    dirty = true;
    const t = $("editor").value;
    $("fileSize").textContent = tr("{0} 字节（未保存） · {1} 字", new Blob([t]).size, t.length);
  });

  $("saveFile").addEventListener("click", async () => {
    if (!currentPath) return;
    const res = await fetch("/api/studio/file", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: currentPath, content: $("editor").value }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(typeof data.detail === "string" ? data.detail : tr("保存失败"));
      return;
    }
    dirty = false;
    $("fileSize").textContent = tr("{0} 字节 · {1} 字 · 已保存", data.bytes, data.chars);
    await loadTree();
  });

  $("btnNewFile").addEventListener("click", async () => {
    const base = guessDir();
    const name = prompt(tr("新文件名（.md 或 .txt）"), "notes.md");
    if (!name) return;
    const path = `${base}/${name}`.replaceAll("//", "/");
    const res = await fetch("/api/studio/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    await loadTree();
    await openFile(path);
  });

  $("btnDelFile").addEventListener("click", async () => {
    if (!currentPath) return;
    if (!confirm(tr("删除 {0}？", currentPath))) return;
    const res = await fetch(`/api/studio/file?path=${encodeURIComponent(currentPath)}`, { method: "DELETE" });
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    currentPath = "";
    $("editor").value = "";
    $("filePath").textContent = tr("未打开文件");
    $("saveFile").disabled = true;
    dirty = false;
    await loadTree();
  });

  function guessDir() {
    if (currentPath && currentPath.includes("/")) return currentPath.split("/").slice(0, -1).join("/");
    if (selectedExpert) {
      const exp = findExpert(selectedExpert);
      if (exp) return `${exp.category}/${exp.id}`;
    }
    return "company";
  }

  $("expertForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const body = {
      id: f.id.value.trim(),
      name: f.name.value.trim(),
      category: f.category.value,
      title: f.title.value.trim(),
      delivers: f.delivers.value.trim(),
      risk: f.risk.value,
      aliases: f.aliases.value.trim(),
    };
    const res = await fetch("/api/studio/experts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    selectedExpert = body.id;
    await loadTree();
    if (window.reloadCatalog) window.reloadCatalog();
    alert(tr("专家已保存。左侧对话墙会立刻出现。"));
  });

  $("btnDelExp").addEventListener("click", async () => {
    const id = $("expertForm").id.value.trim();
    if (!id) return;
    const exp = findExpert(id);
    const msg = exp && exp.builtin ? tr("内置专家 {0} 将从召唤墙隐藏（可再保存恢复）。", id) : tr("删除自定义专家 {0} 及其本岗知识？", id);
    if (!confirm(msg)) return;
    const res = await fetch(`/api/studio/experts/${encodeURIComponent(id)}?delete_kb=true`, { method: "DELETE" });
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    selectedExpert = "";
    await loadTree();
    if (window.reloadCatalog) window.reloadCatalog();
  });

  $("btnNewCat").addEventListener("click", async () => {
    const id = prompt(tr("大类 id（英文，如 lab）"));
    if (!id) return;
    const name = prompt(tr("大类中文名"), id);
    if (!name) return;
    const res = await fetch("/api/studio/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, name, blurb: "" }),
    });
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    await loadTree();
  });

  $("btnNewExp").addEventListener("click", () => {
    const f = $("expertForm");
    f.id.readOnly = false;
    f.reset();
    selectedExpert = "";
    f.id.focus();
  });

  $("saveLimit").addEventListener("click", async () => {
    const kb = Number($("softLimit").value);
    const res = await fetch("/api/studio/limit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kb_soft_limit_kb: kb }),
    });
    if (!res.ok) {
      alert(await apiError(res));
      return;
    }
    await loadTree();
  });
})();
