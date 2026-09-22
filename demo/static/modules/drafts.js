/* One composer draft per session: saved as you type, restored when you come back to that
   session, cleared on send. `storage` is anything with getItem/setItem/removeItem. */
export const DRAFT_PREFIX = "cb_draft:";

export function createDrafts({ storage, input, session, afterRestore } = {}) {
  const key = (sid) => DRAFT_PREFIX + sid;

  function save() {
    const ta = input();
    const sid = session();
    if (!ta || !sid) return;
    try {
      if (ta.value.trim()) storage.setItem(key(sid), ta.value);
      else storage.removeItem(key(sid));
    } catch (e) { /* storage unavailable: nothing to keep */ }
  }

  function clear(sid) {
    try { storage.removeItem(key(sid || session())); } catch (e) { /* ignore */ }
  }

  function restore() {
    const ta = input();
    if (!ta) return "";
    let v = "";
    try { v = storage.getItem(key(session())) || ""; } catch (e) { /* ignore */ }
    ta.value = v;
    if (typeof afterRestore === "function") afterRestore(ta);
    return v;
  }

  return { save, clear, restore };
}
