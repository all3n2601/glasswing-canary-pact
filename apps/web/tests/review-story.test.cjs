const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
function load(file, imports={}) {
  const exports={};
  const {outputText}=ts.transpileModule(readFileSync(resolve(__dirname,'..',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}});
  vm.runInNewContext(outputText,{exports,require:name=>imports[name]??require(name)}); return exports;
}
const story=load('lib/review-story.ts');
const {ReviewStory}=load('components/review-story.tsx',{'@/lib/review-story':story,'@/lib/formatters':load('lib/formatters.ts')});
const event=(type,payload)=>({type,payload});
const first={assessment_id:'asm_ops',agent_id:'operations',pass_type:'first_pass',status:'ok',output:{act_now_view:{summary:'We can continue.'},inaction_view:{summary:'No change.'},confidence:0.5}};
const issue={issue_id:'issue_a',source_agent_id:'challenger',source_assessment_id:'asm_ch',target_assessment_id:'asm_ops',text:'What supports continuity?',severity:4};
const start=event('agent_started',{agent_id:'operations',pass_type:'response',review_issues:[issue]});
const response={assessment_id:'asm_ops_response',agent_id:'operations',pass_type:'response',status:'ok',review_issues:[issue],output:{...first.output,review_replies:[{issue_id:'issue_a',position:'revised',explanation:'The feed dependency changes my assessment.',evidence_refs:['ev_feed']}]}};
const render=events=>renderToStaticMarkup(React.createElement(ReviewStory,{events,complete:false}));
test('conversation preserves original, objection and response; duplicate challenge events collapse',()=>{
  const assessment=event('agent_completed',first), reply=event('agent_completed',response);
  const data=story.reviewSnapshot([assessment,start,reply,{...reply,type:'challenge_raised'}]);
  assert.equal(data.assessments.length,2); assert.equal(data.issues.length,1); assert.equal(data.stage,3);
  const html=render([assessment,start,reply]);
  for(const text of ['We can continue.','What supports continuity?','The feed dependency changes my assessment.','Revised','ev_feed']) assert.ok(html.includes(text));
});
test('loading, absent and failed response states never invent agreement',()=>{
  assert.match(render([]),/Waiting for the decision brief/);
  assert.match(render([start]),/Waiting for the department/);
  const failed={...response,status:'unavailable',output:null};
  const html=render([event('agent_completed',first),start,event('agent_completed',failed),event('run_failed',{reason:'Provider timeout'})]);
  assert.match(html,/Unresolved/); assert.match(html,/No valid response/); assert.match(html,/Provider timeout/);
  assert.doesNotMatch(html,/The feed dependency changes my assessment/);
});
test('recalculation compares recorded values and plan identities, not generated conversation numbers',()=>{
  const result=(plan,value)=>({future:'act_now',result_id:plan,plan_id:plan,value:{net_value_usd:value},feasible:true,impacts:[]});
  const events=[event('simulation_completed',result('plan_first',100)),start,event('simulation_completed',result('plan_final',80))];
  const data=story.reviewSnapshot(events); assert.equal(data.initial.plan_id,'plan_first'); assert.equal(data.latest.plan_id,'plan_final'); assert.equal(data.stage,4);
  assert.match(render(events),/selected a different plan/);
});
test('empty saved history retains the package without inventing a response',()=>{
  const pkg={brief:{title:'Saved proposal'},futures:{rows:[]}};
  const data=story.reviewSnapshot([],pkg); assert.equal(data.stage,5); assert.equal(data.issues.length,0); assert.equal(data.brief.title,'Saved proposal');
});
