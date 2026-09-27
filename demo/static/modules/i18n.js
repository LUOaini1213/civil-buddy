/* The language switch as the page's modules see it (the runtime is /static/i18n.js, loaded first by index.html).
   Without it — a test harness, a page that did not load it — messages come back in Chinese with {0} {1} filled,
   exactly as they were written. */
function runtime() {
  const g = typeof window !== "undefined" ? window : globalThis;
  return g && g.CB_I18N && typeof g.CB_I18N.t === "function" ? g.CB_I18N : null;
}

export function tr(message, ...args) {
  const r = runtime();
  if (r) return r.t(message, ...args);
  return String(message).replace(/\{(\d+)\}/g, (whole, index) => {
    const i = Number(index);
    if (i >= args.length) return whole;
    return args[i] === undefined || args[i] === null ? "" : String(args[i]);
  });
}

export function cbLang() {
  const r = runtime();
  return r ? r.lang() : "zh";
}

export function cbOnLang(fn) {
  const r = runtime();
  if (r) r.onChange(fn);
}
