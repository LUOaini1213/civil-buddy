#!/usr/bin/env node
'use strict';
// Actual page handlers with a small DOM. No browser, model endpoint or network.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname,'../demo/static/engineering.js'),'utf8');
const html = fs.readFileSync(path.join(__dirname,'../demo/static/engineering.html'),'utf8');
const modulePromise = import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const copy = (value)=>JSON.parse(JSON.stringify(value));
const fixture = {schema_version:1,units:'SI',source:'synthetic',title:'synthetic-beam',samples:41,
  nodes:[{id:'A',x_m:0,y_m:0,z_m:0,support:[true,true,true,true,false,false]},{id:'B',x_m:4,y_m:0,z_m:0,support:[false,true,true,false,false,false]}],
  materials:[{id:'M',E_Pa:200e9,G_Pa:200e9/2.6,nu:.3,density_kg_m3:7850}],sections:[{id:'S',A_m2:.01,Iy_m4:8e-6,Iz_m4:8e-6,J_m4:1e-5}],
  members:[{id:'BEAM',i:'A',j:'B',material_id:'M',section_id:'S',rotation_deg:0}],load_cases:[{id:'Q'}],combinations:[{id:'Q',factors:{Q:1}}],nodal_loads:[],
  member_loads:[{member_id:'BEAM',case_id:'Q',direction:'FY',w1_N_m:-1000,w2_N_m:-1000,x1_m:0,x2_m:4}]};
function result(model=fixture) {return {ok:true,engine:{name:'PyniteFEA',version:'3.2.0'},model:copy(model),assumptions:['Explicit supports; synthetic fixture'],combinations:[{id:'Q',factors:{Q:1},nodes:[{id:'A',reaction_N:[0,2000,0],displacement_m:[0,0,0]}],members:[{id:'BEAM',i:'A',j:'B',length_m:4,curves:{x_m:[0,2,4],shear_y_N:[2000,0,-2000],moment_z_Nm:[0,-2000,0],dy_m:[0,-.002083333,0]}}]}]};}
const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};};
const project=(id='a',model=fixture)=>({project:{id,name:`Project-${id}`,revision:1,versions:[{version:1,created_at:'fixture'}]},version:1,run_id:`run-${id}`,snapshot:{kind:'frame',inputs:copy(model),result:result(model)}});

class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.listeners={};this.dataset={};this.attributes={};this._value=null;this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.files=[];}
  set value(value){this._value=String(value);} get value(){return this._value ?? (this.tagName==='select'?this.children[0]?.value||'':'');}
  set disabled(value){this._disabled=Boolean(value);} get disabled(){return this._disabled;}
  append(...values){this.children.push(...values);}
  replaceChildren(...values){this.children=[...values];if(this.tagName==='select')this._value=null;}
  setAttribute(key,value){this.attributes[key]=value;}
  addEventListener(name,fn){(this.listeners[name]||=[]).push(fn);}
  emit(name,event={}){return Promise.all((this.listeners[name]||[]).map(fn=>fn({target:this,preventDefault(){},...event})));}
  click(){if(this.disabled)return Promise.resolve();return this.emit('click');}
}
function dom(){
  const ids={},fields={},modes=[],all=[],stack=[];
  for(const match of html.matchAll(/<(\/?)([a-z]+)\b([^>]*?)>/g)){
    if(match[1]){while(stack.length && stack.pop().tagName!==match[2]){}continue;}
    const element=new Element(match[2]),attributes=match[3],id=/\bid="([^"]+)"/.exec(attributes),name=/\bname="([^"]+)"/.exec(attributes),mode=/\bdata-mode="([^"]+)"/.exec(attributes);
    element.parent=stack.at(-1);element.classes=(/\bclass="([^"]+)"/.exec(attributes)?.[1]||'').split(/\s+/);
    element.required=/\brequired\b/.test(attributes);element.type=/\btype="([^"]+)"/.exec(attributes)?.[1];
    if(id)ids[id[1]]=element;if(name)fields[name[1]]=element;if(mode){element.dataset.mode=mode[1];modes.push(element);}all.push(element);
    if(!['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'].includes(element.tagName))stack.push(element);
  }
  const hasAncestor=(node,predicate)=>{for(let parent=node.parent;parent;parent=parent.parent)if(predicate(parent))return true;return false;};
  const controlled=all.filter(node=>{
    const inInputs=hasAncestor(node,parent=>parent.classes.includes('inputs'));
    return inInputs && (['input','textarea','select'].includes(node.tagName)||node.tagName==='button'&&hasAncestor(node,parent=>parent.tagName==='form')) || node.tagName==='button'&&hasAncestor(node,parent=>parent.classes.includes('tabs'));
  });
  ids.beamForm.elements={namedItem:key=>fields[key]};
  ids.beamForm.reportValidity=()=>Object.values(fields).every(field=>!field.required||(field.type==='checkbox'?field.checked:field.value!==''&&Number.isFinite(Number(field.value))));
  return {ids,fields,modes,cookie:'',getElementById:id=>ids[id],createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selector=>{if(selector==='[data-mode]')return modes;assert.equal(selector,'.inputs input,.inputs textarea,.inputs select,.inputs form button,.tabs button');return controlled;}};
}
async function withApp(fetcher,action,options={}){
  const previous={fetch:global.fetch,Option:global.Option,crypto:global.crypto};
  global.fetch=fetcher;global.Option=class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value;}};
  if(!global.crypto)global.crypto=crypto.webcrypto;
  const document=dom(),{startEngineeringApp}=await modulePromise;
  const app=startEngineeringApp(document,{initialize:false,...options});
  try{await action({app,doc:document});}finally{app.dispose();global.fetch=previous.fetch;global.Option=previous.Option;if(!previous.crypto)delete global.crypto;}
}
async function calculated(app){app.setModel(copy(fixture));await app.execute();assert.equal(app.state.dirty,false);}

test('form edits cannot compute or save an old JSON model as current',async()=>{
  let calls=0;
  await withApp(async url=>{assert.equal(url,'/api/engineering/frame');calls++;return response({run_id:'success',result:result()});},async({app,doc})=>{
    await calculated(app);doc.fields.load.value='1500';await doc.ids.beamForm.emit('input',{target:doc.fields.load});
    assert.equal(app.state.formPending,true);assert.equal(doc.ids.run.disabled,true);assert.equal(doc.ids.save.disabled,true);assert.equal(doc.ids.export.disabled,true);
    await app.execute();await app.saveProject();assert.equal(calls,1);assert.match(doc.ids.notice.textContent,/尚未应用/);assert.match(doc.ids.resultState.textContent,/上一次成功/);
    await doc.ids.discardForm.click();assert.equal(doc.fields.load.value,'1000');assert.equal(app.state.formPending,false);assert.equal(JSON.parse(doc.ids.frameModel.value).member_loads[0].w1_N_m,-1000);
  });
});

test('applying a beam requires support confirmation and matches all six stated constraints',async()=>{
  await withApp(async()=>{throw Error('no network expected');},async({app,doc})=>{
    app.setModel(copy(fixture));doc.fields.load.value='2000';await doc.ids.beamForm.emit('input');await doc.ids.beamForm.emit('submit');
    assert.equal(app.state.formPending,true);assert.equal(JSON.parse(doc.ids.frameModel.value).member_loads[0].w1_N_m,-1000);
    doc.fields.supports.checked=true;await doc.ids.beamForm.emit('submit');const model=JSON.parse(doc.ids.frameModel.value);
    assert.equal(app.state.formPending,false);assert.equal(model.member_loads[0].w1_N_m,-2000);
    assert.deepEqual(model.nodes[0].support,[true,true,true,true,false,false]);assert.deepEqual(model.nodes[1].support,[false,true,true,false,false,false]);
    assert.match(html,/左端约束 X\/Y\/Z 位移与绕 X 转动，右端约束 Y\/Z 位移/);
  });
});

test('invalid JSON history can be undone without parsing or losing the older valid text',async()=>{
  await withApp(async()=>{throw Error('no network expected');},async({app,doc})=>{
    app.setModel(copy(fixture));const original=doc.ids.frameModel.value;
    await doc.ids.frameModel.emit('focus');doc.ids.frameModel.value='{broken';await doc.ids.frameModel.emit('input');await doc.ids.frameModel.emit('change');
    app.setModel({...fixture,title:'replacement'});await doc.ids.undoInput.click();assert.equal(doc.ids.frameModel.value,'{broken');assert.match(doc.ids.notice.textContent,/JSON 尚未完整/);
    await doc.ids.undoInput.click();assert.equal(doc.ids.frameModel.value,original);assert.equal(app.state.dirty,true);
  });
});

test('canceled late example replies cannot overwrite a newer model',async()=>{
  const old=deferred();
  await withApp(async url=>url.endsWith('kind=beam')?old.promise:response({model:{...fixture,title:'new-frame'}}),async({app,doc})=>{
    const pending=app.loadExample('beam');assert.equal(app.state.busy,'load');await app.cancelOperation();await app.loadExample('frame');
    old.resolve(response({model:{...fixture,title:'old-beam'}}));await pending;
    assert.equal(JSON.parse(doc.ids.frameModel.value).title,'new-frame');assert.equal(app.state.busy,false);
  });
});

test('canceled asynchronous JSON file reads do not resurrect old input',async()=>{
  const text=deferred();
  await withApp(async()=>{throw Error('no network expected');},async({app,doc})=>{
    const pending=app.importFrame({size:100,text:()=>text.promise});await app.cancelOperation();app.setModel({...fixture,title:'current'});
    text.resolve(JSON.stringify({...fixture,title:'late-file'}));await pending;assert.equal(JSON.parse(doc.ids.frameModel.value).title,'current');
  });
});

test('failed and canceled computations retain a clearly stale previous result',async()=>{
  let count=0;const late=deferred();
  await withApp(async url=>{
    if(url.includes('/cancel'))return response({ok:true});
    if(++count===1)return response({run_id:'old-run',result:result()});
    if(count===2)return response({detail:'unstable fixture'},422);return late.promise;
  },async({app,doc})=>{
    await calculated(app);await app.execute();assert.equal(app.state.run.run_id,'old-run');assert.equal(app.state.dirty,true);assert.match(doc.ids.notice.textContent,/unstable fixture/);assert.equal(doc.ids.export.disabled,true);
    const pending=app.execute();await app.cancelOperation();late.resolve(response({run_id:'late-run',result:result()}));await pending;
    assert.equal(app.state.run.run_id,'old-run');assert.equal(app.state.busy,false);assert.match(doc.ids.resultState.textContent,/上一次成功/);
  });
});

test('save locks project navigation and submits only the server run reference',async()=>{
  const saving=deferred();const calls=[];
  await withApp(async(url,request)=>{
    calls.push(url);
    if(url==='/api/engineering/projects/a')return response(project('a'));
    if(url==='/api/engineering/projects'&&request?.method==='POST'){
      const body=JSON.parse(request.body);assert.deepEqual(body,{run_id:'run-a',name:'Project-a',id:'a',expected_revision:1});return saving.promise;
    }
    if(url==='/api/engineering/projects')return response({projects:[{id:'a',name:'Project-a'}]});
    throw Error('unexpected '+url);
  },async({app,doc})=>{
    await app.openProject(undefined,'a');const pending=app.saveProject();assert.equal(app.state.busy,'save');assert.equal(doc.ids.open.disabled,true);
    await app.openProject(undefined,'b');assert.equal(calls.includes('/api/engineering/projects/b'),false);
    saving.resolve(response({project:{id:'a',name:'Project-a',revision:2,versions:[]},version:2}));await pending;
    assert.equal(app.state.project.id,'a');assert.equal(app.state.project.revision,2);assert.equal(app.state.busy,false);
  });
});

test('opening another project discards all stale open replies and old undo history',async()=>{
  const old=deferred();
  await withApp(async url=>url.endsWith('/a')?old.promise:response(project('b',{...fixture,title:'project-b'})),async({app,doc})=>{
    app.setModel(fixture);app.setModel({...fixture,title:'old-edit'});const pending=app.openProject(undefined,'a');await app.cancelOperation();await app.openProject(undefined,'b');
    old.resolve(response(project('a')));await pending;assert.equal(app.state.project.id,'b');assert.equal(app.state.run.run_id,'run-b');assert.equal(app.state.history.length,0);assert.equal(doc.ids.undoInput.disabled,true);assert.equal(JSON.parse(doc.ids.frameModel.value).title,'project-b');
  });
});

test('late cancel acknowledgement cannot overwrite a newer successful notification',async()=>{
  const compute=deferred(),cancellation=deferred();let calls=0;
  await withApp(async url=>url.includes('/cancel')?cancellation.promise:++calls===1?compute.promise:response({run_id:'new',result:result()}),async({app,doc})=>{
    app.setModel(fixture);const old=app.execute();const cancel=app.cancelOperation();await app.execute();const message=doc.ids.notice.textContent;
    cancellation.resolve(response({ok:true}));await cancel;compute.resolve(response({run_id:'old',result:result()}));await old;
    assert.equal(app.state.run.run_id,'new');assert.equal(doc.ids.notice.textContent,message);assert.match(message,/计算完成/);
  });
});

test('switching tools clears unapplied form values instead of leaving invisible input drift',async()=>{
  await withApp(async()=>{throw Error('no network expected');},async({app,doc})=>{
    app.setModel(fixture);doc.fields.length.value='8';await doc.ids.beamForm.emit('input');app.switchMode('ifc_check');app.switchMode('frame');
    assert.equal(app.state.formPending,false);assert.equal(doc.fields.length.value,'4');assert.equal(app.state.run,null);
  });
});

test('an existing section record opens as a CAD report with an explicit edit destination',async()=>{
  const record={project:{id:'section',name:'Section',revision:1,versions:[]},version:1,run_id:'section-run',document_id:'doc',snapshot:{kind:'section',inputs:{config:{unit:'mm'}},result:{engine:'sectionproperties',engine_version:'3.10.2',regions:[],notes:[]}}};
  await withApp(async()=>response(record),async({app,doc})=>{
    await app.openProject(undefined,'section');assert.equal(app.state.mode,'section');assert.equal(doc.ids.sectionFields.hidden,false);assert.equal(doc.ids.frameFields.hidden,true);assert.deepEqual(app.state.inputs.section,{document_id:'doc',config:{unit:'mm'}});
  });
});

test('restoring a version always uses the loaded project, not an unopened dropdown selection',async()=>{
  const calls=[];
  await withApp(async url=>{calls.push(url);return response(project('a'));},async({app,doc})=>{
    assert.equal(doc.ids.restore.disabled,true);await app.openProject(undefined,'a');
    doc.ids.projects.value='b';doc.ids.versions.value='1';await doc.ids.restore.click();
    assert.deepEqual(calls,['/api/engineering/projects/a','/api/engineering/projects/a?version=1']);
    assert.equal(app.state.project.id,'a');
  });
});

test('canceled IFC reads cannot replace the source of another project',async()=>{
  const reading=deferred();
  await withApp(async()=>response(project('frame')),async({app,doc})=>{
    app.switchMode('ifc_check');app.state.inputs.ifc_check={ids:{name:'original.ids',data_b64:'original'}};
    doc.ids.checkIfc.files=[{name:'late.ifc',size:64,arrayBuffer:()=>reading.promise}];
    const pending=doc.ids.checkIfc.emit('change');assert.equal(app.state.busy,'load');await app.cancelOperation();await app.openProject(undefined,'frame');
    reading.resolve(new TextEncoder().encode('IFC fixture').buffer);await pending;
    assert.deepEqual(app.state.inputs.ifc_check,{ids:{name:'original.ids',data_b64:'original'}});
    assert.equal(app.state.mode,'frame');assert.equal(app.state.run.run_id,'run-frame');
  });
});

test('late initial capabilities cannot reopen a URL project over a user edit',async()=>{
  const capabilities=deferred(),calls=[];
  await withApp(async url=>{calls.push(url);if(url.endsWith('/capabilities'))return capabilities.promise;if(url==='/api/engineering/projects')return response({projects:[]});throw Error('must not open URL project');},async({app,doc})=>{
    app.setModel({...fixture,title:'new user input'});
    capabilities.resolve(response({tools:{frame:{available:true},section:{available:true},ifc_check:{available:true},ifc_diff:{available:true}}}));await app.ready;
    assert.equal(JSON.parse(doc.ids.frameModel.value).title,'new user input');assert.equal(app.state.project,null);
    assert.equal(calls.some(url=>url.endsWith('/url-project')),false);
  },{initialize:true,location:'http://localhost/engineering?project_id=url-project'});
});
