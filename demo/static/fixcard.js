/* ===== Civil Buddy 纠偏卡片（ux round7 · docs/ux/ux-design-spec.md 附录 F）=====
 * 错误/拒绝/缺数从日志裸文本变成用户能行动的卡片。
 * 统一结构：发生了什么（一句人话）+ 为什么（策略 code/规则名）+ 现在能做什么（≤3 条动作/指引）。
 * 本文件 = 纯分类逻辑 + 通用 DOM 渲染；canonical。frontend/vendor/cb-fix.js 为同构副本（改动须同步两份）。
 * 借鉴（pattern-only）：Sentry issue 卡（类型+上下文+一键展开原始+动作在卡上）、
 * NN/g 错误消息三要素（可见/建设性/尊重用户付出）、GitHub 禁 toast（错误用常驻卡不用自动消失提示）。
 * 零 CDN、零外链、全 --cb-* token。话术只映射后端既有 code/reason，不编数字。 */
(function (global) {
  "use strict";

  /* 动作 kind：prefill=预填输入框草稿（不自动发送）· retry=重放同 payload · newsession=新开会话 · note=纯指引 */
  var KIND_META = {
    blocked: { badge: "已拦截", tone: "red" },
    circuit: { badge: "已熔断", tone: "red" },
    degraded: { badge: "已降级", tone: "orange" },
    retryable: { badge: "可重试", tone: "orange" },
    unsupported: { badge: "暂不支持", tone: "orange" },
    missing: { badge: "缺数", tone: "orange" },
    compliance: { badge: "合规阻断", tone: "red" },
    error: { badge: "失败", tone: "orange" },
  };

  /* 规则表（顺序即优先级）。模式对准后端既有 reason/error_code 原文：
     packing_assistant/runtime/policy.py · tool_engine.py · recovery.py · tools/nl_revision.py */
  function classify(raw, extra) {
    var text = String(raw == null ? "" : raw);
    var x = extra || {};
    var m;

    /* --- 策略引擎六类拒绝（policy.py）--- */
    if ((m = text.match(/拒绝：提问回合不能调写盘工具\s*(\S+?)。/))) {
      return {
        kind: "blocked", code: "deny_chat_write", why: "策略 deny_chat_write · 提问回合只读不写",
        title: "这是提问回合，AI 不会写盘：" + m[1] + " 被策略拦下",
        actions: [
          { kind: "prefill", label: "改成出稿任务", value: "写一份 " },
          { kind: "note", label: "把要写的内容说成「写一份…」就是 run 意图，可正常落盘" },
        ], raw: text,
      };
    }
    if ((m = text.match(/拒绝：岗\s*(\S+?)\s*不能调\s*(\S+?)（exclusive 属于\s*(\S+?)）。/))) {
      return {
        kind: "blocked", code: "deny_cross_expert", why: "策略 deny_cross_expert · 专属工具只归本岗",
        title: "岗 " + m[1] + " 越权调了 " + m[3] + " 的专属工具 " + m[2] + "，已拦截",
        actions: [
          { kind: "prefill", label: "召唤 @" + m[3], value: "@" + m[3] + " " },
          { kind: "note", label: "或把任务改写成 " + m[3] + " 岗的活，由本岗自己调" },
        ], raw: text,
      };
    }
    if ((m = text.match(/熔断：工具\s*(\S+?)\s*连续失败\s*(\d+)\s*次。/))) {
      return {
        kind: "circuit", code: "circuit_open", why: "策略 circuit_open · 连败熔断止损",
        title: "工具 " + m[1] + " 连着失败 " + m[2] + " 次，先熔断停下，没有继续烧",
        actions: [
          { kind: "retry", label: "重试" },
          { kind: "note", label: "连败多为下游/网络问题；稍后再试或换个说法重跑" },
        ], raw: text,
      };
    }
    if ((m = text.match(/熔断：session 成本超限 steps (\d+)\/(\d+) tokens (\d+)\/(\d+)。/))) {
      return {
        kind: "circuit", code: "deny_budget", why: "策略 deny_budget · 会话步数/字数预算",
        title: "本轮预算用完：steps " + m[1] + "/" + m[2] + " · tokens " + m[3] + "/" + m[4] + "，已停下",
        actions: [
          { kind: "prefill", label: "缩短输入重跑", value: "" },
          { kind: "newsession", label: "新开会话" },
          { kind: "note", label: "缩短任务描述或新开会话，预算按会话重新计" },
        ], raw: text,
      };
    }
    if ((m = text.match(/拒绝：目标\s*(.+?)\s*视为生产数据/))) {
      return {
        kind: "blocked", code: "deny_production", why: "策略 deny_production · 禁写生产数据区",
        title: "目标 " + m[1] + " 被判定为生产数据，写入被拒",
        actions: [
          { kind: "note", label: "输出只落本次运行的输出目录；不要指向 D:\\layout / prod" },
        ], raw: text,
      };
    }
    if (/密钥|secret|\.env/i.test(text) && text.indexOf("拒绝") === 0) {
      return {
        kind: "blocked", code: "deny_secret", why: "策略 deny_secret · 密钥沙箱",
        title: "目标碰到密钥/敏感文件，写入被拒，文件未落地",
        actions: [
          { kind: "note", label: "密钥永不写盘：敏感值放环境变量或密钥管理，不经 AI 落文件" },
        ], raw: text,
      };
    }
    if (text.indexOf("拒绝：") === 0 && /沙箱|sandbox|超出|越界|工作区/i.test(text)) {
      return {
        kind: "blocked", code: "deny_sandbox", why: "策略 deny_sandbox · 沙箱边界",
        title: "操作超出本次运行允许的沙箱范围，被拦下",
        actions: [
          { kind: "note", label: "把读写限制在本次会话的工作区/输出目录内" },
        ], raw: text,
      };
    }
    if (/拒绝：run 已取消/.test(text)) {
      return {
        kind: "blocked", code: "deny_cancelled", why: "策略 deny_cancelled · 任务已取消",
        title: "任务已取消，工具未执行", actions: [], raw: text,
      };
    }
    if ((m = text.match(/拒绝：未知工具\s*(\S+?)。/))) {
      return {
        kind: "blocked", code: "deny_unknown", why: "策略 deny_unknown · 工具未注册",
        title: "调用了未注册的工具 " + m[1] + "，已拦截",
        actions: [{ kind: "note", label: "检查工具名拼写；可用工具以本次运行的清单为准" }], raw: text,
      };
    }
    if ((m = text.match(/拒绝：工具\s*(\S+?)\s*缺少参数\s*(\S+?)。/))) {
      return {
        kind: "retryable", code: "invalid_args", why: "参数校验 invalid_args · 缺 " + m[2],
        title: "工具 " + m[1] + " 缺少参数 " + m[2] + "，没跑成",
        actions: [
          { kind: "retry", label: "重试" },
          { kind: "note", label: "补齐参数后重试；参数由调用方组装，AI 不编" },
        ], raw: text,
      };
    }

    /* --- 改方案不支持（nl_revision status=unsupported，message 以「无此功能」开头）--- */
    if (/无此功能/.test(text)) {
      var acts = [];
      var hints = x.hints || [];
      var hasCaps = x.supported_capabilities && x.supported_capabilities.length;
      var maxHints = hasCaps ? 2 : 3; /* 总动作 ≤3：能力提示占 1 个 note 位 */
      for (var i = 0; i < hints.length && acts.length < maxHints; i++) {
        acts.push({ kind: "prefill", label: hints[i], value: hints[i] });
      }
      if (hasCaps) {
        acts.push({ kind: "note", label: "现在会改：" + x.supported_capabilities.join(" / ") });
      } else if (acts.length < 3) {
        acts.push({ kind: "note", label: "试试给出的示例改法，或直接在表单里改" });
      }
      return {
        kind: "unsupported", code: "revise_unsupported", why: "nl_revision · status=unsupported",
        title: "这个改法还不会：方案保持原样，没有假装成功",
        actions: acts, raw: text,
      };
    }

    /* --- 失败恢复（recovery.py）：降级 / 超时 --- */
    if ((m = text.match(/下游失败\s*([\w-]*)\s*，工具\s*(\S+?)\s*降级/))) {
      var meta = [];
      if (x.attempts != null) meta.push("共尝试 " + x.attempts + " 次");
      if (x.audit && x.audit.length) meta.push(x.audit.join(" → "));
      return {
        kind: "degraded", code: "recovery_degrade", why: "恢复层 recovery · 降级到 UNSPECIFIED",
        title: "工具 " + m[2] + " 重试后仍失败，已降级：柜数等数字标为「未提供」，不编造",
        actions: [
          { kind: "retry", label: "重试本工具" },
          { kind: "note", label: "或补齐/修正输入（尺寸、重量）后整单重跑" },
        ],
        meta: meta.join(" · "), raw: text,
      };
    }
    if (/超时|timeout|timed? ?out/i.test(text)) {
      return {
        kind: "retryable", code: "timeout", why: "error_code=timeout · 下游超时，可重试",
        title: (function () { var t = text.match(/工具\s*(\S+?)\s*下游超时（([\d.]+)s）/); return t ? ("工具 " + t[1] + " 等了 " + t[2] + " 秒没回应") : "下游超时，这次没跑成"; })(),
        actions: [
          { kind: "retry", label: "重试" },
          { kind: "note", label: "重试重放同一任务；仍超时多为下游不可用，稍后再试" },
        ], raw: text,
      };
    }

    /* --- 合规阻断（BOX-01 类：结构校核/出运门禁）--- */
    if (/阻断|ship_gate|非标|废标|超长|超载/.test(text)) {
      return {
        kind: "compliance", code: "compliance_block", why: "合规校核 risk_compliance · 出运门禁",
        title: "合规校核拦下，不是工具坏了：按下面改即可重跑",
        actions: [
          { kind: "prefill", label: "改箱型重跑", value: "换箱型重跑：" },
          { kind: "prefill", label: "减载重重跑", value: "减少装载重量重跑：" },
          { kind: "note", label: "阻断项见卡上原文；改箱型/减载重/拆并箱后再跑" },
        ], raw: text,
      };
    }

    /* --- 兜底：普通失败 --- */
    return {
      kind: "error", code: x.error_code || "error", why: (x.error_code ? "error_code=" + x.error_code : "运行报错"),
      title: text.length > 120 ? text.slice(0, 120) + "…" : (text || "运行报错"),
      actions: x.retryable ? [{ kind: "retry", label: "重试" }] : [{ kind: "note", label: "可修改输入后重跑；如反复出现请留下原始报错" }],
      raw: text,
    };
  }

  /* 缺数引导：UNSPECIFIED/[A001] 徽章旁的「去补数」提示条（动作预填草稿，不自动发送） */
  function classifyMissing(text) {
    var t = String(text == null ? "" : text);
    var n = (t.match(/UNSPECIFIED/g) || []).length;
    var anchors = t.match(/\[A\d{3}\]/g) || [];
    var uniq = [];
    for (var i = 0; i < anchors.length; i++) if (uniq.indexOf(anchors[i]) < 0) uniq.push(anchors[i]);
    var total = n + uniq.length;
    if (!total) return null;
    return {
      kind: "missing", code: "missing_data", why: "数据哨兵 UNSPECIFIED / " + (uniq[0] || "[A001]"),
      title: "还有 " + total + " 处数据未提供（未提供/未填锚点）——补一句话即可重跑",
      actions: [
        { kind: "prefill", label: "去补数", value: "补充：" + (uniq.length ? uniq.join(" ") + " " : "") },
        { kind: "note", label: "在输入框补一句话（如尺寸 / 重量 / 项目名 / 点位坐标），发送即重跑；缺的数 AI 不编" },
      ],
      raw: uniq.length ? ("锚点 " + uniq.join(" ") + " · UNSPECIFIED×" + n) : ("UNSPECIFIED×" + n),
      count: total,
    };
  }

  /* 通用 DOM 渲染。handlers = { prefill(v), retry(), newsession() }（按端注入） */
  function cardEl(desc, handlers) {
    var H = handlers || {};
    var meta = KIND_META[desc.kind] || KIND_META.error;
    var root = document.createElement("div");
    root.className = "cb-fix is-" + (meta.tone || "orange");
    root.setAttribute("data-cb-fix", desc.code || "error");
    root.setAttribute("role", "alert");

    var bar = document.createElement("span");
    bar.className = "cb-fix-bar";
    bar.setAttribute("aria-hidden", "true");
    root.appendChild(bar);

    var main = document.createElement("div");
    main.className = "cb-fix-main";

    var head = document.createElement("div");
    head.className = "cb-fix-head";
    var badge = document.createElement("span");
    badge.className = "cb-fix-badge";
    badge.textContent = meta.badge;
    head.appendChild(badge);
    var title = document.createElement("span");
    title.className = "cb-fix-title";
    title.textContent = desc.title || "";
    head.appendChild(title);
    main.appendChild(head);

    var why = document.createElement("div");
    why.className = "cb-fix-why";
    var code = document.createElement("span");
    code.className = "cb-fix-code";
    code.textContent = desc.code || "";
    why.appendChild(code);
    if (desc.why) {
      var whyTxt = document.createElement("span");
      whyTxt.className = "cb-fix-why-txt";
      whyTxt.textContent = desc.why;
      why.appendChild(whyTxt);
    }
    main.appendChild(why);

    if (desc.meta) {
      var metaEl = document.createElement("div");
      metaEl.className = "cb-fix-meta";
      metaEl.textContent = desc.meta;
      main.appendChild(metaEl);
    }

    var acts = (desc.actions || []).slice(0, 3);
    if (acts.length) {
      var what = document.createElement("div");
      what.className = "cb-fix-what";
      var label = document.createElement("span");
      label.className = "cb-fix-what-label";
      label.textContent = "现在能做什么";
      what.appendChild(label);
      for (var i = 0; i < acts.length; i++) {
        (function (a) {
          if (a.kind === "note") {
            var note = document.createElement("span");
            note.className = "cb-fix-note";
            note.textContent = a.label;
            what.appendChild(note);
            return;
          }
          if (a.kind === "newsession" && typeof H.newsession !== "function") return;
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "cb-fix-btn" + (a.kind === "retry" ? " is-retry" : "");
          btn.textContent = a.label;
          if (a.kind === "prefill") btn.addEventListener("click", function () { if (H.prefill) H.prefill(a.value || a.label); });
          else if (a.kind === "retry") btn.addEventListener("click", function () { if (H.retry) H.retry(); });
          else if (a.kind === "newsession") btn.addEventListener("click", function () { if (H.newsession) H.newsession(); });
          what.appendChild(btn);
        })(acts[i]);
      }
      main.appendChild(what);
    }

    if (desc.raw) {
      var det = document.createElement("details");
      det.className = "cb-fix-raw";
      var sum = document.createElement("summary");
      sum.textContent = "原始记录";
      det.appendChild(sum);
      var pre = document.createElement("code");
      pre.textContent = desc.raw;
      det.appendChild(pre);
      main.appendChild(det);
    }

    root.appendChild(main);
    return root;
  }

  var API = { classify: classify, classifyMissing: classifyMissing, cardEl: cardEl, KIND_META: KIND_META };
  global.CB_FIX = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
