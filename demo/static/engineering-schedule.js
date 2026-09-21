import Gantt from './vendor/frappe-gantt-1.2.2/frappe-gantt.es.js';
import {GanttGesture} from './engineering-schedule-state.js';

const $ = (id) => document.getElementById(id);
const clone = (value) => JSON.parse(JSON.stringify(value));
const state = {project: null, name: '', tasks: [], saved: '', history: [], editing: null, editorDirty: false, busy: false};
const snapshot = () => ({name: $('planName').value, tasks: clone(state.tasks)});
const dirty = () => state.editorDirty || JSON.stringify(snapshot()) !== state.saved;
const text = (tag, value, className) => {const el = document.createElement(tag); el.textContent = value; if (className) el.className = className; return el;};
const notice = (message, error = false) => {$('notice').textContent = message; $('notice').className = error ? 'error' : '';};
const htmlEscape = (value) => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
let gantt = null;
const gesture = new GanttGesture({read:snapshot,write:(value) => {state.tasks = value.tasks; $('planName').value = value.name;},validate,record:(value) => remember(value)});
let pendingProject = new URLSearchParams(window.location.search).get('project_id');
if (!/^[a-f0-9]{32}$/.test(pendingProject || '')) pendingProject = null;

async function api(path = '', body) {
  const response = await fetch(`/api/engineering/schedules${path}`, {method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', headers: body === undefined ? {} : {'Content-Type':'application/json'}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) { $('accessPanel').hidden = false; throw new Error('需要访问口令。当前编辑已保留，请验证后重试。'); }
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '请求未成功，请检查输入后重试。');
  $('accessPanel').hidden = true;
  return payload;
}
async function action(work) {
  if (state.busy) return;
  state.busy = true; refreshControls();
  try {await work();} catch (error) {notice(error.message || '操作失败，当前编辑已保留。', true);}
  finally {state.busy = false; refreshControls();}
}
function refreshControls() {
  for (const id of ['savePlan','saveCopy','newPlan','loadExample','openPlan','refreshPlans','applyTask','clearEditor']) $(id).disabled = state.busy;
  $('savePlan').disabled ||= state.editorDirty;
  $('saveCopy').disabled ||= state.editorDirty;
  $('undoEdit').disabled = state.busy || !state.history.length;
  $('undoSaved').disabled = state.busy || !state.project?.can_undo || dirty();
  $('taskFields').disabled = state.busy;
  $('planName').disabled = state.busy;
  $('recentPlans').disabled = state.busy;
  $('gantt').style.pointerEvents = state.busy || state.editorDirty ? 'none' : '';
  $('gantt').setAttribute('aria-disabled', String(state.busy || state.editorDirty));
  $('projectStatus').textContent = state.project ? `修订 ${state.project.revision} · ${dirty() ? '有未保存编辑' : '已保存'}` : (state.tasks.length ? '新计划 · 尚未保存' : '尚未保存');
}
function remember(value = snapshot()) {state.history.push(clone(value)); if (state.history.length > 50) state.history.shift();}
function clearEditor() {
  state.editing = null; state.editorDirty = false; $('taskForm').reset(); $('taskId').disabled = false;
  $('editorTitle').textContent = '添加任务'; $('applyTask').textContent = '添加到计划'; refreshControls();
}
function validate(tasks) {
  if (tasks.length > 250) throw new Error('最多保存 250 个任务。');
  const ids = new Set(); const graph = new Map(); const dates = [];
  for (const t of tasks) {
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(t.id) || ids.has(t.id)) throw new Error(`任务编号无效或重复：${t.id}`);
    ids.add(t.id);
    if (!t.name.trim() || t.name.length > 100 || /[\x00-\x1f\x7f]/.test(t.name)) throw new Error('任务名称须为 1–100 字符，不得含控制字符。');
    for (const d of [t.start,t.end]) {
      const parsed = new Date(`${d}T12:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0,10) !== d || +d.slice(0,4) < 1900 || +d.slice(0,4) > 2100) throw new Error('请输入有效日期，年份须在 1900–2100 之间。');
      dates.push(parsed.getTime());
    }
    if (t.end < t.start) throw new Error(`${t.id}：结束日期不能早于开始日期。`);
    if (!Number.isFinite(t.progress) || t.progress < 0 || t.progress > 100) throw new Error('进度须在 0–100 之间。');
    if (new Set(t.dependencies).size !== t.dependencies.length) throw new Error(`${t.id}：依赖编号重复。`);
    graph.set(t.id,t.dependencies);
  }
  if (dates.length && (Math.max(...dates)-Math.min(...dates))/86400000 > 3653) throw new Error('一个计划的总日期跨度最多 10 年。');
  const visiting = new Set(), visited = new Set();
  function visit(id) {
    if (!ids.has(id)) throw new Error(`依赖任务不存在：${id}`);
    if (visiting.has(id)) throw new Error(`依赖存在循环：${id}`);
    if (visited.has(id)) return;
    visiting.add(id); graph.get(id).forEach(visit); visiting.delete(id); visited.add(id);
  }
  ids.forEach(visit);
}
function edit(task) {
  state.editing = task.id; state.editorDirty = false;
  for (const [key,id] of Object.entries({id:'taskId',name:'taskName',start:'taskStart',end:'taskEnd',progress:'taskProgress'})) $(id).value = task[key];
  $('taskDependencies').value = task.dependencies.join(', '); $('taskId').disabled = true;
  $('editorTitle').textContent = `编辑 ${task.id}`; $('applyTask').textContent = '应用修改'; $('taskName').focus(); refreshControls();
}
function render() {
  $('taskRows').replaceChildren(); $('warnings').replaceChildren();
  const byId = new Map(state.tasks.map((t) => [t.id,t]));
  let warningCount = 0;
  for (const task of state.tasks) {
    const row = document.createElement('tr'), name = text('td',task.name); name.append(text('small',task.id));
    const dates = text('td',`${task.start} → ${task.end}`), duration = Math.round((new Date(`${task.end}T12:00:00Z`)-new Date(`${task.start}T12:00:00Z`))/86400000)+1;
    dates.append(text('small',`${duration} 日历天`));
    const buttons = document.createElement('td');
    const editButton = text('button','编辑'); editButton.onclick = () => {if (!state.busy) edit(task);};
    const del = text('button','删除'); del.onclick = () => {
      if (state.busy) return;
      const dependents = state.tasks.filter((t) => t.dependencies.includes(task.id));
      if (dependents.length) {notice(`${dependents.map((t) => t.id).join('、')} 仍依赖 ${task.id}，请先调整依赖。`,true); return;}
      remember(); state.tasks = state.tasks.filter((t) => t.id !== task.id); clearEditor(); render(); notice(`已从本地计划删除 ${task.id}，可撤销。`);
    };
    buttons.append(editButton,del); row.append(name,dates,text('td',`${task.progress}%`),text('td',task.dependencies.join(', ') || '—'),buttons); $('taskRows').append(row);
    for (const dep of task.dependencies) if (task.start <= byId.get(dep).end) {warningCount += 1; if (warningCount <= 50) $('warnings').append(text('li',`${task.id} 开始日期未晚于 ${dep} 的结束日期，请核对搭接关系。`));}
  }
  if (warningCount > 50) $('warnings').append(text('li',`共有 ${warningCount} 项搭接提醒，先显示前 50 项。`));
  $('taskSummary').textContent = `${state.tasks.length} 个任务 · 最多 250 个`;
  if (!state.tasks.length) {const row = document.createElement('tr'), cell = text('td','添加任务后，点击“编辑”修改日期和进度。','empty'); cell.colSpan = 5; row.append(cell); $('taskRows').append(row);}
  draw(); refreshControls();
}
function draw() {
  $('chartEmpty').hidden = !!state.tasks.length; $('gantt').hidden = !state.tasks.length;
  if (!state.tasks.length) return;
  // Frappe inserts names through innerHTML; retain literal user labels safely.
  const tasks = state.tasks.map((t) => ({...t,name:htmlEscape(t.name),dependencies:[...t.dependencies]}));
  try {
    const height = Math.min(580,90+tasks.length*40);
    if (gantt) {
      gantt.options.view_mode = $('viewMode').value;
      gantt.options.scroll_to = tasks.reduce((a,t) => t.start < a ? t.start : a,tasks[0].start);
      gantt.$container.style.setProperty('--gv-grid-height',`${height}px`);
      gantt.refresh(tasks);
    } else {
      gantt = new Gantt('#gantt',tasks,{view_mode:$('viewMode').value,popup:false,language:'zh',move_dependencies:false,snap_at:'1d',infinite_padding:false,scroll_to:tasks.reduce((a,t) => t.start < a ? t.start : a,tasks[0].start),container_height:height,
        on_date_change: (task,start,end) => chartEdit(task.id,{start:calendarDate(start),end:calendarDate(end)}),
        on_progress_change: (task,progress) => chartEdit(task.id,{progress:Math.round(progress*100)/100})});
    }
  }
  catch {notice('甘特图暂时无法显示；任务清单与编辑内容仍保留，可以保存后重新打开。',true);}
}
function calendarDate(value) {
  return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;
}
function chartEdit(id,patch) {
  if (state.busy || state.editorDirty) {gesture.cancel(); queueMicrotask(draw); return;}
  try {
    const standalone = !gesture.active;
    const token = gesture.active?.token ?? gesture.begin(id);
    gesture.update(id,patch);
    // Native mouse gestures commit only on mouseup, after every chart callback.
    if (standalone) queueMicrotask(() => finishGesture(token));
  } catch (error) {gesture.cancel(); notice(error.message,true); queueMicrotask(render);}
}
function finishGesture(token) {
  const change = gesture.commit(token);
  if (change) {
    const {id,before,after} = change;
    clearEditor();
    const parts = [];
    if (before.start !== after.start || before.end !== after.end) parts.push(`日期：${before.start}–${before.end} → ${after.start}–${after.end}`);
    if (before.progress !== after.progress) parts.push(`进度：${before.progress}% → ${after.progress}%`);
    notice(`${id} ${parts.join('；')}。本次拖动可一步撤销，保存后保留。`);
  }
  render();
}
async function refreshPlans() {
  const result = await api(); const selected = state.project?.id || $('recentPlans').value;
  $('recentPlans').replaceChildren(new Option('选择已保存计划',''));
  for (const plan of result.projects || []) $('recentPlans').append(new Option(`${plan.name} · 修订 ${plan.revision}${plan.error ? ' · 无法读取' : ''}`,plan.id));
  $('recentPlans').value = selected;
}
function showProject(project) {
  validate(project.tasks); state.project = project; state.tasks = clone(project.tasks); state.history = [];
  $('planName').value = project.name; clearEditor(); state.saved = JSON.stringify(snapshot());
  $('versionHistory').textContent = project.versions?.length ? `可恢复历史：${project.versions.map((v) => `修订 ${v.revision}（${v.task_count} 项）`).join('、')}。恢复操作也会生成新修订号。` : '尚无可恢复的已保存修改。';
  const url = new URL(window.location.href); url.searchParams.set('project_id',project.id); window.history.replaceState({},'',url); render();
  pendingProject = null;
}
function canReplace() {return !dirty() || window.confirm('当前有未保存编辑。确定放弃这些编辑并继续吗？');}

$('taskForm').addEventListener('input',() => {state.editorDirty = true; refreshControls();});
$('gantt').addEventListener('mousedown',(event) => {
  if (event.button !== 0 || state.busy || state.editorDirty) return;
  const bar = event.target.closest?.('.bar-wrapper');
  if (!bar) return;
  try {gesture.begin(bar.getAttribute('data-id'));} catch (error) {notice(error.message,true);}
},true);
document.addEventListener('mouseup',() => {
  const token = gesture.active?.token;
  if (token !== undefined) queueMicrotask(() => finishGesture(token));
});
function cancelGesture() {if (gesture.cancel()) {notice('本次拖动已取消，任务恢复为拖动前的值。'); render();}}
$('gantt').addEventListener('pointercancel',cancelGesture);
window.addEventListener('blur',cancelGesture);
$('taskForm').addEventListener('submit',(event) => {
  event.preventDefault();
  try {
    const task = {id:$('taskId').value.trim(),name:$('taskName').value.trim(),start:$('taskStart').value,end:$('taskEnd').value,progress:Number($('taskProgress').value),dependencies:$('taskDependencies').value.split(/[,，\s]+/).filter(Boolean)};
    const tasks = state.editing ? state.tasks.map((t) => t.id === state.editing ? task : t) : [...state.tasks,task];
    validate(tasks); remember(); state.tasks = tasks; clearEditor(); render(); notice(`已应用 ${task.id}。点击“保存计划”写入项目。`);
  } catch (error) {notice(error.message,true);}
});
$('clearEditor').onclick = clearEditor;
$('planName').addEventListener('input',refreshControls);
$('viewMode').onchange = draw;
$('undoEdit').onclick = () => {if (state.busy || !state.history.length) return; const prior = state.history.pop(); state.tasks = prior.tasks; $('planName').value = prior.name; clearEditor(); render(); notice('已撤销最近一次本地任务编辑。');};
for (const [id,copy] of [['savePlan',false],['saveCopy',true]]) $(id).onclick = () => action(async () => {
  validate(state.tasks);
  const body = snapshot(); if (!copy && state.project) Object.assign(body,{id:state.project.id,expected_revision:state.project.revision});
  const payload = await api('',body); showProject(payload.project); notice('计划已保存，可关闭页面后重新打开。'); await refreshPlans();
});
$('openPlan').onclick = () => action(async () => {const id = $('recentPlans').value; if (!id) throw new Error('请先选择计划。'); if (!canReplace()) return; const payload = await api(`/${encodeURIComponent(id)}`); showProject(payload.project); notice('已恢复任务、日期、依赖与保存历史。');});
$('refreshPlans').onclick = () => action(refreshPlans);
$('undoSaved').onclick = () => action(async () => {if (!state.project || dirty()) return; const payload = await api(`/${state.project.id}/undo`,{expected_revision:state.project.revision}); showProject(payload.project); notice('已恢复上次保存的内容，并生成新的修订号。'); await refreshPlans();});
function newPlan(example = false) {
  if (!canReplace()) return;
  pendingProject = null; state.project = null; state.tasks = []; state.history = []; $('planName').value = example ? '合成演示 · 三阶段施工计划' : '';
  if (example) state.tasks = [
    {id:'T1',name:'施工准备（演示）',start:'2026-09-21',end:'2026-09-23',progress:100,dependencies:[]},
    {id:'T2',name:'基础施工（演示）',start:'2026-09-24',end:'2026-10-02',progress:35,dependencies:['T1']},
    {id:'T3',name:'主体施工（演示）',start:'2026-10-03',end:'2026-10-16',progress:0,dependencies:['T2']}
  ];
  clearEditor(); state.saved = example ? '' : JSON.stringify(snapshot()); $('versionHistory').textContent = '尚无保存历史。';
  const url = new URL(window.location.href); url.searchParams.delete('project_id'); window.history.replaceState({},'',url);
  render(); notice(example ? '这是合成演示。日期、进度与任务仅用于展示，不代表真实项目施工安排。' : '已新建空计划，请填写实际任务和日期。');
}
$('newPlan').onclick = () => newPlan(); $('loadExample').onclick = () => newPlan(true);
$('accessForm').onsubmit = (event) => {event.preventDefault(); document.cookie = `cb_token=${encodeURIComponent($('accessToken').value.trim())}; path=/; max-age=2592000; SameSite=Lax`; $('accessToken').value = ''; action(async () => {await refreshPlans(); if (pendingProject && !dirty()) showProject((await api(`/${pendingProject}`)).project); notice('口令验证成功。当前编辑保留，可以继续操作。');});};
window.addEventListener('beforeunload',(event) => {if (dirty()) {event.preventDefault(); event.returnValue = '';}});
state.saved = JSON.stringify(snapshot()); render();
action(async () => {await refreshPlans(); if (pendingProject) showProject((await api(`/${pendingProject}`)).project);});
