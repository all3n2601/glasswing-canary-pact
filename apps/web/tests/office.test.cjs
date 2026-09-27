const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function load(name, globals = {}) {
  const exports={};
  const {outputText}=ts.transpileModule(readFileSync(resolve(__dirname,'../lib',name),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}});
  vm.runInNewContext(outputText,{exports,AbortSignal,DOMException,TypeError,...globals}); return exports;
}
const {reconcileSlots,officePosition}=load('office-layout.ts');
const {mergeRunEvents,boardParticipants}=load('run-events.ts');
const {buildDepartmentSimulation,applyDecisionPackage}=load('simulation-view.ts',{require:()=>({officePosition})});
const profile=JSON.parse(readFileSync(resolve(__dirname,'../../../data/organization_profile.json'),'utf8'));
const baseline=buildDepartmentSimulation(profile);
const impact=(overrides={})=>({affected_department:baseline[0].departmentId,affected_entity:'wf_test',polarity:'harm',severity:4,first_effect_day:30,peak_effect_day:60,confidence:0.8,metric:'capacity_loss',magnitude:0.5,unit:'ratio',direction:'decrease',...overrides});

// Render the scene's component tree and execute its frame callbacks with real Three meshes.
// This catches missing ripple geometry or animation wiring without requiring a WebGL device.
function officeHarness(props={}, loading=false) {
  const React=require('react'), THREE=require('three'), frames=[];
  const imports={
    react:{...React,useRef:value=>({current:value}),useState:value=>[value,()=>{}],useEffect:()=>{},useMemo:fn=>fn()},
    '@react-three/fiber':{Canvas:()=>null,useFrame:fn=>frames.push(fn)},
    '@react-three/drei':{useProgress:()=>({active:loading})},
    './office-furnishings':{},'@/lib/office-layout':{officePosition},
  };
  const {OfficeScene}=load('../components/office-scene.tsx',{require:name=>imports[name]??require(name)});
  const tree=OfficeScene({day:30,departments:applyDecisionPackage(baseline,null,{impacts:[impact()]}),showImpacts:true,...props});
  function find(node,predicate) {
    if(Array.isArray(node)) return node.flatMap(child=>find(child,predicate));
    if(!node || typeof node!=='object') return [];
    return [...(predicate(node)?[node]:[]),...find(node.props?.children,predicate)];
  }
  const world=find(tree,node=>node.type?.name==='World')[0];
  const rendered=world.type({...world.props,reducedMotion:props.reducedMotion??false});
  const workstations=find(rendered,node=>node.type?.name==='Workstation');
  const ripples=workstations.flatMap(node=>find(node.type(node.props),child=>child.type?.name==='ImpactRipples'));
  const rings=ripples.flatMap(node=>find(node.type(node.props),child=>child.type==='mesh').map(element=>{
    const mesh=new THREE.Mesh(undefined,new THREE.MeshBasicMaterial());
    element.props.ref(mesh);
    const material=find(element,child=>child.type==='meshBasicMaterial')[0];
    mesh.material.color.set(material.props.color);
    return {mesh,element,material};
  }));
  return {tree,find,rings,step:delta=>frames.forEach(fn=>fn({},delta))};
}

test('selected result preserves impact timing, strength, and polarity even for the source team',()=>{
  const pkg={brief:{candidate_interventions:[{target_entity_id:baseline[0].departmentId}]} };
  const views=applyDecisionPackage(baseline,pkg,{impacts:[impact()]});
  assert.equal(views[0].startsAt,30); assert.equal(views[0].strength,0.8);
  assert.equal(views[0].tone,'negative');
  const benefit=applyDecisionPackage(baseline,pkg,{impacts:[impact({polarity:'benefit'})]});
  assert.equal(benefit[0].tone,'positive');
  assert.equal(applyDecisionPackage(baseline,null,{impacts:[]})[0].startsAt,Infinity);
});

test('ripples appear at first effect, persist after peak, and disappear before it or without a result',()=>{
  assert.equal(officeHarness({day:29}).rings.length,0);
  assert.equal(officeHarness({day:30}).rings.length,3);
  assert.equal(officeHarness({day:365}).rings.length,3);
  assert.equal(officeHarness({day:-1}).rings.length,0);
  assert.equal(officeHarness({departments:baseline}).rings.length,0);
  assert.equal(officeHarness({showImpacts:false}).rings.length,0);
  assert.equal(officeHarness({board:true}).rings.length,0);
});

test('ripple meshes expand and fade; reduced motion keeps visible stationary impact rings',()=>{
  const scene=officeHarness();scene.step(0);
  const before=scene.rings.map(({mesh})=>[mesh.scale.x,mesh.material.opacity]);
  scene.step(0.1);
  scene.rings.forEach(({mesh,element,material},index)=>{
    assert.ok(mesh.scale.x>before[index][0]);
    assert.ok(mesh.material.opacity<before[index][1]);
    assert.equal(mesh.material.color.getHexString(),'df776c');
    assert.ok(element.props.position[1]>0.03,'rings sit above workstation platforms');
    assert.equal(material.props.depthWrite,false);
  });
  const reduced=officeHarness({reducedMotion:true});reduced.step(0);
  const stationary=reduced.rings.map(({mesh})=>[mesh.scale.x,mesh.material.opacity]);
  reduced.step(10);
  assert.deepEqual(reduced.rings.map(({mesh})=>[mesh.scale.x,mesh.material.opacity]),stationary);
  assert.ok(stationary.every(([,opacity])=>opacity>0));
  const weak=officeHarness({reducedMotion:true,departments:applyDecisionPackage(baseline,null,{impacts:[impact({severity:1})]})});weak.step(0);
  assert.ok(reduced.rings[2].mesh.scale.x>weak.rings[2].mesh.scale.x);
  assert.ok(reduced.rings[0].mesh.material.opacity>weak.rings[0].mesh.material.opacity);
});

test('office loading, empty, and failed scene states retain accessible explanations',()=>{
  const loading=officeHarness({},true);
  assert.equal(loading.find(loading.tree,node=>node.props?.role==='status')[0].props.children,'Loading office…');
  const empty=officeHarness({departments:[]});assert.equal(empty.rings.length,0);
  assert.ok(empty.find(empty.tree,node=>typeof node.props?.children==='string' && node.props.children.startsWith('No departments configured')).length);
  const boundary=new empty.tree.type(empty.tree.props);boundary.state={failed:true};
  assert.equal(boundary.render().props.role,'alert');
});
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

function recoveryClient(fetch, onPause=()=>{}) {
  let now=0;
  return load('canary-api-client.ts',{
    fetch,
    Date:class extends Date {static now(){return now;}},
    setTimeout:(callback,ms)=>{now+=ms;onPause(ms);queueMicrotask(callback);return 1;},
    clearTimeout:()=>{},
  });
}

test('a temporary auth outage during profile loading recovers without another run',async()=>{
  let calls=0;
  const {canaryApi}=recoveryClient(async(url)=>{
    assert.match(url,/office-profile$/);
    return ++calls===1
      ? Response.json({detail:'Authentication is temporarily unavailable.'},{status:503})
      : Response.json({twin_version:'frozen_baseline'});
  });
  assert.equal((await canaryApi.officeProfile('run_a')).twin_version,'frozen_baseline');
  assert.equal(calls,2);
});

test('event history retries network failures with the same cursor',async()=>{
  let calls=0;
  const {canaryApi}=recoveryClient(async(url)=>{
    assert.match(url,/run_a\/event-log\?after_sequence=42$/);
    if (++calls===1) throw new TypeError('NetworkError when attempting to fetch resource.');
    return Response.json({events:[],next_sequence:42,has_more:false,terminal:true});
  });
  assert.equal((await canaryApi.eventLog('run_a',42)).next_sequence,42);
  assert.equal(calls,2);
});

test('run polling survives exhausted read retries and a temporary package outage',async()=>{
  let reads=0, packages=0;
  const states=[], pauses=[];
  const {waitForPackage}=recoveryClient(async(url)=>{
    if (url.endsWith('/package')) {
      if (++packages===1) throw new TypeError('Connection lost');
      return Response.json({package_id:'pkg_a'});
    }
    assert.equal(url,'/api/canary/runs/run_a');
    if (++reads<=3) return Response.json({detail:'Authentication is temporarily unavailable.'},{status:503});
    return Response.json(reads===4 ? {status:'running_agents'} : {status:'awaiting_approval',package_id:'pkg_a'});
  },ms=>pauses.push(ms));
  assert.equal((await waitForPackage('run_a',30000,state=>states.push(state.status))).package_id,'pkg_a');
  assert.deepEqual(states,['running_agents','awaiting_approval']);
  assert.equal(reads,5);assert.equal(packages,2);
  assert.ok(pauses.every(ms=>ms>=1000),'status polling must not hammer auth four times a second');
});

test('writes, expired sessions, missing runs, and actual failed runs are not retried',async()=>{
  for (const status of [401,404]) {
    let calls=0;
    const {canaryApi}=recoveryClient(async()=>{calls++;return Response.json({detail:'Unavailable'},{status});});
    await assert.rejects(canaryApi.run('run_a'),error=>error.status===status);
    assert.equal(calls,1);
  }
  let writes=0;
  const write=recoveryClient(async()=>{writes++;throw new TypeError('Response lost after accepting the run');});
  await assert.rejects(write.canaryApi.createDecision({}),/Response lost/);
  assert.equal(writes,1);
  let reads=0;
  const failed=recoveryClient(async()=>{reads++;return Response.json({status:'failed'});});
  await assert.rejects(failed.waitForPackage('run_a'),/simulation run failed/);
  assert.equal(reads,1);
});

test('persistent outages respect the polling deadline',async()=>{
  const {waitForPackage}=recoveryClient(async()=>Response.json({detail:'Offline'},{status:503}));
  await assert.rejects(waitForPackage('run_a',5000),error=>error.status===504);
});

test('switching runs cancels a transient-error retry before it makes another request',async()=>{
  const controller=new AbortController();
  let calls=0;
  const {canaryApi}=recoveryClient(async()=>{calls++;throw new TypeError('Offline');},()=>controller.abort());
  await assert.rejects(canaryApi.eventLog('old_run',12,controller.signal),{name:'AbortError'});
  assert.equal(calls,1);
});
