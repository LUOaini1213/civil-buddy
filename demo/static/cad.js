const CONFIRMATION = '我明白，将由持证人员签认';
const ROLES = { wall: '墙体', column: '柱子', slab: '楼板', section: '截面', ignore: '忽略' };
const COLORS = { wall: '#8dcad8', column: '#52dbc3', slab: '#8aa4c5', section: '#52dbc3', ignore: '#708296' };
const clone = (value) => JSON.parse(JSON.stringify(value));

export function sameConfig(a, b) {
  const ordered = (value) => Array.isArray(value) ? value.map(ordered) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, ordered(value[key])])) : value;
  return JSON.stringify(ordered(a)) === JSON.stringify(ordered(b));
}

/** Requests are tied to a document generation. A late response may never replace a new file. */
export class CadState {
  constructor() { this.sequence = 0; this.reset(); }
  reset() { this.sequence += 1; this.document = null; this.documentId = null; this.model = null; this.modelId = null; this.appliedConfig = null; this.config = null; this.history = []; this.busy = false; this.selectedId = null; this.project = null; this.savedConfig = null; this.savedModelId = null; this.projectName = ''; this.savedName = ''; }
  begin() { this.busy = true; return ++this.sequence; }
  isCurrent(token) { return token === this.sequence; }
  finish(token) { if (this.isCurrent(token)) this.busy = false; }
  setDocument(token, payload, config) {
    if (!this.isCurrent(token)) return false;
    this.document = payload.document; this.documentId = payload.document_id; this.config = clone(config);
    return true;
  }
  setModel(token, payload, config, undo = false) {
    if (!this.isCurrent(token)) return false;
    if (undo) this.history.pop();
    else if (this.appliedConfig && !sameConfig(this.appliedConfig, config)) this.history.push(clone(this.appliedConfig));
    this.model = payload.model; this.modelId = payload.model_id;
    this.appliedConfig = clone(config); this.config = clone(config);
    return true;
  }
  get dirty() { return !this.appliedConfig || !sameConfig(this.config, this.appliedConfig); }
  get canExport() { return !!(this.modelId && this.model?.objects?.length && !this.dirty && !this.busy); }
  get projectDirty() { return !this.project || !sameConfig(this.config, this.savedConfig) || this.modelId !== this.savedModelId || this.projectName.trim() !== this.savedName; }
  setProject(token, payload, historical = false) {
    if (!this.isCurrent(token)) return false;
    this.document = payload.document; this.documentId = payload.document_id;
    this.model = payload.model || null; this.modelId = payload.model_id || null;
    this.config = clone(payload.draft_config); this.appliedConfig = payload.applied_config ? clone(payload.applied_config) : null;
    this.project = clone(payload.project); this.projectName = payload.project.name; this.savedName = payload.project.name;
    this.savedConfig = historical ? null : clone(payload.draft_config); this.savedModelId = historical ? null : this.modelId;
    this.history = []; this.selectedId = null;
    return true;
  }
}

export function validateConfig(config) {
  if (!['mm', 'cm', 'm', 'in', 'ft'].includes(config.unit)) return '请先确认图纸坐标单位。';
  if (!config.confirmed_solid) return '请确认所选闭合轮廓是实体区域，同层内圈表示孔洞。';
  const tolerance = config.curve_tolerance_mm === undefined ? .1 : config.curve_tolerance_mm;
  if (!Number.isFinite(tolerance) || tolerance < .001 || tolerance > 10) return '曲线弦高误差必须为 0.001 至 10 毫米。';
  const roles = [...new Set(Object.values(config.layers).filter((role) => role !== 'ignore'))];
  if (!roles.length) return '请至少选择一个需要建模的图层。';
  for (const role of roles) {
    const param = config.parameters[role];
    if (!param || !Number.isFinite(param.height_m) || param.height_m <= 0) return `请填写${ROLES[role] || role}的有效${role === 'section' ? '拉伸长度' : role === 'slab' ? '厚度' : '高度'}（大于 0 米）。`;
    if (!Number.isFinite(param.base_m)) return `请填写${ROLES[role] || role}的有效底部标高。`;
  }
  for (const [id, values] of Object.entries(config.overrides || {})) {
    if (Object.hasOwn(values, 'height_m') && (!Number.isFinite(values.height_m) || values.height_m <= 0)) return `请填写实体 ${id} 的有效高度 / 长度。`;
    if (Object.hasOwn(values, 'base_m') && !Number.isFinite(values.base_m)) return `请填写实体 ${id} 的有效底部标高。`;
  }
  return '';
}

export function responseError(payload, status) {
  const detail = payload.detail;
  const message = typeof payload.error === 'string' ? payload.error : payload.error?.message || (typeof detail === 'string' ? detail : detail?.message) || payload.message || `请求失败（HTTP ${status}）。`;
  const error = new Error(message);
  error.status = status;
  error.report = Array.isArray(detail?.report) ? detail.report : null;
  return error;
}

export function defaultConfig(document, mode = 'building', example = false) {
  const roles = mode === 'building' ? ['wall', 'column', 'slab'] : ['section'];
  const layers = Object.create(null);
  for (const layer of document.layers || []) layers[layer.name] = roles.includes(layer.suggested_role) ? layer.suggested_role : 'ignore';
  const parameters = Object.create(null);
  for (const role of ['wall', 'column', 'slab', 'section']) parameters[role] = { height_m: example ? ({ wall: 3, column: 3, slab: .12, section: 6 })[role] : null, base_m: 0 };
  return { mode, unit: example ? 'mm' : '', layers, parameters, overrides: {}, confirmed_solid: false, curve_tolerance_mm: .1 };
}

export function configChanges(before, after, document = { entities: [] }) {
  const changes = [];
  const add = (label, oldValue, newValue, suffix = '') => {
    if (Object.is(oldValue, newValue)) return;
    const display = (value) => value === null || value === undefined || value === '' ? '待填写' : `${value}${suffix}`;
    changes.push({ label, before: display(oldValue), after: display(newValue) });
  };
  add('图纸单位', before.unit, after.unit);
  add('曲线误差', before.curve_tolerance_mm ?? .1, after.curve_tolerance_mm ?? .1, ' mm');
  for (const layer of new Set([...Object.keys(before.layers || {}), ...Object.keys(after.layers || {})])) add(`图层 ${layer}`, ROLES[before.layers?.[layer]] || '忽略', ROLES[after.layers?.[layer]] || '忽略');
  for (const role of ['wall', 'column', 'slab', 'section']) {
    add(`${ROLES[role]}${role === 'section' ? '长度' : role === 'slab' ? '厚度' : '高度'}`, before.parameters?.[role]?.height_m, after.parameters?.[role]?.height_m, ' m');
    add(`${ROLES[role]}标高`, before.parameters?.[role]?.base_m, after.parameters?.[role]?.base_m, ' m');
  }
  for (const id of new Set([...Object.keys(before.overrides || {}), ...Object.keys(after.overrides || {})])) {
    if (sameConfig(before.overrides?.[id], after.overrides?.[id])) continue;
    const entity = document.entities?.find((item) => item.id === id);
    for (const [key, label] of [['height_m', '高度 / 长度'], ['base_m', '标高']]) {
      const value = (cfg) => Object.hasOwn(cfg.overrides?.[id] || {}, key) ? cfg.overrides[id][key] : cfg.parameters?.[cfg.layers?.[entity?.layer]]?.[key];
      add(`实体 ${id} ${label}`, value(before), value(after), ' m');
    }
  }
  return changes;
}

export function drawingGeometry(entities) {
  const coordinates = [];
  const paths = [];
  for (const entity of entities || []) {
    const points = (entity.points || []).filter((point) => Array.isArray(point) && Number.isFinite(point[0]) && Number.isFinite(point[1]));
    if (points.length < 2) continue;
    for (const point of points) coordinates.push(point);
    const path = points.map(([x, y], index) => `${index ? 'L' : 'M'}${x} ${-y}`).join(' ') + (entity.status === 'ready' ? ' Z' : '');
    paths.push({ entity, path });
  }
  if (!coordinates.length) return { paths: [], viewBox: '0 0 100 100' };
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of coordinates) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, -y); maxY = Math.max(maxY, -y); }
  const span = Math.max(maxX - minX, maxY - minY, 1);
  const padding = span * .09;
  return { paths, viewBox: `${minX - padding} ${minY - padding} ${Math.max(maxX - minX, span * .01) + padding * 2} ${Math.max(maxY - minY, span * .01) + padding * 2}` };
}

export async function startCadApp(doc = document) {
  const $ = (id) => doc.getElementById(id);
  const all = (selector) => [...doc.querySelectorAll(selector)];
  const state = new CadState();
  const namespace = 'http://www.w3.org/2000/svg';
  let requestController = null;
  let viewer = null;
  let capability = null;
  let capabilityChecking = false;
  let modelViewError = false;
  let edgesVisible = true;
  let projectListSequence = 0;
  let projectsLoading = false;
  let projectListError = '';
  let projects = [];
  const queryProjectId = new URLSearchParams(window.location?.search || '').get('project_id');
  let pendingProjectId = /^[a-f0-9]{32}$/i.test(queryProjectId || '') ? queryProjectId : null;
  const parameterInputs = new Map();
  const layerInputs = new Map();
  const svgPaths = new Map();
  const node = (tag, text, className) => { const item = doc.createElement(tag); if (text !== undefined) item.textContent = text; if (className) item.className = className; return item; };
  const notice = (message, kind = '') => { $('notice').textContent = message; $('notice').className = `notice ${kind}`; };
  const numberValue = (input) => input.value.trim() === '' ? null : Number(input.value);
  const errorMessage = (error) => error.name === 'AbortError' ? '操作已取消。' : error.message || '连接失败，请检查服务是否运行后重试。';
  const serviceReady = () => capability?.available === true && !capabilityChecking;

  for (const role of ['wall', 'column', 'slab', 'section']) {
    const row = node('div', undefined, 'parameter-row');
    row.dataset.role = role;
    row.append(node('span', ROLES[role]));
    const height = node('input'); height.type = 'number'; height.step = 'any'; height.min = '0.000001'; height.placeholder = '待填写'; height.setAttribute('aria-label', `${ROLES[role]}${role === 'section' ? '拉伸长度' : role === 'slab' ? '厚度' : '高度'}，米`);
    const base = node('input'); base.type = 'number'; base.step = 'any'; base.value = '0'; base.setAttribute('aria-label', `${ROLES[role]}底部标高，米`);
    row.append(height, base); $('parameterRows').append(row); parameterInputs.set(role, { row, height, base });
    for (const input of [height, base]) input.addEventListener('input', edited);
  }

  function readConfig() {
    const config = state.config ? clone(state.config) : defaultConfig({ layers: [] });
    config.unit = $('drawingUnit').value;
    config.curve_tolerance_mm = numberValue($('curveTolerance'));
    config.confirmed_solid = $('solidConfirmed').checked;
    config.layers = Object.fromEntries([...layerInputs].map(([name, input]) => [name, input.value]));
    config.parameters = Object.fromEntries([...parameterInputs].map(([role, inputs]) => [role, { height_m: numberValue(inputs.height), base_m: numberValue(inputs.base) }]));
    return config;
  }

  function setForm(config) {
    state.config = clone(config);
    $('drawingUnit').value = config.unit || '';
    $('curveTolerance').value = config.curve_tolerance_mm ?? .1;
    $('solidConfirmed').checked = !!config.confirmed_solid;
    for (const [role, fields] of parameterInputs) {
      fields.height.value = config.parameters?.[role]?.height_m ?? '';
      fields.base.value = config.parameters?.[role]?.base_m ?? 0;
    }
    $('modeBuilding').setAttribute('aria-pressed', String(config.mode === 'building'));
    $('modeSection').setAttribute('aria-pressed', String(config.mode === 'section'));
    $('modeHint').textContent = config.mode === 'building' ? '墙、柱、板分别拉伸；请选实体占据的区域，不要把房间边界当成实心墙。' : '截面沿长度方向拉伸，同层内圈保留为贯通孔；长度由你指定。';
    $('heightHeading').textContent = config.mode === 'section' ? '拉伸长度' : '高度 / 厚度';
    $('commandHelp').textContent = config.mode === 'section' ? '例如：把拉伸长度改为 6 米；把选中构件长度改成 2 米。' : '例如：把墙高改成 3.6 米；把柱子标高改为 0.2 米。';
    $('commandInput').placeholder = config.mode === 'section' ? '把拉伸长度改为 6 米' : '把墙高改成 3.6 米';
    renderLayers(); updateParameterRows(); renderDrawing(); refresh();
  }

  function renderLayers() {
    layerInputs.clear(); $('layerList').replaceChildren();
    for (const layer of state.document?.layers || []) {
      const row = node('div', undefined, 'layer-row');
      const role = state.config.layers[layer.name] || 'ignore';
      const name = node('span', layer.name, 'layer-name'); name.style.setProperty('--layer-color', COLORS[role] || COLORS.ignore);
      row.append(name, node('span', String(layer.entity_count), 'layer-count'));
      const input = node('select'); input.setAttribute('aria-label', `${layer.name} 图层用途`);
      for (const key of state.config.mode === 'section' ? ['ignore', 'section'] : ['ignore', 'wall', 'column', 'slab']) {
        const option = node('option', ROLES[key]); option.value = key; input.append(option);
      }
      input.value = role;
      input.addEventListener('change', () => { edited(); updateParameterRows(); name.style.setProperty('--layer-color', COLORS[input.value]); renderDrawing(); });
      row.append(input); $('layerList').append(row); layerInputs.set(layer.name, input);
    }
    if (!layerInputs.size) $('layerList').append(node('p', '这份图纸没有可映射的图层。', 'hint'));
  }

  function updateParameterRows() {
    const mode = state.config?.mode || 'building';
    for (const [role, { row }] of parameterInputs) row.hidden = mode === 'section' ? role !== 'section' : role === 'section';
  }

  function edited() {
    if (!state.document) return;
    state.config = readConfig();
    if (state.model && state.dirty) notice('参数已修改，当前仍显示上次生成的模型。请生成或应用修改后再导出。', 'warn');
    refresh(); renderInspector();
  }

  function refresh() {
    const hasDoc = !!state.document;
    const ready = serviceReady();
    $('cadFile').disabled = !ready;
    $('dropzone').setAttribute('aria-disabled', String(!ready));
    for (const button of all('[data-example]')) button.disabled = !ready;
    $('retryService').disabled = capabilityChecking || state.busy;
    $('accessSubmit').disabled = capabilityChecking || state.busy;
    $('configFields').disabled = !hasDoc || state.busy;
    $('buildModel').disabled = !hasDoc || state.busy || !ready;
    $('buildModel').textContent = state.busy ? '处理中…' : state.model ? '更新三维模型 ↗' : '生成三维模型 ↗';
    $('commandInput').disabled = !hasDoc || state.busy || !ready;
    $('sendCommand').disabled = !hasDoc || state.busy || !ready;
    const canDiscardDraft = !!state.model && state.dirty;
    $('undoChange').disabled = !(canDiscardDraft || state.history.length) || state.busy || (!ready && !canDiscardDraft);
    $('undoChange').title = canDiscardDraft ? '放弃未应用参数，恢复当前模型的参数' : '撤销上一次已生成的修改';
    $('fitView').disabled = !viewer || !state.model?.objects?.length;
    $('toggleEdges').disabled = $('fitView').disabled;
    $('exportConfirmation').disabled = (!state.model && !state.project) || state.busy;
    const confirmed = $('exportConfirmation').value === CONFIRMATION;
    for (const button of all('[data-export]')) button.disabled = !state.canExport || !confirmed || !ready;
    $('exportHint').textContent = !state.model ? '生成模型后可导出' : !ready ? '连接恢复后可导出' : state.dirty ? '参数尚未应用，导出已暂停' : !state.model.objects?.length ? '没有可导出的有效构件' : !confirmed ? '完整输入签认提示后可下载' : '模型及参数与当前预览一致';
    $('modelBadge').hidden = !state.model;
    $('modelBadge').className = `model-badge${state.dirty ? ' stale' : ''}`;
    $('modelBadge').textContent = state.dirty ? '旧模型 · 参数未应用' : `${state.model?.objects?.length || 0} 个几何构件 · 米`;
    $('modelEmpty').hidden = !!state.model?.objects?.length || modelViewError;
    $('fileMeta').hidden = !hasDoc;
    $('projectName').disabled = !hasDoc || state.busy;
    $('saveDraft').disabled = !hasDoc || state.busy || !ready;
    $('saveCopy').disabled = !hasDoc || state.busy || !ready;
    $('saveVersion').disabled = !state.canExport || !ready;
    $('projectPackage').disabled = !ready || state.busy;
    $('recentProjects').disabled = !ready || state.busy || projectsLoading;
    $('refreshProjects').disabled = !ready || state.busy || projectsLoading;
    $('openProject').disabled = !ready || state.busy || !$('recentProjects').value;
    $('projectVersions').disabled = !ready || state.busy || !state.project?.versions?.length;
    $('openVersion').disabled = !ready || state.busy || !$('projectVersions').value;
    $('exportProject').disabled = !ready || state.busy || !state.project || state.projectDirty || !confirmed;
    const agentReady = !!state.project && !state.projectDirty && !state.busy;
    $('agentProjectLink').setAttribute('aria-disabled', String(!agentReady));
    $('agentProjectLink').href = agentReady ? `/?cad_project_id=${encodeURIComponent(state.project.id)}` : '#';
    $('projectStatus').textContent = state.project ? `${state.project.name} · 修订 ${state.project.revision}${state.projectDirty ? ' · 有未保存更改' : ' · 已保存'}` : hasDoc ? '新项目 · 尚未保存' : projectListError || '尚未保存项目';
    doc.body.setAttribute('aria-busy', String(state.busy));
  }

  function renderDrawing() {
    svgPaths.clear(); $('drawingSvg').replaceChildren();
    const geometry = drawingGeometry(state.model?.preview_entities || state.document?.entities);
    $('drawingSvg').setAttribute('viewBox', geometry.viewBox);
    $('drawingEmpty').hidden = !!geometry.paths.length;
    $('entityCount').textContent = state.document ? `${state.document.entities?.length || 0} 个轮廓 / 实体` : '等待图纸';
    for (const { entity, path } of geometry.paths) {
      const element = doc.createElementNS(namespace, 'path');
      element.setAttribute('d', path);
      const color = entity.status === 'ready' ? COLORS[state.config.layers[entity.layer] || 'ignore'] : '#ff9299';
      element.setAttribute('stroke', color); element.setAttribute('fill', color); element.setAttribute('tabindex', '0');
      element.setAttribute('role', 'button'); element.setAttribute('aria-label', `实体 ${entity.id}，图层 ${entity.layer}，${entity.status === 'ready' ? '可建模' : entity.reason || '未支持'}`);
      const title = doc.createElementNS(namespace, 'title'); title.textContent = `${entity.layer} · ${entity.id}${entity.reason ? ` · ${entity.reason}` : ''}`; element.append(title);
      const choose = () => selectEntity(entity.id);
      element.addEventListener('click', choose); element.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(); } });
      $('drawingSvg').append(element); svgPaths.set(entity.id, element);
    }
    highlightSelection();
  }

  function highlightSelection() {
    for (const [id, path] of svgPaths) path.classList.toggle('selected', id === state.selectedId);
  }

  function selectEntity(id) {
    const object = state.model?.objects?.find((item) => item.source_entity_ids?.includes(id));
    // A hole is a boundary of its owning solid, never an independently extrudable
    // component. Both numeric and language edits must address the shell handle.
    state.selectedId = object?.source_entity_ids?.[0] || id;
    viewer?.select(object?.id || null); highlightSelection(); renderInspector();
  }

  function renderInspector() {
    const host = $('objectInspector'); host.replaceChildren();
    const source = state.document?.entities?.find((entity) => entity.id === state.selectedId);
    if (!source) { host.append(node('p', '选择一个二维轮廓或三维构件，查看原始图层、实体编号与建模尺寸。', 'hint')); return; }
    const object = state.model?.objects?.find((item) => item.source_entity_ids?.includes(source.id));
    const list = node('dl');
    const add = (label, value) => list.append(node('dt', label), node('dd', value));
    add('原图实体', source.id); add('来源图层', source.layer); add('实体类型', source.type);
    const blockPaths = [...new Set((source.source_entities || []).filter((item) => item.insert_path?.length).map((item) => item.insert_path.map((block) => `${block.block} (${block.handle})`).join(' → ')))];
    if (blockPaths.length) add('来源块引用', blockPaths.join('；'));
    add('用途', ROLES[state.config.layers[source.layer]] || '忽略');
    if (object) {
      add('模型编号', object.id); add('关联图元', object.source_entity_ids.join(', '));
      add(object.role === 'section' ? '拉伸长度' : object.role === 'slab' ? '厚度' : '高度', `${object.parameters.height_m} m`);
      add('底部标高', `${object.parameters.base_m} m`);
      if (Number.isFinite(object.volume_m3)) add('几何体积', `${Number(object.volume_m3.toPrecision(7))} m³`);
      if (state.dirty) add('应用状态', '显示上次生成值，当前参数尚未应用');
    } else add('状态', source.reason || '尚未生成此构件');
    host.append(list);
    // An inner loop belongs to its shell. Only the shell can receive an object override.
    if (object && object.source_entity_ids[0] === source.id && state.config.layers[source.layer] === object.role) {
      const form = node('form', undefined, 'object-edit');
      const draftParameters = { ...state.config.parameters[object.role], ...state.config.overrides?.[source.id] };
      const heightLabel = node('label', object.role === 'section' ? '长度（米）' : '高度 / 厚度（米）');
      const height = node('input'); height.type = 'number'; height.step = 'any'; height.min = '.000001'; height.required = true; height.value = draftParameters.height_m ?? ''; height.disabled = state.busy || !serviceReady(); heightLabel.append(height);
      const baseLabel = node('label', '标高（米）'); const base = node('input'); base.type = 'number'; base.step = 'any'; base.required = true; base.value = draftParameters.base_m ?? ''; base.disabled = height.disabled; baseLabel.append(base);
      const apply = node('button', '应用'); apply.type = 'submit'; apply.disabled = height.disabled;
      form.append(heightLabel, baseLabel, apply);
      for (const input of [height, base]) input.addEventListener('input', () => {
        if (state.busy || !serviceReady()) return;
        const next = readConfig(); next.overrides = { ...next.overrides, [source.id]: { height_m: numberValue(height), base_m: numberValue(base) } }; state.config = next;
        notice('构件参数已修改，点击应用后更新模型。当前模型仍是上次生成值。', 'warn'); refresh();
      });
      form.addEventListener('submit', (event) => { event.preventDefault(); if (state.busy || !serviceReady()) return; const next = readConfig(); next.overrides = { ...next.overrides, [source.id]: { height_m: numberValue(height), base_m: numberValue(base) } }; setForm(next); build(next); });
      host.append(form);
    }
  }

  function renderReport(latestReport = null) {
    $('reportList').replaceChildren();
    const report = latestReport || state.model?.report || [];
    const counts = { modeled: 0, ignored: 0, failed: 0 };
    for (const item of report) {
      const status = Object.hasOwn(counts, item.status) ? item.status : 'failed'; counts[status] += 1;
      const row = node('div', undefined, 'report-row'); row.append(node('span', ({ modeled: '已处理', ignored: '已忽略', failed: '失败' })[status], `status-${status}`));
      const details = node('div'); details.append(node('strong', `${item.layer || '—'} · ${item.id || '—'}`), node('p', item.reason || (status === 'modeled' ? '已进入几何模型' : ''))); row.append(details); $('reportList').append(row);
    }
    $('reportSummary').textContent = report.length ? `${counts.modeled} 已处理 · ${counts.ignored} 忽略 · ${counts.failed} 失败` : '尚未建模';
    if (!report.length) $('reportList').append(node('p', '成功、忽略和失败的实体会分别列出，孔洞也会保留处理记录。', 'hint'));
    return counts;
  }

  async function serviceFetch(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) {
      capability = null;
      $('accessPanel').hidden = false;
      $('retryService').hidden = false;
      $('serviceStatus').textContent = '需要访问口令';
      $('serviceStatus').className = 'service-status offline';
      refresh(); renderInspector();
    }
    return response;
  }

  async function jsonRequest(url, options = {}) {
    const response = await serviceFetch(url, options);
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('json')) throw new Error(response.ok ? '服务返回了无法识别的数据。' : `建模服务请求失败（HTTP ${response.status}）。`);
    const payload = await response.json();
    if (!response.ok || payload.ok === false) throw responseError(payload, response.status);
    return payload;
  }

  function startRequest() {
    requestController?.abort(); requestController = new AbortController();
    const token = state.begin(); refresh(); renderInspector();
    return { token, signal: requestController.signal };
  }

  function renderVersions() {
    const select = $('projectVersions'); select.replaceChildren();
    const placeholder = node('option', state.project?.versions?.length ? '选择已保存的模型版本' : '尚无已保存版本'); placeholder.value = ''; select.append(placeholder); select.value = '';
    for (const version of [...(state.project?.versions || [])].reverse()) {
      const option = node('option', `版本 ${version.version} · ${version.objects} 个构件 · ${version.created_at}`); option.value = String(version.version); select.append(option);
    }
  }

  async function refreshProjects() {
    if (!serviceReady()) return;
    const sequence = ++projectListSequence; projectsLoading = true; projectListError = ''; refresh();
    try {
      const payload = await jsonRequest('/api/cad/projects', { cache: 'no-store' });
      if (sequence !== projectListSequence) return;
      projects = payload.projects || [];
      const selected = $('recentProjects').value;
      $('recentProjects').replaceChildren();
      const placeholder = node('option', projects.length ? '选择一个已保存项目' : '还没有已保存项目'); placeholder.value = ''; $('recentProjects').append(placeholder);
      for (const project of projects) { const option = node('option', `${project.name} · 修订 ${project.revision}`); option.value = project.id; $('recentProjects').append(option); }
      $('recentProjects').value = projects.some((project) => project.id === selected) ? selected : '';
    } catch (error) {
      if (sequence === projectListSequence) { projectListError = `项目列表读取失败：${errorMessage(error)}`; const option = node('option', projectListError); option.value = ''; $('recentProjects').replaceChildren(option); $('recentProjects').value = ''; }
    } finally { if (sequence === projectListSequence) { projectsLoading = false; refresh(); } }
  }

  function showDocumentDetails() {
    $('filename').textContent = state.document.filename;
    const sourceCount = state.document.layers.reduce((sum, layer) => sum + layer.entity_count, 0);
    $('fileDetails').textContent = `${state.document.layers.length} 个图层 · ${sourceCount} 个来源实体`;
    const unit = state.document.units;
    $('unitHint').textContent = unit?.meters_per_unit ? `原图单位标注：${unit.name}。请选择并确认，避免尺寸缩放错误。` : '原图未提供可确认的单位，请根据实际图纸选择。';
  }

  function showProject(token, payload, historical = false) {
    if (!state.setProject(token, payload, historical)) return false;
    $('cadFile').value = ''; $('projectPackage').value = ''; $('projectName').value = state.project.name;
    $('exportConfirmation').value = ''; $('commandInput').value = ''; $('exampleHint').hidden = true;
    $('commandResult').textContent = '项目已载入。修改只作用于图层选择和建模参数，原图保持不变。';
    renderChanges([], ''); showDocumentDetails(); setForm(state.config); renderVersions();
    try { if (state.model) viewer?.setModel(state.model, true); else viewer?.clear(); }
    catch (error) { showViewerError(`三维显示失败：${errorMessage(error)}。模型数据仍可导出。`); }
    renderReport(); renderInspector(); refresh();
    return true;
  }

  async function openProject(projectId, version = null) {
    if (!projectId || state.busy || !serviceReady()) return;
    const { token, signal } = startRequest(); notice(version ? `正在载入模型版本 ${version}…` : '正在恢复项目原图、草稿与模型…');
    try {
      const query = version ? `?version=${encodeURIComponent(version)}` : '';
      const payload = await jsonRequest(`/api/cad/projects/${encodeURIComponent(projectId)}${query}`, { signal, cache: 'no-store' });
      if (!showProject(token, payload, !!version)) return;
      notice(version ? `已载入版本 ${version}。保存后才会写入项目，现有历史版本保持不变。` : `已恢复项目“${payload.project.name}”。${state.dirty && state.model ? '草稿与上次生成模型分别保留，请应用参数后再导出模型。' : '可以继续修改参数。'}导出时需要重新填写签认提示。`);
    } catch (error) { if (state.isCurrent(token)) notice(`${errorMessage(error)} 当前图纸与模型保持不变。`, 'error'); }
    finally { state.finish(token); if (state.isCurrent(token)) { refresh(); renderInspector(); } }
  }

  async function saveProject(includeModel, newCopy = false) {
    if (!state.document || state.busy || !serviceReady() || (includeModel && !state.canExport)) return;
    const name = $('projectName').value.trim();
    if (!name) { notice('请填写项目名称后保存。', 'warn'); return; }
    const config = readConfig(); state.config = clone(config); state.projectName = name;
    const body = { name, document_id: state.documentId, config };
    if (state.project && !newCopy) { body.project_id = state.project.id; body.expected_revision = state.project.revision; }
    if (includeModel) body.model_id = state.modelId;
    const { token, signal } = startRequest(); notice(includeModel ? '正在保存模型版本与原图…' : '正在保存项目草稿…');
    try {
      const payload = await jsonRequest('/api/cad/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
      if (!state.isCurrent(token)) return;
      state.project = clone(payload.project); state.savedConfig = clone(config); state.savedName = name;
      if (newCopy) state.savedModelId = null;
      if (includeModel) state.savedModelId = state.modelId;
      renderVersions();
      notice(includeModel ? '模型版本已保存。原图、参数和处理报告可在重启后恢复。' : state.modelId !== state.savedModelId ? '草稿已保存。当前模型尚未归档，请点击“保存模型版本”保留本次几何结果。' : '草稿已保存，上次生成的模型版本保持不变。');
      await refreshProjects();
    } catch (error) {
      if (state.isCurrent(token)) notice(error.status === 409 ? '项目已被其他页面修改，本次未覆盖。当前草稿仍在，请另存为新项目，或打开最新项目后重新修改。' : `${errorMessage(error)} 当前草稿仍保留，可重试保存。`, 'error');
    } finally { state.finish(token); if (state.isCurrent(token)) { refresh(); renderInspector(); } }
  }

  async function importProject(file) {
    if (!file || state.busy || !serviceReady()) return;
    if (!/\.zip$/i.test(file.name)) { notice('请选择 CAD 项目 ZIP 包。', 'warn'); return; }
    if (file.size > 16 * 1024 * 1024) { notice('项目包超出 16 MB 上传上限。', 'warn'); return; }
    const { token, signal } = startRequest(); notice('正在检查项目包并创建独立副本…');
    try {
      const form = new FormData(); form.append('file', file);
      const payload = await jsonRequest('/api/cad/projects/import', { method: 'POST', body: form, signal });
      if (!showProject(token, payload)) return;
      notice(`已导入为新项目“${payload.project.name}”。原项目未覆盖；导出签认需要重新输入。`);
      await refreshProjects();
    } catch (error) { if (state.isCurrent(token)) notice(`${errorMessage(error)} 当前图纸与模型保持不变。`, 'error'); }
    finally { state.finish(token); if (state.isCurrent(token)) { $('projectPackage').value = ''; refresh(); renderInspector(); } }
  }

  function download(blob, filename) {
    const url = URL.createObjectURL(blob); const link = node('a'); link.href = url; link.download = filename;
    doc.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  async function exportProject() {
    if (!state.project || state.projectDirty || state.busy || !serviceReady() || $('exportConfirmation').value !== CONFIRMATION) return;
    const { token, signal } = startRequest(); notice('正在打包原图、草稿和模型版本…');
    try {
      const response = await serviceFetch(`/api/cad/projects/${encodeURIComponent(state.project.id)}/export`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmation: $('exportConfirmation').value, expected_revision: state.project.revision }), signal });
      if (!response.ok) throw responseError(await response.json().catch(() => ({})), response.status);
      const blob = await response.blob(); if (!state.isCurrent(token)) return;
      download(blob, `${state.project.name.replace(/[\\/:*?"<>|]/g, '_')}.cad-project.zip`);
      notice('项目包已准备下载。同事导入后会创建独立副本，并重新确认导出签认。');
    } catch (error) { if (state.isCurrent(token)) notice(error.status === 409 ? '项目已有更新，本次未下载旧画面之外的版本。请打开最新项目，核对后重新导出。' : errorMessage(error), 'error'); }
    finally { state.finish(token); if (state.isCurrent(token)) { refresh(); renderInspector(); } }
  }

  function renderChanges(changes, status) {
    $('commandDiff').hidden = !changes.length; $('commandDiffRows').replaceChildren(); $('commandDiffStatus').textContent = status;
    for (const change of changes) { const row = node('div', undefined, 'command-diff-row'); row.append(node('span', change.label), node('span', change.before, 'before'), node('span', '→'), node('span', change.after, 'after')); $('commandDiffRows').append(row); }
  }

  function clear() {
    requestController?.abort(); state.reset(); viewer?.clear();
    $('cadFile').value = ''; $('drawingSvg').replaceChildren(); $('drawingEmpty').hidden = false; $('entityCount').textContent = '等待图纸';
    $('exampleHint').hidden = true; $('exportConfirmation').value = ''; $('commandInput').value = '';
    $('projectName').value = ''; $('projectPackage').value = ''; renderVersions(); renderChanges([], '');
    $('commandResult').textContent = '修改只作用于图层选择、高度、长度和标高；平面轮廓来自原图。';
    layerInputs.clear(); $('layerList').replaceChildren(node('p', '上传后显示图层', 'hint')); svgPaths.clear();
    for (const fields of parameterInputs.values()) { fields.height.value = ''; fields.base.value = '0'; }
    $('drawingUnit').value = ''; $('curveTolerance').value = '.1'; $('solidConfirmed').checked = false;
    renderReport(); renderInspector(); refresh(); notice('先上传 DXF，或选择一个合成样例体验完整流程。');
  }

  async function importFile(file, exampleMode = null) {
    if (!serviceReady()) return;
    if (!file || !/\.dxf$/i.test(file.name)) { notice('请选择 DXF 文件。DWG 请先使用 CAD 软件另存为 DXF。', 'error'); return; }
    if (capability?.max_upload_bytes && file.size > capability.max_upload_bytes) { notice(`文件超出上传上限 ${Math.round(capability.max_upload_bytes / 1024 / 1024)} MB。`, 'error'); return; }
    clear();
    const { token, signal } = startRequest(); notice(`正在读取 ${file.name} 的实体和图层…`);
    try {
      const form = new FormData(); form.append('file', file);
      const payload = await jsonRequest('/api/cad/import', { method: 'POST', body: form, signal });
      const config = defaultConfig(payload.document, exampleMode || 'building', !!exampleMode);
      if (!state.setDocument(token, payload, config)) return;
      state.projectName = (payload.document.filename || file.name).replace(/\.dxf$/i, '').slice(0, 100); $('projectName').value = state.projectName;
      showDocumentDetails();
      $('exampleHint').hidden = !exampleMode;
      setForm(config);
      const rejectedEntities = payload.document.entities.filter((entity) => entity.status !== 'ready');
      const rejected = rejectedEntities.length;
      if (rejected) {
        renderReport(rejectedEntities.map((entity) => ({ id: entity.id, layer: entity.layer, status: 'failed', reason: entity.reason || '无效或暂未支持的原图实体' })));
        $('reportSummary').textContent = `导入检查 · ${rejected} 个未支持 / 无效实体`;
      }
      notice(`已读取图纸。${rejected ? `其中 ${rejected} 个实体无效或暂未支持；` : ''}请确认单位、图层映射、实体区域及尺寸。`, rejected ? 'warn' : '');
    } catch (error) { if (state.isCurrent(token)) notice(errorMessage(error), 'error'); }
    finally { state.finish(token); if (state.isCurrent(token)) refresh(); }
  }

  async function build(config = readConfig(), undo = false, request = null) {
    if (!serviceReady() || (state.busy && !request)) return false;
    const issue = validateConfig(config);
    state.config = clone(config); refresh();
    if (issue) { notice(issue, 'warn'); if (request) { state.finish(request.token); refresh(); } return false; }
    const { token, signal } = request || startRequest();
    notice('正在检查轮廓并计算三维几何…');
    const firstModel = !state.model;
    try {
      const payload = await jsonRequest('/api/cad/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: state.documentId, config }), signal });
      if (!state.setModel(token, payload, config, undo)) return false;
      if (undo) { $('commandResult').textContent = '已撤销，恢复上一次建模参数。'; renderChanges([], ''); }
      try {
        viewer?.setModel(payload.model, firstModel);
        const selected = payload.model.objects?.find((item) => item.source_entity_ids?.includes(state.selectedId));
        viewer?.select(selected?.id || null);
      } catch (error) { showViewerError(`三维显示失败：${errorMessage(error)}。模型数据仍可导出。`); }
      renderDrawing(); const counts = renderReport(); renderInspector();
      if (!payload.model.objects?.length) notice('未生成有效构件，请查看处理记录，修正图层或轮廓后重试。', 'warn');
      else if (counts.failed) notice(`已生成 ${payload.model.objects.length} 个构件，但有 ${counts.failed} 个实体处理失败。请查看记录；当前为部分结果。`, 'warn');
      else notice(`已生成 ${payload.model.objects.length} 个几何构件。可以旋转查看、选择来源或继续修改尺寸。`);
      return true;
    } catch (error) {
      if (state.isCurrent(token)) {
        if (error.report) renderReport(error.report);
        notice(`${errorMessage(error)}${state.model ? ' 当前保留上次生成的模型，本次参数尚未应用。' : ''}`, 'error');
      }
      return false;
    } finally { state.finish(token); if (state.isCurrent(token)) { refresh(); renderInspector(); } }
  }

  async function runCommand(message) {
    if (!message.trim() || state.busy || !state.document || !serviceReady()) return;
    const config = readConfig(); state.config = clone(config);
    renderChanges([], '');
    const request = startRequest(); notice('正在解析参数修改…');
    try {
      const payload = await jsonRequest('/api/cad/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: state.documentId, config, message, selected_id: state.selectedId }), signal: request.signal });
      if (!state.isCurrent(request.token)) return;
      setForm(payload.config);
      $('commandResult').textContent = payload.changes?.length ? payload.changes.join('；') : payload.message || '已解析参数。';
      const changes = configChanges(config, payload.config, state.document); renderChanges(changes, '待应用：正在重新生成几何模型');
      const applied = await build(payload.config, false, request);
      if (state.isCurrent(request.token)) { renderChanges(changes, applied ? '已应用：原值 → 新值，可撤销' : '未应用：当前保留上次生成的模型'); if (applied) $('commandInput').value = ''; }
    } catch (error) { if (state.isCurrent(request.token)) notice(`${errorMessage(error)} 现有模型保持不变。`, 'error'); }
    finally { state.finish(request.token); if (state.isCurrent(request.token)) { refresh(); renderInspector(); } }
  }

  async function loadExample(mode) {
    if (!serviceReady()) return;
    clear(); const { token, signal } = startRequest(); notice('正在载入合成演示图纸…');
    try {
      const response = await serviceFetch(`/api/cad/examples/${mode}`, { signal });
      if (!response.ok) throw new Error(`样例读取失败（HTTP ${response.status}）。`);
      const blob = await response.blob();
      if (!state.isCurrent(token)) return;
      await importFile(new File([blob], `demo-${mode}.dxf`, { type: 'application/dxf' }), mode);
    } catch (error) { if (state.isCurrent(token)) notice(errorMessage(error), 'error'); }
    finally { state.finish(token); if (state.isCurrent(token)) refresh(); }
  }

  async function exportModel(format) {
    if (!state.canExport || !serviceReady() || $('exportConfirmation').value !== CONFIRMATION) return;
    const modelId = state.modelId;
    const { token, signal } = startRequest(); notice('正在准备模型与参数下载…');
    try {
      const response = await serviceFetch('/api/cad/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId, confirmation: $('exportConfirmation').value, format }), signal });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw responseError(payload, response.status);
      }
      const blob = await response.blob(); if (!state.isCurrent(token)) return;
      download(blob, `${(state.document.filename || 'cad-model').replace(/\.dxf$/i, '')}.${format}`);
      notice('已准备下载。参数记录包含原图来源、单位和坐标变换。');
    } catch (error) { if (state.isCurrent(token)) notice(errorMessage(error), 'error'); }
    finally { state.finish(token); if (state.isCurrent(token)) { refresh(); renderInspector(); } }
  }

  function showViewerError(message) { modelViewError = true; $('webglError').textContent = message; $('webglError').hidden = false; $('modelEmpty').hidden = true; }

  $('cadFile').addEventListener('change', (event) => { const file = event.target.files[0]; if (file) importFile(file); });
  const dropzone = $('dropzone');
  for (const type of ['dragenter', 'dragover']) dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.add('dragging'); });
  for (const type of ['dragleave', 'drop']) dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.remove('dragging'); });
  dropzone.addEventListener('drop', (event) => { const file = event.dataTransfer.files[0]; if (file) importFile(file); });
  $('clearFile').addEventListener('click', clear);
  $('projectName').addEventListener('input', () => { state.projectName = $('projectName').value; refresh(); });
  $('saveDraft').addEventListener('click', () => saveProject(false));
  $('saveVersion').addEventListener('click', () => saveProject(true));
  $('saveCopy').addEventListener('click', () => saveProject(state.canExport, true));
  $('recentProjects').addEventListener('change', refresh);
  $('projectVersions').addEventListener('change', refresh);
  $('refreshProjects').addEventListener('click', refreshProjects);
  $('openProject').addEventListener('click', () => openProject($('recentProjects').value));
  $('openVersion').addEventListener('click', () => openProject(state.project?.id, $('projectVersions').value));
  $('projectPackage').addEventListener('change', (event) => { const file = event.target.files[0]; if (file) importProject(file); });
  $('exportProject').addEventListener('click', exportProject);
  $('agentProjectLink').addEventListener('click', (event) => { if (!state.project || state.projectDirty || state.busy) event.preventDefault(); });
  for (const button of all('[data-example]')) button.addEventListener('click', () => loadExample(button.dataset.example));
  for (const button of all('[data-mode]')) button.addEventListener('click', () => {
    if (!state.document || state.busy || state.config.mode === button.dataset.mode) return;
    const next = readConfig(); next.mode = button.dataset.mode;
    for (const layer of state.document.layers) {
      const current = next.layers[layer.name];
      next.layers[layer.name] = current === 'ignore' ? 'ignore' : next.mode === 'section' ? 'section' : ['wall', 'column', 'slab'].includes(layer.suggested_role) ? layer.suggested_role : 'ignore';
    }
    next.overrides = {}; next.confirmed_solid = false; setForm(next); edited();
  });
  $('drawingUnit').addEventListener('change', edited); $('curveTolerance').addEventListener('input', edited); $('solidConfirmed').addEventListener('change', edited);
  $('buildModel').addEventListener('click', () => build());
  $('commandForm').addEventListener('submit', (event) => { event.preventDefault(); runCommand($('commandInput').value); });
  $('undoChange').addEventListener('click', () => {
    if (state.busy) return;
    if (state.model && state.dirty) {
      setForm(clone(state.appliedConfig)); renderInspector(); renderReport();
      $('commandResult').textContent = '已放弃未应用的修改，恢复当前模型的参数。';
      renderChanges([], '');
      notice('已恢复当前模型的参数。');
      return;
    }
    if (!state.history.length || !serviceReady()) return;
    const previous = clone(state.history[state.history.length - 1]); setForm(previous); build(previous, true);
  });
  $('retryService').addEventListener('click', () => loadCapabilities(true));
  $('accessForm').addEventListener('submit', (event) => {
    event.preventDefault();
    if (capabilityChecking || state.busy) return;
    const token = $('accessToken').value.trim();
    if (!token) { notice('请输入访问口令。', 'warn'); return; }
    doc.cookie = `cb_token=${encodeURIComponent(token)}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
    $('accessToken').value = '';
    loadCapabilities(true);
  });
  $('exportConfirmation').addEventListener('input', refresh);
  for (const button of all('[data-export]')) button.addEventListener('click', () => exportModel(button.dataset.export));
  $('fitView').addEventListener('click', () => viewer?.fit());
  $('toggleEdges').addEventListener('click', () => { edgesVisible = !edgesVisible; viewer?.setEdges(edgesVisible); $('toggleEdges').setAttribute('aria-pressed', String(edgesVisible)); });
  window.addEventListener('beforeunload', () => { requestController?.abort(); viewer?.dispose(); });
  updateParameterRows(); refresh();

  // A missing graphics driver never blocks source inspection, parameter entry, or export.
  import('./cad-viewer.js').then(({ CadViewer }) => {
    viewer = new CadViewer($('modelStage'), (object) => { state.selectedId = object?.source_entity_ids?.[0] || null; highlightSelection(); renderInspector(); }, showViewerError);
    if (state.model) viewer.setModel(state.model);
    refresh();
  }).catch(() => showViewerError('当前浏览器无法启动三维查看器（WebGL 或本地显示组件不可用）。仍可检查二维轮廓、生成模型并导出 GLB。'));

  async function loadCapabilities(retry = false) {
    if (capabilityChecking || state.busy) return;
    capabilityChecking = true; refresh(); renderInspector();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      capability = await jsonRequest('/api/cad/capabilities', { signal: controller.signal, cache: 'no-store' });
      const available = capability.available === true;
      $('serviceStatus').textContent = available ? '本地几何工具已就绪' : '建模工具暂不可用';
      $('serviceStatus').className = `service-status ${available ? 'online' : 'offline'}`;
      $('accessPanel').hidden = true;
      $('retryService').hidden = available;
      if (!available) notice(`建模工具缺少依赖：${(capability.missing_dependencies || []).join('、') || '请检查服务配置'}。安装后可点击重新检测。`, 'error');
      else if (retry) notice(state.document ? '连接已恢复，图纸和参数已保留。请继续操作。' : '连接已恢复，可以上传 DXF 或选择演示样例。');
    } catch (error) {
      capability = null;
      $('retryService').hidden = false;
      $('serviceStatus').textContent = error.status === 401 ? '需要访问口令' : '建模服务连接失败';
      $('serviceStatus').className = 'service-status offline';
      notice(error.status === 401 ? '请输入工作台访问口令，再继续使用建模工具。' : error.status === 404 ? '当前服务未提供 CAD 建模工具，请返回工作台。' : error.name === 'AbortError' ? '连接超时，请检查服务后点击重新检测。' : errorMessage(error), 'error');
    } finally { clearTimeout(timer); capabilityChecking = false; refresh(); renderInspector(); }
    if (serviceReady()) {
      await refreshProjects();
      if (pendingProjectId && serviceReady() && !state.busy) { const projectId = pendingProjectId; pendingProjectId = null; if (!state.document) await openProject(projectId); }
    }
  }
  await loadCapabilities();
  return state;
}

if (typeof document !== 'undefined' && document.getElementById('cadFile')) startCadApp();
