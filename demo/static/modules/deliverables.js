/* Deliverables on the page: download links without server paths, the card under an
 * answer (one row per document with its md / docx / xlsx, a zip for a multi-file run), and
 * the preview. Pure helpers are exported for tests; the DOM side is a factory:
 *   state       { session }
 *   capability  (name) => true | false | undefined   (file_ref decides the link form)
 *   obStep      (n)                                  onboarding step ticks
 *   addStatus   (text)
 *   openDoc     async ({url, title, role})           the preview modal (docpreview.js)
 *   relTime     (unixSeconds) => "3 分钟前"
 *   log         () => the conversation log element
 *   doc         document
 */
import { tr, cbLang } from "./i18n.js";
export function docStem(name) {
  return String(name || "").replace(/\.(md|markdown|docx|xlsx|csv|pdf|txt|json)$/i, "");
}

export function docExt(name) {
  const m = /\.([A-Za-z0-9]+)$/.exec(String(name || ""));
  return m ? m[1].toLowerCase() : "";
}

export function groupDeliverables(files) {
  const rows = new Map();
  for (const f of files || []) {
    if (!f || typeof f.path !== "string" || !f.path) continue;
    const key = `${f.run_id || ""}|${docStem(f.name || f.path)}`;
    if (!rows.has(key)) rows.set(key, { stem: docStem(f.name || f.path), expert: f.expert || "", run_id: f.run_id || "", formats: [] });
    rows.get(key).formats.push(f);
  }
  for (const row of rows.values()) {
    const order = { md: 0, markdown: 0, docx: 1, xlsx: 2 };
    row.formats.sort((a, b) => (order[docExt(a.name)] ?? 9) - (order[docExt(b.name)] ?? 9));
  }
  return [...rows.values()];
}

export function isDocMd(f) {
  return /\.(md|markdown)$/i.test(String(f && (f.name || f.path) || ""));
}

export function createDeliverables({ state, capability, obStep, addStatus, openDoc, relTime, log, doc }) {
  function fileUrl(f, nameOverride) {
    /* 优先 session/run/file 形式：链接里不带服务器绝对路径，备份导入到另一台机器也还能点。
       Rust 工作台（没有 file_ref 能力）和老卡片仍用 path=。
       Rust canonicalize 返回 \\?\ verbatim 前缀；/api/file 对该形态 404——
       剥掉后端点自会 canonicalize（自测发现：此前侧栏下载链接全部 404）。
       name：卡片显示名，服务端据此写 Content-Disposition（手机端不认 download 属性）。 */
    const rec = f && typeof f === "object" ? f : { path: f };
    const p = String(rec.path || "").replace(/^\\\\\?\\/, "");
    const name = nameOverride || rec.name || "";
    let q;
    if (capability("file_ref") === true && rec.run_id && state.session && p) {
      const stored = p.split(/[\\/]/).pop();
      q = `/api/file?session=${encodeURIComponent(state.session)}&run=${encodeURIComponent(rec.run_id)}&file=${encodeURIComponent(stored)}`;
    } else {
      q = `/api/file?path=${encodeURIComponent(p)}`;
    }
    return name ? q + `&name=${encodeURIComponent(String(name))}` : q;
  }

  async function openDeliverable(f) {
    obStep(3); /* ux(round10)：文书预览打开 → 引导第 3 步打勾 */
    try {
      await openDoc({
        url: fileUrl(f),
        title: f.name || f.title || tr("交付物文书"),
        role: tr("岗位 · {0}", f.expert || tr("未指定")),
      });
    } catch (e) {
      addStatus(tr("预览失败 {0}：{1}", f.name || "", (e && e.message) || e));
    }
  }

  /* 聊天流内交付物卡片：点开即预览，另留 .md 下载 */
  /* 交付物卡片。files：扁平文件列表（done 事件 / 恢复）；runs：按轮分组（服务端
     deliverable_runs，带 export_errors / docx_pending）。同一份文书的 md / docx / xlsx
     折成一行：标题 + 预览 + 各格式下载；多文件的轮次给「打包下载」一个 zip。 */
  function runLabel(run) {
    const when = run && run.mtime ? relTime(Math.floor(Date.parse(run.mtime) / 1000)) : "";
    return [run && run.expert, when].filter(Boolean).join(" · ");
  }
  function appendDocCards(files, bodyEl, opts) {
    const options = opts || {};
    const runs = Array.isArray(options.runs) && options.runs.length
      ? options.runs
      : [{ run_id: "", expert: "", deliverables: files || [], export_errors: options.export_errors || [], docx_pending: options.docx_pending }];
    const host = bodyEl && bodyEl.parentElement ? bodyEl.parentElement : log();
    let painted = 0;
    for (const run of runs) {
      const groups = groupDeliverables(run.deliverables);
      const notes = [];
      if (run.docx_pending) notes.push(tr("Word 稿待生成：本轮只有 Markdown，稍后可在「本会话交付物」里取 Word。"));
      for (const e of run.export_errors || []) notes.push(tr("{0}：只有 Markdown 稿可下载。", e));
      if (!groups.length && !notes.length) continue;
      const card = doc.createElement("div");
      card.className = "cb-doc-card";
      const head = doc.createElement("div");
      head.className = "cb-doc-card-head";
      const tag = doc.createElement("span");
      tag.className = "cb-doc-card-tag";
      tag.textContent = tr("交付物文书");
      head.appendChild(tag);
      const label = runLabel(run);
      if (label) {
        const who = doc.createElement("span");
        who.className = "cb-doc-card-run";
        who.textContent = label;
        head.appendChild(who);
      }
      const nFiles = groups.reduce((n, g) => n + g.formats.length, 0);
      if (nFiles > 1 && run.run_id && state.session) {
        const zip = doc.createElement("a");
        zip.className = "dl cb-doc-card-zip";
        zip.href = `/api/deliverables.zip?session_id=${encodeURIComponent(state.session)}&run_id=${encodeURIComponent(run.run_id)}`;
        zip.setAttribute("download", `civil-docs-${run.run_id.slice(0, 8)}.zip`);
        zip.textContent = tr("打包下载（{0} 个文件）", nFiles);
        zip.addEventListener("click", () => obStep(3));
        head.appendChild(zip);
      }
      card.appendChild(head);
      for (const g of groups) {
        const row = doc.createElement("div");
        row.className = "cb-doc-row";
        const t = doc.createElement("span");
        t.className = "cb-doc-card-t";
        t.textContent = g.stem || tr("文书");
        t.title = g.formats.map((f) => f.name).join(" / ");
        row.appendChild(t);
        const md = g.formats.find(isDocMd);
        if (md) {
          const b = doc.createElement("button");
          b.type = "button";
          b.textContent = tr("预览");
          b.addEventListener("click", () => openDeliverable(md));
          row.appendChild(b);
        }
        for (const f of g.formats) {
          const a = doc.createElement("a");
          a.className = "dl";
          a.href = fileUrl(f);
          a.setAttribute("download", f.name || tr("文书.md"));
          a.textContent = "." + (docExt(f.name) || tr("文件"));
          a.title = tr("下载 ") + (f.name || "");
          a.addEventListener("click", () => obStep(3)); /* ux(round10)：下载 → 引导第 3 步打勾 */
          row.appendChild(a);
        }
        card.appendChild(row);
      }
      for (const n of notes) {
        const w = doc.createElement("p");
        w.className = "cb-doc-note";
        w.textContent = n;
        card.appendChild(w);
      }
      const k = doc.createElement("span");
      k.className = "cb-doc-card-k";
      k.textContent = tr("AI 草稿 · 不签认");
      card.appendChild(k);
      if (cbLang() === "en") {
        /* the post templates are Chinese; the page says so instead of machine-translating a draft */
        const zh = doc.createElement("p");
        zh.className = "cb-doc-note cb-lang-note";
        zh.textContent = tr("草稿模板为中文，未做机器翻译。");
        card.appendChild(zh);
      }
      host.appendChild(card);
      painted += 1;
    }
    if (painted) log().scrollTop = log().scrollHeight;
  }

  return { fileUrl, openDeliverable, appendDocCards, runLabel };
}
