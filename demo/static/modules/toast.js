/* The page's one visible notice: a single line at the bottom, gone after 6 s, optionally
   with one action button. `announce` mirrors it to the screen-reader live region. */
export function createToast({ doc, announce, ttl = 6000 } = {}) {
  let timer = null;
  return function toast(text, opts) {
    const options = opts || {};
    let box = doc.getElementById("cbToast");
    if (!box) {
      box = doc.createElement("div");
      box.id = "cbToast";
      box.className = "cb-toast";
      box.setAttribute("role", "status");
      doc.body.appendChild(box);
    }
    box.innerHTML = "";
    const msg = doc.createElement("span");
    msg.textContent = String(text || "");
    box.appendChild(msg);
    if (options.action && typeof options.onAction === "function") {
      const btn = doc.createElement("button");
      btn.type = "button";
      btn.textContent = options.action;
      btn.addEventListener("click", () => { box.hidden = true; options.onAction(); });
      box.appendChild(btn);
    }
    box.hidden = false;
    if (typeof announce === "function") announce(text);
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { box.hidden = true; }, ttl);
    return box;
  };
}
