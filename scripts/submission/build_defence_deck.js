// 海之子杯复赛答辩 PPT 生成器
// 逐页文案在 docs/submission/haizizhi-defence-deck.json（每页挂出处），成品写到
// output/submission/05-复赛答辩PPT-CivilBuddy.pptx（该目录 gitignored）。
// 内容由多智能体取证产出：四路读仓库取可复跑事实 → 三种叙事角度 → 九个评审打分 → 合成。
// 视觉：深工程蓝黑主色，封面与收口深底、内容页浅底；安全琥珀强调；工具绿＝工具算的数、
//       蓝＝人确认、红＝被挡下的错；母题是每个数字下面挂一枚等宽字体的“出处”角标。
const fs = require("fs");
const path = require("path");

// pptxgenjs 不是本仓依赖（package.json 里一个 dependency 都没有，不为一份 PPT 破例）。
// 跑法：在任意临时目录 `npm i pptxgenjs`，然后
//   NODE_PATH=<那个目录>/node_modules node scripts/submission/build_defence_deck.js
let pptxgen;
try {
  pptxgen = require("pptxgenjs");
} catch (e) {
  console.error("缺少 pptxgenjs。在任意目录 npm i pptxgenjs 后，用 NODE_PATH 指向它的 node_modules 再跑。");
  process.exit(2);
}

const ROOT = path.resolve(__dirname, "..", "..");
const CONTENT = path.join(ROOT, "docs", "submission", "haizizhi-defence-deck.json");
const D = JSON.parse(fs.readFileSync(CONTENT, "utf8"));
const S = {};
D.slides.forEach((s) => (S[s.n] = s));

const C = {
  ink: "0E1B2B", inkSoft: "16293D", inkLine: "26405A",
  paper: "F4F6F8", white: "FFFFFF", card: "FFFFFF",
  amber: "E6B84D", amberDeep: "A8781E",
  tool: "1E8F5C", toolSoft: "E4F4EC",
  human: "2563EB", humanSoft: "E6EDFC",
  danger: "C0453B", dangerSoft: "FBEAE8",
  text: "1B2733", muted: "5A6675", faint: "93A1AF",
  line: "DCE2E8", grey: "B9C2CB",
};
const F = { t: "微软雅黑", b: "微软雅黑", m: "Consolas" };
const W = 13.333, H = 7.5, M = 0.8;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "团队 Mintang";
pres.company = "Civil Buddy";
pres.title = D.deck_title;

const shadow = () => ({ type: "outer", angle: 90, offset: 2, blur: 9, color: "8E9BA8", opacity: 0.22 });

function notes(slide, n) {
  const s = S[n];
  slide.addNotes(`【${s.seconds} 秒】${s.speaker_notes}\n\n——出处——\n${s.evidence}`);
}

function light(n, kicker) {
  const sl = pres.addSlide();
  sl.background = { color: C.paper };
  sl.addText(kicker, { x: M, y: 0.46, w: W - 2 * M, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.amberDeep, charSpacing: 3 });
  sl.addText(S[n].title, { x: M, y: 0.74, w: W - 2 * M, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 31, bold: true, color: C.ink });
  sl.addText(`${n} / 14`, { x: W - M - 1.2, y: H - 0.5, w: 1.2, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F.m, fontSize: 9, color: C.faint, align: "right" });
  return sl;
}

function chip(sl, text, x, y, w, onDark) {
  sl.addShape(pres.ShapeType.roundRect, { x, y, w, h: 0.26, rectRadius: 0.05,
    fill: { color: onDark ? C.inkSoft : C.white }, line: { color: onDark ? C.inkLine : C.line, width: 0.75 } });
  sl.addText(text, { x: x + 0.1, y, w: w - 0.2, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F.m, fontSize: 8.5, color: onDark ? "8FA7BC" : C.muted, valign: "middle" });
}

function rule(sl, x, y, w, color, h) {
  sl.addShape(pres.ShapeType.rect, { x, y, w, h: h || 0.02, fill: { color: color || C.line }, line: { type: "none" } });
}

function vrule(sl, x, y, h, color) {
  sl.addShape(pres.ShapeType.rect, { x, y, w: 0.02, h, fill: { color: color || C.line }, line: { type: "none" } });
}

function card(sl, o) {
  sl.addShape(pres.ShapeType.roundRect, { x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.07,
    fill: { color: o.fill || C.card }, line: { color: o.border || C.line, width: o.borderW || 1 },
    shadow: o.flat ? undefined : shadow() });
}

// ============================== 1. 封面 ==============================
{
  const sl = pres.addSlide();
  sl.background = { color: C.ink };
  sl.addText("Civil Buddy", { x: M, y: 1.35, w: 9, h: 1.0, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 52, bold: true, color: C.white });
  sl.addText("土木企业 16 大类 66 岗的内部起草搭子", { x: M, y: 2.4, w: 9, h: 0.45, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 17, color: "9FB3C8" });

  // 中部：闸门
  rule(sl, M, 3.95, W - 2 * M, C.inkLine, 0.015);
  sl.addText("AI 一定会做错", { x: M, y: 3.42, w: 3.4, h: 0.4, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 16, color: "8FA7BC" });
  sl.addText("错，走不出这道门", { x: W - M - 4.2, y: 3.42, w: 4.2, h: 0.4, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 18, bold: true, color: C.amber, align: "right" });
  // 闸门符号：两条竖杠夹一个被挡住的箭头
  sl.addShape(pres.ShapeType.rect, { x: 6.28, y: 3.55, w: 0.11, h: 0.8, fill: { color: C.amber }, line: { type: "none" } });
  sl.addShape(pres.ShapeType.rect, { x: 7.02, y: 3.55, w: 0.11, h: 0.8, fill: { color: C.amber }, line: { type: "none" } });
  sl.addText("→", { x: 5.55, y: 3.72, w: 0.7, h: 0.45, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 22, bold: true, color: "5C7A8C", align: "center", valign: "middle" });
  sl.addShape(pres.ShapeType.ellipse, { x: 6.5, y: 3.78, w: 0.4, h: 0.4, fill: { color: C.amber }, line: { type: "none" } });
  sl.addText("✕", { x: 6.5, y: 3.78, w: 0.4, h: 0.4, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 13, bold: true, color: C.ink, align: "center", valign: "middle" });

  const facts = ["所有产出：内部讨论草稿", "不出签认件，不代交官方系统", "能否投标、能否开工，不由它判"];
  facts.forEach((t, i) => {
    sl.addText("· " + t, { x: M, y: 4.62 + i * 0.36, w: 7, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 13.5, color: "8FA7BC" });
  });
  sl.addText("今天只讲一件事：错，是怎么被挡住的", { x: W - M - 5.4, y: 4.7, w: 5.4, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 17, bold: true, color: C.white, align: "right" });

  rule(sl, M, 6.45, W - 2 * M, C.inkLine, 0.015);
  sl.addText("第一届「海之子」杯 AI 智能体挑战计划 · 复赛答辩 · 团队 Mintang", {
    x: M, y: 6.62, w: 8.5, h: 0.3, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 11, color: "6E889E" });
  sl.addText("内部讨论 AI 草稿 · 不是签认件", { x: W - M - 4, y: 6.62, w: 4, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: "6E889E", align: "right" });
  notes(sl, 1);
}

// ============================== 2. 六步流程 ==============================
{
  const sl = light(2, "现状");
  sl.addText("一份出运表进来，一张装柜作业单出去 —— 中间必须停在一个人那里", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 14, color: C.muted });

  const steps = [
    { t: "读表", g: "表头映射门" }, { t: "听懂", g: "意图分流" }, { t: "算数", g: "引擎算数" },
    { t: "过门", g: "合规门" }, { t: "人确认", g: "HITL" }, { t: "出文书", g: "数字溯源" },
  ];
  const bw = 1.32, gap = 0.23, x0 = M + 1.32, y0 = 2.55;
  steps.forEach((s, i) => {
    const x = x0 + i * (bw + gap);
    const isHuman = i === 4;
    card(sl, { x, y: y0, w: bw, h: 1.0, border: isHuman ? C.amber : C.line, borderW: isHuman ? 2 : 1 });
    sl.addText(s.t, { x, y: y0, w: bw, h: 1.0, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: isHuman ? 17 : 15.5, bold: true, color: isHuman ? C.amberDeep : C.ink,
      align: "center", valign: "middle" });
    sl.addText(s.g, { x, y: y0 + 1.08, w: bw, h: 0.26, isTextBox: true, margin: 0,
      fontFace: F.m, fontSize: 8, color: C.faint, align: "center" });
    if (i < steps.length - 1) {
      sl.addText("→", { x: x + bw, y: y0 + 0.3, w: gap, h: 0.4, isTextBox: true, margin: 0,
        fontFace: F.b, fontSize: 15, color: C.grey, align: "center", valign: "middle" });
    }
  });
  // 人确认上方的小人
  sl.addShape(pres.ShapeType.ellipse, { x: x0 + 4 * (bw + gap) + bw / 2 - 0.17, y: y0 - 0.62, w: 0.34, h: 0.34,
    fill: { color: C.amber }, line: { type: "none" } });
  sl.addText("人", { x: x0 + 4 * (bw + gap) + bw / 2 - 0.17, y: y0 - 0.62, w: 0.34, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 11, bold: true, color: C.ink, align: "center", valign: "middle" });
  sl.addText("流程在这里停", { x: x0 + 4 * (bw + gap) - 0.3, y: y0 - 0.95, w: 2.1, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 10, bold: true, color: C.amberDeep, align: "center" });

  // 两端
  card(sl, { x: M, y: y0 - 0.05, w: 1.15, h: 1.1, fill: "EDF1F5", flat: true, border: C.line });
  sl.addText("真实\n出运表", { x: M, y: y0 - 0.05, w: 1.15, h: 1.1, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.muted, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
  card(sl, { x: W - M - 1.15, y: y0 - 0.05, w: 1.15, h: 1.1, fill: "EDF1F5", flat: true, border: C.line });
  sl.addText("装柜\n作业单", { x: W - M - 1.15, y: y0 - 0.05, w: 1.15, h: 1.1, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.muted, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });

  rule(sl, M, 4.45, W - 2 * M, C.line);
  const pts = [
    ["每一步都出过、或拦下过一个真错", "所以每一步都留了一道现在还在跑的门"],
    ["没做过工时实测", "所以今天不报「省了多少小时」"],
  ];
  pts.forEach((p, i) => {
    const x = M + i * 6.1;
    sl.addText(p[0], { x, y: 4.78, w: 5.7, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 15, bold: true, color: C.ink });
    sl.addText(p[1], { x, y: 5.14, w: 5.7, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12.5, color: C.muted });
  });
  chip(sl, "docs/ARCHITECTURE.md · harness 0.6.4 · agent_mode=steps", M, 5.8, 5.6, false);
  notes(sl, 2);
}

// ============================== 3. 算数：15 → 1 ==============================
{
  const sl = light(3, "第一层 · 算数");
  sl.addText("同一套流程，跑两条命令 —— 一条装得下，一条被自己的合规门打回", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  // 左：正例
  card(sl, { x: M, y: 2.0, w: 7.4, h: 4.05 });
  sl.addText("正例", { x: M + 0.35, y: 2.2, w: 2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.tool, charSpacing: 2 });
  sl.addText("15 → 1", { x: M + 0.35, y: 2.5, w: 3.4, h: 1.0, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 54, bold: true, color: C.ink });
  sl.addText("15 个箱子装进 1 个 40HQ\n逐箱 x / y / z 坐标由引擎算出", {
    x: M + 3.7, y: 2.62, w: 3.3, h: 0.9, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, color: C.muted, lineSpacingMultiple: 1.25 });

  const bars = [["订柜有效体积", 0.8226, "82%"], ["重量利用率", 0.9439, "94%"]];
  bars.forEach((b, i) => {
    const y = 3.72 + i * 0.62;
    sl.addText(b[0], { x: M + 0.35, y, w: 2.2, h: 0.28, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12, color: C.text });
    sl.addShape(pres.ShapeType.roundRect, { x: M + 2.6, y: y + 0.06, w: 3.3, h: 0.18, rectRadius: 0.09,
      fill: { color: "E3E8ED" }, line: { type: "none" } });
    sl.addShape(pres.ShapeType.roundRect, { x: M + 2.6, y: y + 0.06, w: 3.3 * b[1], h: 0.18, rectRadius: 0.09,
      fill: { color: C.tool }, line: { type: "none" } });
    sl.addText(b[2], { x: M + 6.0, y, w: 0.9, h: 0.28, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 13, bold: true, color: C.tool });
  });

  const badges = [["风险判定 WARN：订舱前复核", C.amber, C.amberDeep], ["VGM 草稿：待托运人签字", C.grey, C.muted]];
  badges.forEach((b, i) => {
    const x = M + 0.35 + i * 3.4;
    sl.addShape(pres.ShapeType.roundRect, { x, y: 5.08, w: 3.2, h: 0.4, rectRadius: 0.06,
      fill: { color: C.white }, line: { color: b[1], width: 1.25 } });
    sl.addText(b[0], { x: x + 0.12, y: 5.08, w: 2.96, h: 0.4, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 11, bold: true, color: b[2], valign: "middle" });
  });
  chip(sl, "main.py --demo → output/runs/20260920_133429_0f36f38d", M + 0.35, 5.6, 5.4, false);

  // 右：负例
  card(sl, { x: M + 7.75, y: 2.0, w: 3.98, h: 4.05, fill: "FCF3F2", border: "EBC7C2" });
  sl.addText("负例", { x: M + 8.1, y: 2.2, w: 2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.danger, charSpacing: 2 });
  sl.addShape(pres.ShapeType.ellipse, { x: M + 8.1, y: 2.62, w: 0.62, h: 0.62, fill: { color: C.danger }, line: { type: "none" } });
  sl.addText("✕", { x: M + 8.1, y: 2.62, w: 0.62, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 21, bold: true, color: C.white, align: "center", valign: "middle" });
  sl.addText("结构校核不通过", { x: M + 8.1, y: 3.42, w: 3.3, h: 0.44, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 21, bold: true, color: C.danger });
  sl.addText("REJECT · level=high", { x: M + 8.1, y: 3.88, w: 3.3, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.m, fontSize: 11, color: C.danger });
  sl.addText("30 个 6 米铁架（负例箱数）\n→ 打回改箱型加固", { x: M + 8.1, y: 4.35, w: 3.3, h: 0.7, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted, lineSpacingMultiple: 1.25 });
  chip(sl, "--preset structure_fail", M + 8.1, 5.6, 3.3, false);
  notes(sl, 3);
}

// ============================== 4. 71 / 128 ==============================
{
  const sl = light(4, "第二层 · 自我推翻");
  // 被划掉的旧数字
  sl.addText("128 / 128  PASS", { x: M, y: 1.6, w: 5.2, h: 0.72, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 36, bold: true, color: C.grey, strike: true });
  sl.addText("自建评测这样报了很久", { x: M, y: 2.3, w: 5.2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.faint });
  sl.addText("↓", { x: M + 0.55, y: 2.72, w: 0.6, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 22, bold: true, color: C.amber, align: "center" });
  sl.addText("人追进脚本：判据接受 can_fit=False", { x: M + 1.25, y: 2.8, w: 5, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, color: C.amberDeep, valign: "middle" });

  sl.addText("71 / 128", { x: M, y: 3.35, w: 5.2, h: 1.1, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 62, bold: true, color: C.ink });
  sl.addText("128 次真实流水线里，真正装得下的次数", { x: M, y: 4.48, w: 5.4, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 13.5, color: C.text });
  sl.addText("PASS 只代表流程跑完并返回了 can_fit 字段", { x: M, y: 4.82, w: 5.4, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted });
  sl.addText("这 71 次全是单柜；另外 57 次交回人改方案", { x: M, y: 5.2, w: 5.4, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted });
  chip(sl, "render_eval_table.py --check README.md · CI 每次提交核对", M, 5.72, 5.4, false);

  // 128 点阵
  const gx = M + 6.1, gy = 2.05, cell = 0.3, pad = 0.09;
  sl.addText("128 次 · 每格一次流水线", { x: gx, y: 1.62, w: 5, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.muted });
  for (let i = 0; i < 128; i++) {
    const r = Math.floor(i / 16), c = i % 16;
    const fit = i < 71;
    sl.addShape(pres.ShapeType.rect, {
      x: gx + c * (cell + pad * 0.35), y: gy + r * (cell + pad * 0.45), w: cell, h: cell,
      fill: { color: fit ? C.tool : "EDF1F5" }, line: { color: fit ? C.tool : C.grey, width: 0.75 },
    });
  }
  const legendY = gy + 8 * (cell + pad * 0.45) + 0.18;
  sl.addShape(pres.ShapeType.rect, { x: gx, y: legendY, w: 0.22, h: 0.22, fill: { color: C.tool }, line: { type: "none" } });
  sl.addText("装得下 71", { x: gx + 0.32, y: legendY - 0.02, w: 1.6, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.text, valign: "middle" });
  sl.addShape(pres.ShapeType.rect, { x: gx + 2.0, y: legendY, w: 0.22, h: 0.22, fill: { color: "EDF1F5" }, line: { color: C.grey, width: 0.75 } });
  sl.addText("装不下 57 · 交回人改", { x: gx + 2.32, y: legendY - 0.02, w: 3, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.muted, valign: "middle" });
  sl.addText("两个数由脚本从留档算出，一个都不许手打", { x: gx, y: legendY + 0.44, w: 5.3, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, bold: true, color: C.amberDeep });
  notes(sl, 4);
}

// ============================== 5. 数字全对，结论是编的 ==============================
{
  const sl = light(5, "第三层 · 结论");
  sl.addText("本机小模型 qwen2.5:3b 跑三个真实任务，这是它写的原话", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  card(sl, { x: M, y: 2.0, w: 7.6, h: 1.5 });
  sl.addText("模型回复", { x: M + 0.35, y: 2.2, w: 2, h: 0.28, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, bold: true, color: C.faint, charSpacing: 2 });
  sl.addText("「所有约束条件都满足，可以订舱」", { x: M + 0.35, y: 2.52, w: 6.9, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 21, bold: true, color: C.text });
  sl.addShape(pres.ShapeType.roundRect, { x: M + 0.35, y: 3.06, w: 3.5, h: 0.32, rectRadius: 0.05,
    fill: { color: C.toolSoft }, line: { type: "none" } });
  sl.addText("✓ 句中数字全部通过溯源检查", { x: M + 0.45, y: 3.06, w: 3.3, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 10.5, bold: true, color: C.tool, valign: "middle" });

  sl.addText("⚡ 结论冲突", { x: M + 8.0, y: 2.55, w: 2.2, h: 0.4, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 15, bold: true, color: C.danger, align: "center", valign: "middle" });
  sl.addText("↕", { x: M + 8.7, y: 3.0, w: 0.8, h: 0.9, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 26, bold: true, color: C.danger, align: "center", valign: "middle" });

  card(sl, { x: M, y: 3.72, w: 7.6, h: 1.25, fill: C.ink, border: C.ink });
  sl.addText("引擎报告", { x: M + 0.35, y: 3.9, w: 2, h: 0.28, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, bold: true, color: "6E889E", charSpacing: 2 });
  sl.addText("「不可直接订舱」", { x: M + 0.35, y: 4.22, w: 6.9, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 21, bold: true, color: "FF8E85" });

  card(sl, { x: M + 8.0, y: 3.72, w: 3.73, h: 1.25, fill: "FDF6E6", border: "EAD4A0" });
  sl.addText("数字全对\n结论是编的", { x: M + 8.25, y: 3.92, w: 3.2, h: 0.9, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 19, bold: true, color: C.amberDeep, lineSpacingMultiple: 1.2 });

  rule(sl, M, 5.32, W - 2 * M, C.line);
  sl.addText("护栏动作：模型下了结论 → 先让它改写一次 → 改完还在的，从正文划掉并点名", {
    x: M, y: 5.55, w: 8.6, h: 0.36, isTextBox: true, margin: 0, fontFace: F.t, fontSize: 15, bold: true, color: C.ink });
  sl.addText("护栏是确定性代码，与模型聪不聪明无关", { x: M, y: 5.95, w: 8.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted });
  chip(sl, "verdict_guard.py · PR #39 · eval_verdicts.py", M + 8.0, 5.62, 3.73, false);
  notes(sl, 5);
}

// ============================== 6. 护栏被满分骗过 ==============================
{
  const sl = light(6, "第三层 · 自查");
  sl.addText("规则定稿之后、运行之前，另写一轮它没见过的题", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  const colX = [M + 3.4, M + 6.9], colW = 3.2, rowY = [2.55, 3.55];
  sl.addText("开发集（它见过）", { x: colX[0], y: 2.05, w: colW, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, bold: true, color: C.faint, align: "center" });
  sl.addText("留出集（规则冻结后才写）", { x: colX[1], y: 2.05, w: colW, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, bold: true, color: C.ink, align: "center" });

  const rows = [["第一版 · 字面短语表", "1.000", "0.667"], ["现行 · 句式规则", "1.000", "0.900"]];
  rows.forEach((r, i) => {
    sl.addText(r[0], { x: M, y: rowY[i] + 0.2, w: 3.2, h: 0.4, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 13, color: C.text, valign: "middle" });
    [1, 2].forEach((k) => {
      const dev = k === 1;
      const hi = !dev && i === 1;
      card(sl, { x: colX[k - 1], y: rowY[i], w: colW, h: 0.8,
        fill: dev ? "E8ECF0" : C.white, border: hi ? C.amber : C.line, borderW: hi ? 2.25 : 1, flat: dev });
      sl.addText(r[k], { x: colX[k - 1], y: rowY[i], w: colW, h: 0.8, isTextBox: true, margin: 0,
        fontFace: F.t, fontSize: hi ? 30 : 24, bold: true, color: dev ? C.grey : (i === 0 ? C.danger : C.ink),
        align: "center", valign: "middle" });
    });
  });
  sl.addText("满分是必然，没有信息量", { x: colX[0], y: 4.45, w: colW, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, color: C.faint, align: "center" });
  sl.addText("我们对外只报这一格", { x: colX[1], y: 4.45, w: colW, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.amberDeep, align: "center" });

  rule(sl, M, 5.0, W - 2 * M, C.line);
  sl.addText("第一版在没见过的题上漏掉了：满足规范要求 · 已通过专家论证 · 不存在废标问题", {
    x: M, y: 5.22, w: 8.4, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 13, color: C.text });
  sl.addText("召回 1.000，但样本只有 20 句 / 9 个必报项 —— 说的是这一轮，不是「不会漏」", {
    x: M, y: 5.6, w: 8.4, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 12, color: C.muted });
  chip(sl, "eval_verdicts.py --heldout 2", M + 8.9, 5.3, 2.83, false);
  notes(sl, 6);
}

// ============================== 7. ×1000 ==============================
{
  const sl = light(7, "交卷之后");
  sl.addText("我们逐条复核「材料写的」与「代码做的」是否一致，最重的一处在这里", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  card(sl, { x: M, y: 2.05, w: 3.1, h: 1.5 });
  sl.addText("表头写的", { x: M, y: 2.22, w: 3.1, h: 0.28, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.faint, align: "center" });
  sl.addText("1.35 t", { x: M, y: 2.5, w: 3.1, h: 0.75, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 40, bold: true, color: C.ink, align: "center" });

  sl.addText("×1000", { x: M + 3.35, y: 2.42, w: 2.2, h: 0.8, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 40, bold: true, color: C.danger, align: "center", valign: "middle" });

  card(sl, { x: M + 5.8, y: 2.05, w: 3.1, h: 1.5, fill: C.dangerSoft, border: "EBC7C2" });
  sl.addText("程序读成", { x: M + 5.8, y: 2.22, w: 3.1, h: 0.28, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.danger, align: "center" });
  sl.addText("1.35 kg", { x: M + 5.8, y: 2.5, w: 3.1, h: 0.75, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 40, bold: true, color: C.danger, align: "center" });

  sl.addText("这个换算比例同时喂给三处", { x: M, y: 3.85, w: 5, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 14, bold: true, color: C.ink });
  ["按重量估柜", "载重校验", "VGM 草稿"].forEach((t, i) => {
    const x = M + i * 3.05;
    sl.addShape(pres.ShapeType.roundRect, { x, y: 4.28, w: 2.75, h: 0.52, rectRadius: 0.06,
      fill: { color: C.white }, line: { color: C.danger, width: 1.25, dashType: "dash" } });
    sl.addText(t, { x, y: 4.28, w: 2.75, h: 0.52, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12.5, bold: true, color: C.danger, align: "center", valign: "middle" });
  });

  card(sl, { x: M + 9.25, y: 2.05, w: 2.48, h: 2.75, fill: C.toolSoft, border: "BCDFCE" });
  sl.addText("修后", { x: M + 9.25, y: 2.25, w: 2.48, h: 0.28, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, bold: true, color: C.tool, align: "center", charSpacing: 2 });
  sl.addText("14 种", { x: M + 9.25, y: 2.6, w: 2.48, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 32, bold: true, color: C.tool, align: "center" });
  sl.addText("表头写法进回归\n1.35 t 必须落成 1350 kg", { x: M + 9.4, y: 3.3, w: 2.18, h: 0.8, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, color: C.tool, align: "center", lineSpacingMultiple: 1.25 });

  rule(sl, M, 5.1, W - 2 * M, C.line);
  sl.addText("今天报的每一个数，都是这个问题修完之后重跑的", { x: M, y: 5.32, w: 8.6, h: 0.36, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 15, bold: true, color: C.ink });
  sl.addText("修之前那些依赖重量口径的旧数字，今天一个都不拿来用", { x: M, y: 5.7, w: 8.6, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted });
  chip(sl, "git 53a550e · test_table_mapper_unit.py", M + 8.9, 5.4, 2.83, false);
  notes(sl, 7);
}

// ============================== 8. 够不着 ==============================
{
  const sl = light(8, "机制 · 权限");
  sl.addText("模型能碰到的东西被按死在 8 个工具里，出稿那一步连自由文本都没有", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  const tools = ["列步骤", "读岗位 SOP", "查岗位知识库", "列资料", "读资料", "让岗位出稿", "跑装箱引擎", "跑招标对照"];
  tools.forEach((t, i) => {
    const col = i % 4, row = Math.floor(i / 4);
    const x = M + col * 1.85, y = 2.05 + row * 0.78;
    const key = t === "让岗位出稿";
    card(sl, { x, y, w: 1.68, h: 0.6, border: key ? C.human : C.line, borderW: key ? 2 : 1, flat: true,
      fill: key ? C.humanSoft : C.white });
    sl.addText(t, { x, y, w: 1.68, h: 0.6, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 11.5, bold: key, color: key ? C.human : C.text, align: "center", valign: "middle" });
  });
  sl.addText("「让岗位出稿」入参只有 skill_id 与文件名 —— 没有自由文本，模型写的字进不了成稿", {
    x: M, y: 3.68, w: 7.2, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, color: C.human, lineSpacingMultiple: 1.2 });

  // 右侧：改前改后
  card(sl, { x: M + 7.6, y: 2.05, w: 4.13, h: 3.3 });
  sl.addText("改前 → 现在", { x: M + 7.9, y: 2.25, w: 3.5, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.faint, charSpacing: 2 });
  const metrics = [["任务意图", "0.718", "1.000"], ["数字出处", "0.729", "1.000"], ["结论护栏（留出集）", "0.692", "0.900"]];
  metrics.forEach((m, i) => {
    const y = 2.68 + i * 0.78;
    sl.addText(m[0], { x: M + 7.9, y, w: 2.0, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12, color: C.text, valign: "middle" });
    sl.addText(m[1], { x: M + 9.85, y, w: 0.8, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.m, fontSize: 12, color: C.grey, valign: "middle", strike: true });
    sl.addText("→", { x: M + 10.6, y, w: 0.4, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 11, color: C.grey, valign: "middle", align: "center" });
    sl.addText(m[2], { x: M + 11.0, y, w: 0.85, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 15, bold: true, color: C.tool, valign: "middle" });
  });
  sl.addText("守卫是确定性代码，不计作模型理解正确", { x: M + 7.9, y: 4.95, w: 3.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.muted });

  rule(sl, M, 4.6, 7.2, C.line);
  sl.addText("拿掉数字溯源这一道检查：结论护栏从 0.900 掉到 0.692", { x: M, y: 4.82, w: 7.2, h: 0.36, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 14.5, bold: true, color: C.ink });
  sl.addText("三道门是互相撑着的，不是堆在一起好看", { x: M, y: 5.2, w: 7.2, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted });
  chip(sl, "model_loop.py · eval_task_intent.py · eval_number_provenance.py", M, 5.68, 6.4, false);
  notes(sl, 8);
}

// ============================== 9. 人说了算 ==============================
{
  const sl = light(9, "机制 · 人确认");
  sl.addText("不是弹个提示让人点一下，是人不确认、下一段根本不开始", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  card(sl, { x: M, y: 2.2, w: 2.9, h: 1.7 });
  sl.addText("成箱方案", { x: M, y: 2.2, w: 2.9, h: 1.7, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 17, bold: true, color: C.ink, align: "center", valign: "middle" });

  // 闸门
  sl.addShape(pres.ShapeType.rect, { x: M + 3.25, y: 2.0, w: 0.14, h: 2.1, fill: { color: C.amber }, line: { type: "none" } });
  sl.addShape(pres.ShapeType.roundRect, { x: M + 2.85, y: 2.75, w: 0.95, h: 0.62, rectRadius: 0.08,
    fill: { color: C.amber }, line: { type: "none" } });
  sl.addText("锁", { x: M + 2.85, y: 2.75, w: 0.95, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 15, bold: true, color: C.ink, align: "center", valign: "middle" });
  sl.addText("人确认柜型", { x: M + 2.5, y: 4.18, w: 1.7, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.amberDeep, align: "center" });

  card(sl, { x: M + 4.2, y: 2.2, w: 2.9, h: 1.7, fill: "E8ECF0", border: C.grey, flat: true });
  sl.addText("拼柜", { x: M + 4.2, y: 2.2, w: 2.9, h: 1.7, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 17, bold: true, color: C.grey, align: "center", valign: "middle" });
  sl.addShape(pres.ShapeType.roundRect, { x: M + 4.55, y: 3.28, w: 2.2, h: 0.46, rectRadius: 0.06,
    fill: { color: C.white }, line: { color: C.danger, width: 1.5 } });
  sl.addText("未确认 · 不能进入", { x: M + 4.55, y: 3.28, w: 2.2, h: 0.46, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, bold: true, color: C.danger, align: "center", valign: "middle" });

  // 手打确认句
  card(sl, { x: M + 7.6, y: 2.2, w: 4.13, h: 1.7, fill: C.white, border: C.human, borderW: 1.5 });
  sl.addText("高风险写盘：必须手打这一句", { x: M + 7.9, y: 2.4, w: 3.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.human });
  sl.addShape(pres.ShapeType.rect, { x: M + 7.9, y: 2.82, w: 3.55, h: 0.6, fill: { color: "F7F9FB" }, line: { color: C.line, width: 1 } });
  sl.addText("我明白，将由持证人员签认", { x: M + 8.0, y: 2.82, w: 3.35, h: 0.6, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 13, color: C.text, valign: "middle" });
  sl.addText("一个字一个字敲，不是点按钮", { x: M + 7.9, y: 3.5, w: 3.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, color: C.muted });

  rule(sl, M, 4.72, W - 2 * M, C.line);
  const pts = [["人点拒绝", "下一段被挡住，不是提示一下就过"], ["不可递交", "写在工具的输出格式里，不是文案"]];
  pts.forEach((p, i) => {
    const x = M + i * 6.1;
    sl.addText(p[0], { x, y: 4.95, w: 5.7, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 15, bold: true, color: C.ink });
    sl.addText(p[1], { x, y: 5.3, w: 5.7, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12, color: C.muted });
  });
  chip(sl, "submit_blocked: {\"const\": true} · tool_contracts.py", M, 5.78, 5.6, false);
  notes(sl, 9);
}

// ============================== 10. 人管口径 ==============================
{
  const sl = light(10, "人机协同");
  sl.addText("分工不是谁听谁的：口径与边界归人，实现与回归归 AI", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  const cols = [
    { t: "人", c: C.human, items: ["做什么、不做什么", "数字从哪来", "结论谁下", "口径拍板与验收"] },
    { t: "AI", c: C.tool, items: ["实现与回归", "子代理审查", "逐条复跑取证", "把纠偏写成门禁"] },
  ];
  cols.forEach((col, i) => {
    const x = M + i * 2.6;
    card(sl, { x, y: 2.1, w: 2.35, h: 2.9 });
    sl.addShape(pres.ShapeType.ellipse, { x: x + 0.9, y: 2.32, w: 0.55, h: 0.55, fill: { color: col.c }, line: { type: "none" } });
    sl.addText(col.t, { x: x + 0.9, y: 2.32, w: 0.55, h: 0.55, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 16, bold: true, color: C.white, align: "center", valign: "middle" });
    col.items.forEach((t, k) => {
      sl.addText("· " + t, { x: x + 0.22, y: 3.08 + k * 0.42, w: 1.95, h: 0.34, isTextBox: true, margin: 0,
        fontFace: F.b, fontSize: 11.5, color: C.text });
    });
  });

  const nodes = [
    ["发现", "队友两个已合并 PR 全绿，可 CI 一个验收脚本都没引用", C.danger],
    ["沉淀", "新门禁逐个起独立进程跑，找到的脚本少于 12 个直接红", C.amber],
    ["守住", "项目门禁 69 项，2026-09-20 全绿 69/69", C.tool],
  ];
  nodes.forEach((n, i) => {
    const y = 2.1 + i * 1.02;
    sl.addShape(pres.ShapeType.ellipse, { x: M + 5.55, y: y + 0.18, w: 0.42, h: 0.42, fill: { color: n[2] }, line: { type: "none" } });
    sl.addText(String(i + 1), { x: M + 5.55, y: y + 0.18, w: 0.42, h: 0.42, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
    if (i < 2) vrule(sl, M + 5.75, y + 0.62, 0.58, C.line);
    sl.addText(n[0], { x: M + 6.2, y: y + 0.12, w: 1.2, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 14, bold: true, color: C.ink });
    sl.addText(n[1], { x: M + 6.2, y: y + 0.45, w: 5.4, h: 0.4, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12, color: C.muted });
  });

  rule(sl, M, 5.3, W - 2 * M, C.line);
  sl.addText("履历表 15 段，每段挂提交哈希：人发现什么 → AI 做了什么 → 沉淀成哪道还在拦人的门", {
    x: M, y: 5.52, w: 8.6, h: 0.36, isTextBox: true, margin: 0, fontFace: F.t, fontSize: 14.5, bold: true, color: C.ink });
  chip(sl, "docs/submission/haizizhi-resume.md", M + 8.9, 5.56, 2.83, false);
  notes(sl, 10);
}

// ============================== 11. 招标逐行比对 ==============================
{
  const sl = light(11, "投标岗");
  sl.addText("同一套纪律搬到投标岗：一条招标要求，只出一行；数字对不上，当场标出来", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  card(sl, { x: M, y: 2.05, w: 5.4, h: 2.75, fill: "EFF1F4", border: C.line, flat: true });
  sl.addText("基线", { x: M + 0.3, y: 2.25, w: 2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.faint, charSpacing: 2 });
  sl.addText("同一条要求下面挂了三行重复响应", { x: M + 0.3, y: 2.6, w: 4.8, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, color: C.text });
  [0, 1, 2].forEach((k) => {
    sl.addShape(pres.ShapeType.rect, { x: M + 0.3, y: 3.05 + k * 0.4, w: 4.8, h: 0.3, fill: { color: "E2E6EA" }, line: { type: "none" } });
  });
  sl.addText("？ 数值冲突未被发现", { x: M + 0.42, y: 3.45, w: 3, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11, bold: true, color: C.grey, valign: "middle" });
  sl.addText("每条要求 1.316 行 · 召回 0.615", { x: M + 0.3, y: 4.35, w: 4.8, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.m, fontSize: 10.5, color: C.muted });

  card(sl, { x: M + 6.0, y: 2.05, w: 5.73, h: 2.75 });
  sl.addText("现在", { x: M + 6.3, y: 2.25, w: 2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.tool, charSpacing: 2 });
  sl.addText("一条要求 → 一行，并指出数字冲突", { x: M + 6.3, y: 2.6, w: 5.1, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, color: C.text });
  sl.addShape(pres.ShapeType.rect, { x: M + 6.3, y: 3.05, w: 5.1, h: 0.34, fill: { color: "EDF1F5" }, line: { type: "none" } });
  sl.addText("招标：工期 60 日历天", { x: M + 6.42, y: 3.05, w: 2.5, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, color: C.text, valign: "middle" });
  sl.addText("投标：90 天", { x: M + 9.0, y: 3.05, w: 1.6, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 11.5, bold: true, color: C.danger, valign: "middle" });
  sl.addShape(pres.ShapeType.roundRect, { x: M + 6.3, y: 3.55, w: 2.5, h: 0.42, rectRadius: 0.06,
    fill: { color: "FDF6E6" }, line: { color: C.amber, width: 1.25 } });
  sl.addText("待人工核验", { x: M + 6.3, y: 3.55, w: 2.5, h: 0.42, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.amberDeep, align: "center", valign: "middle" });
  sl.addText("系统只标冲突，合规结论仍由人下", { x: M + 6.3, y: 4.15, w: 5.1, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, color: C.muted });
  sl.addText("每条要求 1.000 行", { x: M + 6.3, y: 4.5, w: 5.1, h: 0.28, isTextBox: true, margin: 0,
    fontFace: F.m, fontSize: 10.5, color: C.muted });

  const stats = [["0.980", "链接召回（基线 0.615）"], ["1.000", "链接精确率"], ["14 / 14", "数字冲突全检出"]];
  stats.forEach((s, i) => {
    const x = M + i * 4.0;
    sl.addText(s[0], { x, y: 5.05, w: 3.7, h: 0.6, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 30, bold: true, color: C.tool });
    sl.addText(s[1], { x, y: 5.66, w: 3.7, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 11.5, color: C.muted });
  });
  chip(sl, "eval_tender_response_match.py · 现行 19 例 · 召回 0.980 · 冲突 14/14 · 51 条金标链接", M, 6.15, 8.6, false);
  notes(sl, 11);
}

// ============================== 12. 工友侧 ==============================
{
  const sl = light(12, "主题 · 为工友谋幸福");
  sl.addText("已经做出来的只有一件：一页三分钟的班前口播稿", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  // 手机卡
  card(sl, { x: M, y: 2.05, w: 3.1, h: 3.9, border: C.ink, borderW: 1.5 });
  const rows12 = [
    ["今天干什么", "工序 · 部位 · 时间"],
    ["哪儿会掉、会砸、会淹", "临边 · 洞口 · 吊装半径"],
    ["三步怎么干", "每步一句，不超过十个字"],
    ["谁喊停、找谁", "任何人可喊停 · 值班电话"],
  ];
  rows12.forEach((r, i) => {
    sl.addText(r[0], { x: M + 0.25, y: 2.35 + i * 0.85, w: 2.6, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 14.5, bold: true, color: C.ink });
    sl.addText(r[1], { x: M + 0.25, y: 2.72 + i * 0.85, w: 2.6, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 11, color: C.muted });
  });

  // 中新分栏
  card(sl, { x: M + 3.55, y: 2.05, w: 4.3, h: 1.85 });
  sl.addText("工资条例要点 · 中新分栏", { x: M + 3.8, y: 2.25, w: 3.8, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.faint });
  sl.addText("中国", { x: M + 3.8, y: 2.62, w: 1.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 13.5, bold: true, color: C.ink });
  sl.addText("保障农民工工资\n支付条例（724 号令）", { x: M + 3.8, y: 2.92, w: 1.8, h: 0.7, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 10.5, color: C.muted, lineSpacingMultiple: 1.2 });
  vrule(sl, M + 5.75, 2.6, 1.05, C.line);
  sl.addText("新加坡", { x: M + 5.95, y: 2.62, w: 1.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 13.5, bold: true, color: C.ink });
  sl.addText("MOM · TADM", { x: M + 5.95, y: 2.92, w: 1.8, h: 0.7, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 10.5, color: C.muted });
  sl.addShape(pres.ShapeType.roundRect, { x: M + 5.9, y: 2.2, w: 1.85, h: 0.34, rectRadius: 0.05,
    fill: { color: C.dangerSoft }, line: { type: "none" } });
  sl.addText("两栏禁止静默混用", { x: M + 5.9, y: 2.2, w: 1.85, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 10.5, bold: true, color: C.danger, align: "center", valign: "middle" });

  // 未交付
  card(sl, { x: M + 8.1, y: 2.05, w: 3.63, h: 1.85, fill: "EFF1F4", border: C.line, flat: true });
  sl.addText("设想 · 未交付", { x: M + 8.35, y: 2.25, w: 3, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.grey, charSpacing: 2 });
  ["一屏一句交底卡", "拍照判停", "匿名权益问答", "老师傅手艺沉淀"].forEach((t, i) => {
    const x = M + 8.35 + (i % 2) * 1.6, y = 2.65 + Math.floor(i / 2) * 0.5;
    sl.addShape(pres.ShapeType.roundRect, { x, y, w: 1.5, h: 0.38, rectRadius: 0.05,
      fill: { color: C.white }, line: { color: C.line, width: 1 } });
    sl.addText(t, { x, y, w: 1.5, h: 0.38, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 9.5, color: C.muted, align: "center", valign: "middle" });
  });

  card(sl, { x: M + 3.55, y: 4.1, w: 8.18, h: 1.85, fill: C.ink, border: C.ink });
  sl.addText("我们不做的", { x: M + 3.85, y: 4.3, w: 3, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: "6E889E", charSpacing: 2 });
  sl.addText("不做情绪识别，不做行为监控打分", { x: M + 3.85, y: 4.65, w: 7.6, h: 0.45, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 22, bold: true, color: C.white });
  sl.addText("工友侧的东西只帮人把话说清楚，不用来评判人", { x: M + 3.85, y: 5.2, w: 7.6, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12.5, color: "9FB3C8" });
  chip(sl, "docs/submission/创意材料-工友侧.md", M, 6.15, 3.1, false);
  notes(sl, 12);
}

// ============================== 13. 66 岗分三级 ==============================
{
  const sl = light(13, "完成度 · 自评");
  sl.addText("宽度是路线图，深度才是可复跑证据", {
    x: M, y: 1.45, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 14, color: C.muted });

  const ladder = [
    ["L1 知识库草稿", "66 / 66", 6.4, C.grey],
    ["L2 工具写盘", "36 / 66", 5.1, C.human],
    ["L3 全链路引擎", "1 岗", 3.9, C.tool],
  ];
  ladder.forEach((l, i) => {
    const y = 4.72 - i * 1.02;
    card(sl, { x: M, y, w: l[2], h: 0.86, border: l[3], borderW: 1.5 });
    sl.addText(l[0], { x: M + 0.26, y, w: l[2] - 1.75, h: 0.86, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 14, bold: true, color: C.ink, valign: "middle" });
    sl.addText(l[1], { x: M + l[2] - 1.45, y, w: 1.2, h: 0.86, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 15, bold: true, color: l[3], align: "right", valign: "middle" });
  });
  sl.addText("L3 是 pack-ship 装柜岗 —— 不宣称 66 岗全部深度落地", { x: M, y: 5.72, w: 6.2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 12, color: C.muted });

  // 记分卡
  card(sl, { x: M + 7.0, y: 1.95, w: 4.73, h: 3.95, border: C.amber, borderW: 1.75 });
  sl.addShape(pres.ShapeType.rect, { x: M + 7.0, y: 1.95, w: 4.73, h: 0.42, fill: { color: "FDF6E6" }, line: { type: "none" } });
  sl.addText("仓内校准自评口径，不是评审结论", { x: M + 7.0, y: 1.95, w: 4.73, h: 0.42, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: C.amberDeep, align: "center", valign: "middle" });
  sl.addText("8.85", { x: M + 7.3, y: 2.5, w: 2.4, h: 1.0, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 54, bold: true, color: C.ink });
  sl.addText("8.90", { x: M + 9.8, y: 2.95, w: 1.0, h: 0.4, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 20, color: C.grey, strike: true, valign: "middle" });
  sl.addText("自己封顶", { x: M + 10.7, y: 3.0, w: 1.0, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 10.5, color: C.grey, valign: "middle" });
  const gates = [["赢线", "PASS", C.tool], ["冲刺线", "FAIL", C.danger]];
  gates.forEach((g, i) => {
    const y = 3.75 + i * 0.62;
    sl.addText(g[0], { x: M + 7.3, y, w: 1.4, h: 0.4, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 13, color: C.text, valign: "middle" });
    sl.addShape(pres.ShapeType.roundRect, { x: M + 8.7, y: y + 0.04, w: 1.3, h: 0.34, rectRadius: 0.05,
      fill: { color: g[2] }, line: { type: "none" } });
    sl.addText(g[1], { x: M + 8.7, y: y + 0.04, w: 1.3, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F.t, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle" });
  });
  sl.addText("冲刺线是我们自己判的 FAIL：基线只跑了 quick，n=12", {
    x: M + 7.25, y: 5.0, w: 4.3, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, color: C.muted, lineSpacingMultiple: 1.2 });
  chip(sl, "eval_competition_scorecard.py --skip-phase0", M, 6.15, 4.6, false);
  notes(sl, 13);
}

// ============================== 14. 收口 ==============================
{
  const sl = pres.addSlide();
  sl.background = { color: C.ink };
  sl.addText("推得开，也收得住", { x: M, y: 0.62, w: 8, h: 0.66, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 31, bold: true, color: C.white });

  ["某局周报格式", "某公司联系单", "内部口径"].forEach((t, i) => {
    const x = M + i * 2.3;
    sl.addShape(pres.ShapeType.roundRect, { x, y: 1.72, w: 2.1, h: 0.72, rectRadius: 0.07,
      fill: { color: C.inkSoft }, line: { color: C.inkLine, width: 1 } });
    sl.addText(t, { x, y: 1.72, w: 2.1, h: 0.72, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12, color: "9FB3C8", align: "center", valign: "middle" });
  });
  sl.addText("→", { x: M + 6.95, y: 1.85, w: 0.7, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 20, bold: true, color: C.amber, align: "center", valign: "middle" });
  sl.addShape(pres.ShapeType.roundRect, { x: M + 7.8, y: 1.6, w: 3.93, h: 0.96, rectRadius: 0.07,
    fill: { color: C.amber }, line: { type: "none" } });
  sl.addText("一个文件夹装进来，就是一批新岗位", { x: M + 7.8, y: 1.6, w: 3.93, h: 0.96, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 14.5, bold: true, color: C.ink, align: "center", valign: "middle" });
  sl.addText("插件里只有 SOP、表单模板、知识摘录 —— 不含代码，装它不会执行任何东西", {
    x: M, y: 2.62, w: 11.7, h: 0.3, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 12, color: "6E889E" });

  rule(sl, M, 3.35, W - 2 * M, C.danger, 0.03);
  sl.addText("红线", { x: M, y: 3.5, w: 1.5, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F.b, fontSize: 11.5, bold: true, color: "FF8E85", charSpacing: 2 });
  const lines = ["不出签认件", "不代交官方系统", "不承诺中标率", "不编条款单价坐标", "不做行为监控打分"];
  lines.forEach((t, i) => {
    sl.addText("✕  " + t, { x: M + i * 2.36, y: 3.86, w: 2.3, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F.b, fontSize: 12, color: "C8D6E2" });
  });

  sl.addText("我们不保证模型不出错，", { x: 0, y: 4.75, w: W, h: 0.55, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 26, bold: true, color: "9FB3C8", align: "center" });
  sl.addText("我们保证错的走不出这道门。", { x: 0, y: 5.35, w: W, h: 0.7, isTextBox: true, margin: 0,
    fontFace: F.t, fontSize: 34, bold: true, color: C.amber, align: "center" });

  rule(sl, M, 6.45, W - 2 * M, C.inkLine, 0.015);
  sl.addText("Civil Buddy · 团队 Mintang · github.com/LUOaini1213/civil-buddy", {
    x: M, y: 6.62, w: 9, h: 0.3, isTextBox: true, margin: 0, fontFace: F.b, fontSize: 11, color: "6E889E" });
  notes(sl, 14);
}

const outFile = path.join(ROOT, "output", "submission", "05-复赛答辩PPT-CivilBuddy.pptx");
pres.writeFile({ fileName: outFile }).then((f) => console.log("写出:", f));
