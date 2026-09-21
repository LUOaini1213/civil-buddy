#!/usr/bin/env node
'use strict';

// No browser, model endpoint or network is used. These exercise request ownership,
// download gating, undo, and the actual UI handlers with a deliberately tiny DOM.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../demo/static/cad.js'), 'utf8');
const ui = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const html = fs.readFileSync(path.join(__dirname, '../demo/static/cad.html'), 'utf8');
const copy = (value) => JSON.parse(JSON.stringify(value));
const drawing = {
  filename: 'test.dxf', sha256: 'fixture', units: { name: 'Millimeters', meters_per_unit: .001 },
  layers: [{ name: 'WALL', suggested_role: 'wall', entity_count: 2 }],
  entities: [
    { id: 'A', layer: 'WALL', type: 'LWPOLYLINE', status: 'ready', points: [[0, 0], [4000, 0], [4000, 3000], [0, 3000]] },
    { id: 'B', layer: 'WALL', type: 'LWPOLYLINE', status: 'ready', points: [[200, 200], [3800, 200], [3800, 2800], [200, 2800]] },
  ],
};
const model = { objects: [{ id: 'solid-A', layer: 'WALL', role: 'wall', source_entity_ids: ['A', 'B'], parameters: { height_m: 3, base_m: 0 }, vertices: [], faces: [], volume_m3: 7.92 }], report: [{ id: 'A', layer: 'WALL', status: 'modeled', reason: 'solid' }, { id: 'B', layer: 'WALL', status: 'modeled', reason: 'hole boundary' }] };
const documentResponse = { ok: true, document_id: 'drawing-one', document: drawing };
const modelResponse = { ok: true, model_id: 'model-one', model };

test('unit selector has valid option tags for every server-supported coordinate unit', () => {
  const select = /<select id="drawingUnit">([\s\S]*?)<\/select>/.exec(html)[1];
  const options = [...select.matchAll(/<option value="([^"]*)">([^<]+)<\/option>/g)];
  assert.deepEqual(options.map((option) => option[1]), ['', 'mm', 'cm', 'm', 'in', 'ft']);
  assert.equal(select.replace(/<option value="[^"]*">[^<]+<\/option>/g, '').trim(), '');
});

test('real drawings require explicit units, solid confirmation and user dimensions', async () => {
  const { defaultConfig, validateConfig } = await ui;
  const config = defaultConfig(drawing);
  assert.equal(config.unit, '');
  assert.equal(config.parameters.wall.height_m, null);
  assert.match(validateConfig(config), /单位/);
  config.unit = 'mm'; assert.match(validateConfig(config), /确认/);
  config.confirmed_solid = true; assert.match(validateConfig(config), /墙体/);
  config.parameters.wall.height_m = 3; assert.equal(validateConfig(config), '');
  config.overrides.A = { height_m: null }; assert.match(validateConfig(config), /实体 A/);
});

test('defaults never turn unknown or incompatible layers into solid geometry', async () => {
  const { defaultConfig } = await ui;
  const source = { layers: [...drawing.layers, { name: '<script>alert(1)</script>', suggested_role: 'unknown' }, { name: '__proto__', suggested_role: 'section' }] };
  const config = defaultConfig(source, 'section', true);
  assert.equal(config.layers.WALL, 'ignore');
  assert.equal(config.layers['<script>alert(1)</script>'], 'ignore');
  assert.equal(config.layers.__proto__, 'section');
  assert.equal(config.parameters.section.height_m, 6);
  assert.equal(config.confirmed_solid, false);
});

test('switching or clearing a file rejects all late import/build replies', async () => {
  const { CadState, defaultConfig } = await ui;
  const state = new CadState(); const oldRequest = state.begin(); state.reset(); const current = state.begin();
  assert.equal(state.setDocument(oldRequest, documentResponse, defaultConfig(drawing)), false);
  assert.equal(state.setModel(oldRequest, modelResponse, {}), false);
  state.finish(oldRequest); assert.equal(state.busy, true);
  assert.equal(state.setDocument(current, documentResponse, defaultConfig(drawing)), true);
  state.finish(current); assert.equal(state.busy, false); assert.equal(state.model, null);
});

test('a failed rebuild retains geometry but edited or pending parameters block export', async () => {
  const { CadState, defaultConfig } = await ui;
  const state = new CadState(); const config = defaultConfig(drawing, 'building', true); config.confirmed_solid = true;
  const token = state.begin(); state.setDocument(token, documentResponse, config); state.setModel(token, modelResponse, config); state.finish(token);
  assert.equal(state.canExport, true);
  state.config.parameters.wall.height_m = 3.6;
  const failed = state.begin(); assert.equal(state.canExport, false); state.finish(failed);
  assert.equal(state.modelId, 'model-one'); assert.equal(state.model.objects[0].parameters.height_m, 3);
  assert.equal(state.dirty, true); assert.equal(state.canExport, false); assert.equal(state.history.length, 0);
});

test('undo history changes only after a successful model response', async () => {
  const { CadState, defaultConfig } = await ui;
  const state = new CadState(); const first = defaultConfig(drawing, 'building', true); first.confirmed_solid = true;
  let token = state.begin(); state.setModel(token, modelResponse, first); state.finish(token);
  const next = copy(first); next.parameters.wall.height_m = 3.6;
  token = state.begin(); state.setModel(token, { ...modelResponse, model_id: 'model-two' }, next); state.finish(token);
  assert.equal(state.history.length, 1); assert.equal(state.history[0].parameters.wall.height_m, 3);
  state.config = copy(state.history[0]); token = state.begin(); state.finish(token);
  assert.equal(state.history.length, 1); assert.equal(state.modelId, 'model-two'); assert.equal(state.canExport, false);
  token = state.begin(); state.setModel(token, modelResponse, first, true); state.finish(token);
  assert.equal(state.history.length, 0); assert.equal(state.canExport, true);
});

test('unit or layer changes cannot masquerade as an unchanged model', async () => {
  const { sameConfig, defaultConfig } = await ui;
  const first = defaultConfig(drawing, 'building', true); const next = copy(first);
  assert.equal(sameConfig(first, next), true); next.unit = 'm'; assert.equal(sameConfig(first, next), false);
  next.unit = 'mm'; next.layers.WALL = 'ignore'; assert.equal(sameConfig(first, next), false);
});

test('preview retains source coordinates, flips only screen Y and does not close invalid paths', async () => {
  const { drawingGeometry } = await ui;
  const output = drawingGeometry([{ ...drawing.entities[0], points: [[100000, 200000], [100020, 200000], [100020, 200010]] }, { id: 'C', status: 'invalid', points: [[0, 0], [1, 1], [NaN, 2]] }]);
  assert.match(output.paths[0].path, /^M100000 -200000 L100020 -200000 L100020 -200010 Z$/);
  assert.equal(output.paths[1].path, 'M0 0 L1 -1');
  assert.equal(output.viewBox.split(' ').map(Number).every(Number.isFinite), true);
});

test('structured geometry failures retain their per-entity report', async () => {
  const { responseError } = await ui;
  const report = [{ id: 'A', status: 'failed', reason: 'intersecting boundaries' }];
  const error = responseError({ detail: { message: '没有可生成的实体', report } }, 422);
  assert.match(error.message, /没有可生成/); assert.deepEqual(error.report, report);
  assert.equal(responseError({ detail: '图纸已过期' }, 410).message, '图纸已过期');
});

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.dataset = {}; this.value = ''; this.checked = false; this.disabled = false; this.hidden = false; this.textContent = ''; this.style = { setProperty() {} }; this.attributes = {}; const classes = new Set(); this.classList = { add: (...names) => names.forEach((name) => classes.add(name)), remove: (...names) => names.forEach((name) => classes.delete(name)), toggle: (name, on) => on ? classes.add(name) : classes.delete(name) }; }
  set value(value) { this._value = String(value); }
  get value() { return this._value; }
  append(...items) { this.children.push(...items); }
  prepend(...items) { this.children.unshift(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  emit(name, data = {}) { for (const listener of this.listeners[name] || []) listener({ target: this, preventDefault() {}, ...data }); }
  remove() {}
  click() { this.emit('click'); }
}

function dom() {
  const ids = {}, groups = { example: [], mode: [], export: [] };
  for (const match of html.matchAll(/<([a-z]+)\b([^>]*?)>/g)) {
    const id = /\bid="([^"]+)"/.exec(match[2]);
    const element = new Element(match[1]); if (id) ids[id[1]] = element;
    for (const key of Object.keys(groups)) { const data = new RegExp(`data-${key}="([^"]+)"`).exec(match[2]); if (data) { element.dataset[key] = data[1]; groups[key].push(element); } }
  }
  return { ids, groups, body: new Element('body'), createElement: (tag) => new Element(tag), createElementNS: (_, tag) => new Element(tag), getElementById: (id) => ids[id], querySelectorAll: (selector) => groups[/\[data-(\w+)\]/.exec(selector)?.[1]] || [] };
}

const json = (payload, status = 200) => new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
async function waitFor(predicate) { for (let i = 0; i < 100; i++) { if (predicate()) return; await new Promise((resolve) => setImmediate(resolve)); } assert.fail('UI operation did not settle'); }

async function withApp(fetcher, action) {
  const previousFetch = global.fetch, previousWindow = global.window;
  const document = dom(); global.window = { addEventListener() {}, devicePixelRatio: 1 };
  global.fetch = (url, options) => url === '/api/cad/capabilities' ? Promise.resolve(json({ ok: true, available: true })) : fetcher(url, options);
  try { const { startCadApp } = await ui; const state = await startCadApp(document); await action({ document, state }); }
  finally { global.fetch = previousFetch; global.window = previousWindow; }
}

test('actual UI requires confirmation, builds sample and suspends download on a parameter edit', async () => {
  let builds = 0;
  await withApp(async (url) => {
    if (url.includes('/examples/')) return new Response('fixture');
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/build')) { builds++; return json(modelResponse); }
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.groups.example[0].click(); await waitFor(() => state.document && !state.busy);
    doc.ids.buildModel.click(); await waitFor(() => !state.busy); assert.equal(builds, 0); assert.match(doc.ids.notice.textContent, /确认/);
    doc.ids.solidConfirmed.checked = true; doc.ids.solidConfirmed.emit('change'); doc.ids.buildModel.click(); await waitFor(() => !!state.model && !state.busy);
    assert.equal(builds, 1); assert.equal(doc.ids.reportSummary.textContent, '2 已处理 · 0 忽略 · 0 失败');
    doc.ids.exportConfirmation.value = '我明白，将由持证人员签认'; doc.ids.exportConfirmation.emit('input'); assert.equal(doc.groups.export[0].disabled, false);
    const wallHeight = doc.ids.parameterRows.children[0].children[1]; wallHeight.value = '3.6'; wallHeight.emit('input');
    assert.equal(doc.groups.export[0].disabled, true); assert.equal(state.modelId, 'model-one'); assert.match(doc.ids.modelBadge.textContent, /旧模型/);
  });
});

test('actual UI displays a failed build report and keeps the prior model', async () => {
  let builds = 0;
  await withApp(async (url) => {
    if (url.includes('/examples/')) return new Response('fixture');
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/build')) return ++builds === 1 ? json(modelResponse) : json({ detail: { message: '轮廓相交', report: [{ id: 'A', layer: 'WALL', status: 'failed', reason: 'self intersection' }] } }, 422);
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.groups.example[0].click(); await waitFor(() => state.document && !state.busy);
    doc.ids.solidConfirmed.checked = true; doc.ids.solidConfirmed.emit('change'); doc.ids.buildModel.click(); await waitFor(() => state.model && !state.busy);
    const input = doc.ids.parameterRows.children[0].children[1]; input.value = '4'; input.emit('input'); doc.ids.buildModel.click(); await waitFor(() => builds === 2 && !state.busy);
    assert.match(doc.ids.notice.textContent, /轮廓相交/); assert.doesNotMatch(doc.ids.notice.textContent, /object Object/);
    assert.equal(doc.ids.reportSummary.textContent, '0 已处理 · 0 忽略 · 1 失败'); assert.equal(state.modelId, 'model-one'); assert.equal(state.canExport, false);
  });
});

test('actual UI rejects an unknown natural-language instruction without changing parameters', async () => {
  await withApp(async (url) => {
    if (url.includes('/examples/')) return new Response('fixture');
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/command')) return json({ detail: '无法识别完整指令' }, 422);
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.groups.example[0].click(); await waitFor(() => state.document && !state.busy);
    const before = copy(state.config); doc.ids.commandInput.value = '删除全部坐标'; doc.ids.commandForm.emit('submit'); await waitFor(() => !state.busy);
    assert.deepEqual(state.config, before); assert.match(doc.ids.notice.textContent, /无法识别完整指令/);
  });
});

test('ordinary file upload keeps dimensions blank until supplied, with no inactive role requirement', async () => {
  let sentConfig = null;
  await withApp(async (url, options) => {
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/build')) { sentConfig = JSON.parse(options.body).config; return json(modelResponse); }
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.ids.cadFile.files = [new File(['fixture'], 'user-drawing.dxf')]; doc.ids.cadFile.emit('change');
    await waitFor(() => state.document && !state.busy);
    assert.equal(doc.ids.drawingUnit.value, ''); assert.equal(doc.ids.parameterRows.children[0].children[1].value, '');
    doc.ids.drawingUnit.value = 'mm'; doc.ids.drawingUnit.emit('change');
    doc.ids.solidConfirmed.checked = true; doc.ids.solidConfirmed.emit('change');
    doc.ids.buildModel.click(); await waitFor(() => !state.busy); assert.equal(sentConfig, null); assert.match(doc.ids.notice.textContent, /墙体/);
    const height = doc.ids.parameterRows.children[0].children[1]; height.value = '3'; height.emit('input');
    doc.ids.buildModel.click(); await waitFor(() => state.model && !state.busy);
    assert.equal(sentConfig.parameters.wall.height_m, 3); assert.equal(sentConfig.parameters.section.height_m, null);
    assert.equal(sentConfig.layers.WALL, 'wall'); assert.equal(doc.ids.exampleHint.hidden, true);
  });
});

test('clearing the UI during a pending request discards even a server response that ignores abort', async () => {
  let finishBuild;
  await withApp(async (url) => {
    if (url.includes('/examples/')) return new Response('fixture');
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/build')) return new Promise((resolve) => { finishBuild = resolve; });
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.groups.example[0].click(); await waitFor(() => state.document && !state.busy);
    doc.ids.solidConfirmed.checked = true; doc.ids.solidConfirmed.emit('change'); doc.ids.buildModel.click(); await waitFor(() => !!finishBuild);
    doc.ids.clearFile.click(); finishBuild(json(modelResponse)); await new Promise((resolve) => setImmediate(resolve));
    assert.equal(state.document, null); assert.equal(state.model, null); assert.equal(doc.ids.configFields.disabled, true);
    assert.equal(doc.ids.modelBadge.hidden, true); assert.equal(state.canExport, false); assert.match(doc.ids.notice.textContent, /先上传/);
  });
});

test('natural-language parameters rebuild geometry and undo rebuilds the saved configuration', async () => {
  const heights = [];
  await withApp(async (url, options) => {
    if (url.includes('/examples/')) return new Response('fixture');
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/command')) { const next = JSON.parse(options.body).config; next.parameters.wall.height_m = 3.6; return json({ ok: true, config: next, changes: ['墙高改为 3.6 m'] }); }
    if (url.endsWith('/build')) {
      const height = JSON.parse(options.body).config.parameters.wall.height_m; heights.push(height);
      const nextModel = copy(model); nextModel.objects[0].parameters.height_m = height;
      return json({ ...modelResponse, model_id: 'model-' + heights.length, model: nextModel });
    }
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.groups.example[0].click(); await waitFor(() => state.document && !state.busy);
    doc.ids.solidConfirmed.checked = true; doc.ids.solidConfirmed.emit('change'); doc.ids.buildModel.click(); await waitFor(() => state.model && !state.busy);
    doc.ids.commandInput.value = '把墙高改成3.6米'; doc.ids.commandForm.emit('submit'); await waitFor(() => heights.length === 2 && !state.busy);
    assert.equal(state.model.objects[0].parameters.height_m, 3.6); assert.equal(doc.ids.undoChange.disabled, false);
    doc.ids.undoChange.click(); await waitFor(() => heights.length === 3 && !state.busy);
    assert.deepEqual(heights, [3, 3.6, 3]); assert.equal(state.model.objects[0].parameters.height_m, 3); assert.equal(state.history.length, 0);
    assert.equal(doc.ids.commandResult.textContent, '已撤销，恢复上一次建模参数。');
  });
});

test('clicking a modeled hole targets its owning solid for subsequent parameter commands', async () => {
  let selected;
  await withApp(async (url, options) => {
    if (url.includes('/examples/')) return new Response('fixture');
    if (url.endsWith('/import')) return json(documentResponse);
    if (url.endsWith('/build')) return json(modelResponse);
    if (url.endsWith('/command')) {
      const body = JSON.parse(options.body); selected = body.selected_id;
      return json({ ok: true, config: body.config, changes: ['构件高度已更新'] });
    }
    throw Error('unexpected URL ' + url);
  }, async ({ document: doc, state }) => {
    doc.groups.example[0].click(); await waitFor(() => state.document && !state.busy);
    doc.ids.solidConfirmed.checked = true; doc.ids.solidConfirmed.emit('change'); doc.ids.buildModel.click(); await waitFor(() => state.model && !state.busy);
    // Second source entity B is the inner boundary of solid A.
    doc.ids.drawingSvg.children[1].click(); assert.equal(state.selectedId, 'A');
    const numericForm = doc.ids.objectInspector.children.find((item) => item.tagName === 'form');
    assert.ok(numericForm, 'the selected owner exposes its numeric parameter form');
    doc.ids.commandInput.value = '把选中构件高度改为4米'; doc.ids.commandForm.emit('submit'); await waitFor(() => selected !== undefined && !state.busy);
    assert.equal(selected, 'A'); assert.equal(Object.hasOwn(state.config.overrides, 'B'), false);
  });
});
