const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function load(name, globals = {}) {
  const exports={};
  const {outputText}=ts.transpileModule(readFileSync(resolve(__dirname,'../lib',name),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}});
  vm.runInNewContext(outputText,{exports,...globals}); return exports;
}
const {reconcileSlots,officePosition}=load('office-layout.ts');
const {mergeRunEvents,boardParticipants}=load('run-events.ts');
test('department positions survive reorder, removal and addition; 24 unique slots per page',()=>{
  const ids=Array.from({length:24},(_,i)=>`dept_${i}`);
  const initial=reconcileSlots({},ids);
  const next=reconcileSlots(initial,[...ids].reverse().slice(1).concat('dept_new'));
  for(const id of ids) assert.equal(next[id],initial[id]);
  assert.equal(next.dept_new,24);
  assert.equal(new Set(ids.map(id=>JSON.stringify(officePosition(initial[id])))).size,24);
});
test('event recovery is ordered, deduplicated and isolated by run',()=>{
  const event=(sequence,run_id='run_a')=>({sequence,run_id,event_id:`evt_${sequence}`,type:'agent_started',payload:{agent_id:'finance'}});
  const merged=mergeRunEvents('run_a',[event(1)],[event(3),event(2),event(1),event(4,'run_b')]);
  assert.equal(JSON.stringify(merged.map(e=>e.sequence)),'[1,2,3]');
});
test('failed completion never becomes a successful speaker and challenge envelopes deduplicate',()=>{
  const start={type:'agent_started',payload:{agent_id:'finance',plan_id:'plan_a'}};
  const failed={type:'agent_completed',payload:{agent_id:'finance',plan_id:'plan_a',assessment_id:'a',status:'invalid'}};
  assert.equal(boardParticipants([start,failed])[0].status,'unavailable');
  const success={type:'agent_completed',payload:{agent_id:'challenger',plan_id:'plan_a',assessment_id:'b',status:'ok',challenge:{confidence:0.5}}};
  const all=boardParticipants([start,failed,success,{...success,type:'challenge_raised'}]);
  assert.equal(all.length,2); assert.equal(all[1].challenge,true);
});

test('separate assessment passes remain inspectable without duplicate challenge envelopes',()=>{
  const assessment=pass=>({type:'agent_completed',payload:{agent_id:'finance',plan_id:'plan_a',assessment_id:pass,pass_type:pass,status:'ok'}});
  const first=assessment('first_pass'), second=assessment('second_pass');
  const participants=boardParticipants([first,second,{...second,type:'challenge_raised'}]);
  assert.equal(participants.length,2);
  assert.equal(participants[0].assessment.pass_type,'first_pass');
  assert.equal(participants[1].assessment.pass_type,'second_pass');
});


test('run failure settles pending seats while preserving received assessments',()=>{
  const complete={type:'agent_completed',payload:{agent_id:'finance',plan_id:'plan_a',assessment_id:'a',status:'ok'}};
  const start={type:'agent_started',payload:{agent_id:'operations',plan_id:'plan_a'}};
  const participants=boardParticipants([complete,start,{type:'run_failed',payload:{reason:'Provider unavailable'}}]);
  assert.equal(participants[0].status,'available');
  assert.equal(participants[1].status,'unavailable');
  assert.match(participants[1].reason,/ended before/);
});

test('response start and failure preserve the original assessment as a separate pass',()=>{
  const first={type:'agent_completed',payload:{agent_id:'operations',plan_id:'plan_a',assessment_id:'initial',pass_type:'first_pass',status:'ok'}};
  const start={type:'agent_started',payload:{agent_id:'operations',plan_id:'plan_a',pass_type:'response'}};
  const fail={type:'agent_failed',payload:{agent_id:'operations',plan_id:'plan_a',pass_type:'response',reason:'Timeout'}};
  const final={type:'agent_completed',payload:{agent_id:'operations',plan_id:'plan_a',assessment_id:'reply',pass_type:'response',status:'unavailable'}};
  const pending=boardParticipants([first,start]);
  assert.equal(pending.length,2); assert.equal(pending[0].status,'available'); assert.equal(pending[1].status,'analyzing');
  const complete=boardParticipants([first,start,fail,final]);
  assert.equal(complete.length,2); assert.equal(complete[0].status,'available'); assert.equal(complete[1].status,'unavailable');
});

test('canceled run never publishes a late response or starts a package request',async()=>{
  let finish, calls=0, states=0;
  const controller=new AbortController();
  const {waitForPackage}=load('canary-api-client.ts',{
    fetch:async()=>{calls++;return new Promise(resolve=>{finish=resolve;});},
    setTimeout,clearTimeout,DOMException,
  });
  const waiting=waitForPackage('old_run',1000,()=>states++,controller.signal);
  controller.abort();
  finish(new Response(JSON.stringify({status:'completed',package_id:'old_package'})));
  await assert.rejects(waiting,{name:'AbortError'});
  assert.equal(calls,1);assert.equal(states,0);
});

test('canceling between run polls removes the pending timer',async()=>{
  const controller=new AbortController();
  let calls=0, polls=0, canceled=0;
  const {waitForPackage}=load('canary-api-client.ts',{
    fetch:async()=>{calls++;return new Response(JSON.stringify({status:'running'}));},
    setTimeout:()=>{polls++;queueMicrotask(()=>controller.abort());return 123;},
    clearTimeout:id=>{assert.equal(id,123);canceled++;},DOMException,
  });
  await assert.rejects(waitForPackage('run_a',1000,undefined,controller.signal),{name:'AbortError'});
  assert.equal(calls,1);assert.equal(polls,1);assert.equal(canceled,1);
});
