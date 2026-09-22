/* Offline gesture acceptance: one physical drag is one undoable operation. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const source = fs.readFileSync(path.join(__dirname,'../demo/static/engineering-schedule-state.js'),'utf8');
  const {GanttGesture} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
  const original = {name:'合成验收',tasks:[{id:'T2',name:'基础',start:'2026-09-24',end:'2026-10-02',progress:35,dependencies:[]}]};
  const clone = (value) => JSON.parse(JSON.stringify(value));
  let current = clone(original), undo = [];
  const gesture = new GanttGesture({read:() => current,write:(value) => {current=value;},record:(value) => undo.push(value),validate:(tasks) => {if (tasks[0].end < tasks[0].start) throw new Error('invalid dates');}});

  const first = gesture.begin('T2');
  gesture.update('T2',{start:'2026-09-25',end:'2026-10-03'});
  gesture.update('T2',{start:'2026-09-26',end:'2026-10-04'});
  assert.equal(undo.length,0,'no intermediate callbacks enter undo history');
  const dates = gesture.commit(first);
  assert.equal(dates.before.start,'2026-09-24');
  assert.equal(dates.after.start,'2026-09-26');
  assert.equal(undo.length,1,'one gesture produces one revision');
  current = undo.pop();
  assert.deepEqual(current,original,'one undo restores before the physical drag');
  assert.equal(gesture.commit(first),null,'duplicate mouseup cannot add a revision');

  const second = gesture.begin('T2');
  gesture.update('T2',{progress:40}); gesture.update('T2',{progress:67}); gesture.update('T2',{progress:72});
  const progress = gesture.commit(second);
  assert.equal(progress.before.progress,35); assert.equal(progress.after.progress,72);
  assert.equal(undo.length,1); current=undo.pop(); assert.deepEqual(current,original);

  const third = gesture.begin('T2');
  gesture.update('T2',{progress:90}); gesture.cancel();
  assert.deepEqual(current,original,'cancel restores before the gesture');
  assert.equal(gesture.commit(third),null); assert.equal(undo.length,0);

  const fourth = gesture.begin('T2');
  gesture.update('T2',{start:'2026-09-25',end:'2026-10-03'});
  gesture.update('T2',{start:'2026-09-24',end:'2026-10-02'});
  assert.equal(gesture.commit(fourth),null,'dragging out and back creates no edit');
  assert.equal(undo.length,0);

  const fifth = gesture.begin('T2');
  gesture.update('T2',{progress:80});
  assert.equal(gesture.commit(first),null,'stale release cannot commit a later gesture');
  assert.equal(gesture.active.token,fifth); gesture.cancel();
  assert.throws(() => gesture.begin('UNKNOWN'));
  assert.deepEqual(current,original);
  console.log('PASS schedule gestures: multi-callback dates/progress, single undo, cancel, no-op, stale mouseup, unknown task');
})().catch((error) => {console.error(error); process.exitCode=1;});
