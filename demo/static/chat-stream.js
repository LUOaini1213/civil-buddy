/* Shared SSE transport. No DOM or vendor dependencies. */
(function (root) {
  "use strict";

  function abortError() {
    const error = new Error("已停止接收回答");
    error.name = "AbortError";
    return error;
  }

  async function read(body, onEvent, options) {
    if (!body || typeof body.getReader !== "function") {
      throw new Error("服务器未返回可读取的回答流，请重试。");
    }
    const signal = options && options.signal;
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventName = "message";
    let dataLines = [];
    let ended = false;
    let cancelled = null;
    const cancel = () => {
      if (!cancelled) cancelled = reader.cancel().catch(() => {});
    };
    const checkAbort = () => {
      if (signal && signal.aborted) throw abortError();
    };
    const line = async (value) => {
      if (!value) {
        const name = eventName;
        const data = dataLines.join("\n");
        const hasData = dataLines.length > 0;
        eventName = "message";
        dataLines = [];
        if (hasData) await onEvent(name, data);
        return;
      }
      if (value[0] === ":") return; // Keepalive comment.
      const separator = value.indexOf(":");
      const field = separator < 0 ? value : value.slice(0, separator);
      let data = separator < 0 ? "" : value.slice(separator + 1);
      if (data[0] === " ") data = data.slice(1);
      if (field === "event") eventName = data || "message";
      if (field === "data") dataLines.push(data);
    };
    const drain = async (final) => {
      let start = 0;
      for (let i = 0; i < buffer.length; i += 1) {
        const ch = buffer[i];
        if (ch !== "\n" && ch !== "\r") continue;
        // A CRLF pair may straddle two network chunks.
        if (ch === "\r" && i + 1 === buffer.length && !final) break;
        checkAbort();
        await line(buffer.slice(start, i));
        if (ch === "\r" && buffer[i + 1] === "\n") i += 1;
        start = i + 1;
      }
      buffer = buffer.slice(start);
    };
    if (signal) signal.addEventListener("abort", cancel, { once: true });
    try {
      checkAbort();
      while (true) {
        const chunk = await reader.read();
        checkAbort();
        if (chunk.done) {
          ended = true;
          buffer += decoder.decode();
          await drain(true);
          // An unterminated event is intentionally not dispatched at EOF.
          break;
        }
        buffer += decoder.decode(chunk.value, { stream: true });
        await drain(false);
      }
    } finally {
      if (signal) signal.removeEventListener("abort", cancel);
      if (!ended) cancel();
      if (cancelled) await cancelled;
      reader.releaseLock();
    }
  }

  const api = { read };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CB_CHAT_STREAM = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
