#!/usr/bin/env node
'use strict';
// Execute the main app's actual binding and request handlers with a small DOM.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../demo/static/app.js'), 'utf8');
const plan = 'a'.repeat(32), cad = 'b'.repeat(32);

function harness(url = 'http://localhost/') {
  const elements = new Map(), storage = new Map([['cb_active_session_v1', 'saved-session']]);
  class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; }
    set id(value) { this._id = value; elements.set(value, this); }
    get id() { return this._id; }
    prepend(child) { this.children.unshift(child); child.parentElement = this; }
    appendChild(child) { this.children.push(child); child.parentElement = this; }
    replaceChildren() { this.children = []; }
    addEventListener(type, callback) { this.listeners[type] = callback; }
    remove() { elements.delete(this.id); if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(x => x !== this); }
  }
  const composer = new Element('div'), input = new Element('textarea');
  input.id = 'input'; input.parentElement = composer;
  const requests = [], statuses = [];
  const context = vm.createContext({
    URL, console, location: { href: url }, document: { getElementById: id => elements.get(id), createElement: tag => new Element(tag) },
    crypto: { randomUUID: () => 'offline-session-id' },
    localStorage: { getItem: key => storage.get(key), setItem: (k,v) => storage.set(k,v), removeItem: key => storage.delete(key) },
    history: { replaceState: (_a,_b,href) => { context.location.href = String(href); } },
    fetch: async (url, options) => { requests.push({url, body: JSON.parse(options.body)}); return {ok:false, status:409}; },
    apiError: async () => 'offline request captured', addStatus: text => statuses.push(text),
    cbProj: {cur:'ordinary-project'}, cbConfirmed: () => false, cbClearServerHitl: () => {}, cbCapability: () => true,
  });
  vm.runInContext(source.slice(0, source.indexOf('async function cbResumeSession')), context);
  return {context, elements, requests, statuses, storage, state:vm.runInContext('state',context), composer};
}

function loadBetween(context, start, next) {
  const begin = source.indexOf(start), end = source.indexOf(next, begin + start.length);
  assert.ok(begin >= 0 && end > begin, start);
  vm.runInContext(source.slice(begin, end), context);
}

test('explicit planning URL binds and bypasses unrelated remembered session', () => {
  const h = harness('http://localhost/?planning_project_id='+plan);
  assert.equal(h.state.planningProjectId, plan);
  assert.equal(h.state.cadProjectId, '');
  assert.equal(h.context.cbRememberedSession(), '');
  h.context.cbPlanningProjectRender();
  const banner = h.elements.get('planningProjectContext');
  assert.equal(banner.children[0].href, '/engineering/planning?project_id='+plan);
  assert.match(banner.children[1].textContent, /确认/);
  banner.children[2].listeners.click();
  assert.equal(h.state.planningProjectId, '');
  assert.equal(h.elements.has('planningProjectContext'), false);
  assert.equal(new URL(h.context.location.href).searchParams.has('planning_project_id'), false);
});

test('malformed IDs and mutually conflicting URL bindings never reach context', () => {
  for (const query of ['planning_project_id=../private', 'planning_project_id='+plan+'&cad_project_id='+cad]) {
    const h = harness('http://localhost/?'+query);
    assert.equal(h.state.planningProjectId, '');
    assert.equal(h.state.cadProjectId, '');
  }
});

test('boot never restores the old session over an explicit planning URL', async () => {
  for (const explicit of [true, false]) {
    const h = harness('http://localhost/' + (explicit ? '?planning_project_id='+plan : ''));
    let restored = 0;
    h.context.fetch = async () => ({ok:true,json:async()=>({capabilities:{}})});
    for (const name of ['cbApplyHealth','paintContext','reloadCatalog','loadJobRoot','loadPolicy','loadThreads']) h.context[name]=async()=>{};
    h.context.estimateLocalContext=()=>({}); h.context.cbPackTrialFrom=()=>false;
    h.context.cbEmptyDownShow=error=>{throw error;};
    h.context.cbProj.sessions=[{session_id:'saved-session'}];
    h.context.cbProjOpenSession=async()=>{restored++;h.state.planningProjectId='';h.state.session='saved-session';};
    loadBetween(h.context, 'async function cbResumeSession(', '\nfunction cbConfirmed(');
    loadBetween(h.context, 'async function boot()', '\nasync function loadPolicy(');
    assert.equal(await h.context.boot(), true);
    assert.equal(restored, explicit ? 0 : 1);
    assert.equal(h.state.planningProjectId, explicit ? plan : '');
  }
});

test('restoring a planning session replaces CAD binding and can later clear it', () => {
  const h = harness('http://localhost/?cad_project_id='+cad);
  h.context.cbCadProjectRender();
  h.context.cbRestoreProjectBindings({planning_project_id:plan,cad_project_id:''});
  assert.equal(h.state.planningProjectId, plan);
  assert.equal(h.state.cadProjectId, '');
  assert.equal(h.elements.has('cadProjectContext'), false);
  assert.equal(h.elements.has('planningProjectContext'), true);
  h.context.cbRestoreProjectBindings({});
  assert.equal(h.state.planningProjectId, '');
  assert.equal(h.elements.has('planningProjectContext'), false);
  h.context.cbRestoreProjectBindings({cad_project_id:cad,planning_project_id:plan});
  assert.equal(h.state.planningProjectId, '');
  assert.equal(h.state.cadProjectId, '');
});

test('foreground and background chat send the selected planning ID separately from workspace project', async () => {
  const h = harness('http://localhost/?planning_project_id='+plan);
  loadBetween(h.context, 'async function streamChat(', '\n/* 一轮回答在页面上的状态');
  loadBetween(h.context, 'async function cbRunBackground(', '\nasync function handleSlash(');
  h.state.history = [{role:'user',content:'当前消息'}];
  await assert.rejects(h.context.streamChat('检查计划', null, {controller:{signal:undefined}}), /offline request captured/);
  await h.context.cbRunBackground('检查计划');
  assert.equal(h.requests.length, 2);
  for (const request of h.requests) {
    assert.equal(request.url, '/api/chat');
    assert.equal(request.body.planning_project_id, plan);
    assert.equal(request.body.cad_project_id, '');
    assert.equal(request.body.project_id, 'ordinary-project');
  }
  assert.equal(h.requests[1].body.background, true);
});

test('new local conversation clears planning binding and its URL before the next message', () => {
  const h = harness('http://localhost/?planning_project_id='+plan);
  for (const name of ['cbDetachActiveRun','cbUploadAbortAll','cbAttachRender','cbDraftRestore','cbContextReset','renderSummon','cbResetToEmpty','paintContext']) h.context[name]=()=>{};
  h.context.estimateLocalContext=()=>({});
  loadBetween(h.context, 'function cbNewLocalSession()', '\nfunction cbContextReset(');
  h.context.cbPlanningProjectRender();
  h.context.cbNewLocalSession();
  assert.equal(h.state.planningProjectId, '');
  assert.equal(h.state.cadProjectId, '');
  assert.equal(h.elements.has('planningProjectContext'), false);
  assert.equal(new URL(h.context.location.href).searchParams.has('planning_project_id'), false);
  assert.equal(h.storage.has('cb_active_session_v1'), false);
});

test('logistics binds exclusively, restores and clears without borrowing another project', () => {
  const logistics = 'c'.repeat(32);
  const h = harness('http://localhost/?logistics_project_id='+logistics);
  assert.equal(h.state.logisticsProjectId, logistics);
  assert.equal(h.context.cbRememberedSession(), '');
  h.context.cbLogisticsProjectRender();
  const banner = h.elements.get('logisticsProjectContext');
  assert.equal(banner.children[0].href, '/logistics?project_id='+logistics);
  h.context.cbRestoreProjectBindings({planning_project_id:plan});
  assert.equal(h.state.logisticsProjectId, '');
  assert.equal(h.elements.has('logisticsProjectContext'), false);
  h.context.cbRestoreProjectBindings({logistics_project_id:logistics});
  assert.equal(h.state.planningProjectId, '');
  assert.equal(h.state.logisticsProjectId, logistics);
  h.elements.get('logisticsProjectContext').children[2].listeners.click();
  assert.equal(h.state.logisticsProjectId, '');
  for (const query of ['logistics_project_id='+logistics+'&planning_project_id='+plan,
                       'logistics_project_id='+logistics+'&cad_project_id='+cad]) {
    const mixed = harness('http://localhost/?'+query);
    assert.equal(mixed.state.logisticsProjectId, '');
    assert.equal(mixed.state.planningProjectId, '');
    assert.equal(mixed.state.cadProjectId, '');
  }
});

test('logistics selection reaches foreground and background requests', async () => {
  const logistics = 'c'.repeat(32);
  const h = harness('http://localhost/?logistics_project_id='+logistics);
  loadBetween(h.context, 'async function streamChat(', '\n/* 一轮回答在页面上的状态');
  loadBetween(h.context, 'async function cbRunBackground(', '\nasync function handleSlash(');
  h.state.history=[{role:'user',content:'检查箱单'}];
  await assert.rejects(h.context.streamChat('检查箱单',null,{controller:{signal:undefined}}), /offline request captured/);
  await h.context.cbRunBackground('检查箱单');
  for (const request of h.requests) {
    assert.equal(request.body.logistics_project_id, logistics);
    assert.equal(request.body.planning_project_id, '');
    assert.equal(request.body.cad_project_id, '');
  }
});

test('switching saved sessions clears an old project launch link before refresh', () => {
  for (const key of ['cad_project_id', 'planning_project_id', 'logistics_project_id']) {
    const h = harness('http://localhost/?'+key+'='+plan+'&view=chat#messages');
    h.context.cbRestoreProjectBindings({[key]:cad});
    h.context.cbRememberSession('chosen-session');
    const refreshed = harness(h.context.location.href);
    refreshed.storage.set('cb_active_session_v1', 'chosen-session');
    assert.equal(refreshed.context.cbRememberedSession(), 'chosen-session');
    const url = new URL(h.context.location.href);
    assert.equal(url.searchParams.has(key), false);
    assert.equal(url.searchParams.get('view'), 'chat');
    assert.equal(url.hash, '#messages');
    refreshed.context.cbRestoreProjectBindings({[key]:cad});
    assert.equal(refreshed.state[key.replace(/_([a-z])/g, (_, c) => c.toUpperCase())], cad);
  }
});
