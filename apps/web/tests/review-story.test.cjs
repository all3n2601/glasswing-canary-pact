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

const decisionPackage={package_id:'pkg_review',brief:{horizon_days:365},recommendation:{plan_id:'plan_naive',result_id:'result_now',future:'act_now',headline:'Recorded engine comparison.'},futures:{rows:[{result_id:'result_now',feasible:true,net_value_p50_usd:62400}]},open_questions:['Verify transition costs.'],missing_perspectives:[]};
const perspective=(agent,text,severity=4,pass_type='first_pass',plan_id='plan_naive')=>({...first,assessment_id:`${agent}_${pass_type}`,agent_id:agent,plan_id,pass_type,output:{...first.output,act_now_view:{summary:text,failure_modes:[{text,severity,evidence_refs:['ev_workflow']}]},questions:[{text:`Who owns the ${agent} workflow?`}]}});
test('decision highlights preserve revised evidence, scope to the recommended plan and bound the reading load',()=>{
  const assessments=[perspective('marketing','Old claim'),perspective('marketing','Reach may slow.',4,'response'),perspective('marketing','Old claim arrives late'),perspective('operations','Forecast handoff may fail.'),perspective('people','Owner coverage is unknown.',5),perspective('finance','Transition costs are unknown.'),perspective('other','Wrong plan.',5,'first_pass','plan_other')];
  const highlights=story.decisionHighlights(assessments,decisionPackage);
  assert.equal(highlights.risks.length,3); assert.equal(highlights.questions.length,3);
  const texts=highlights.risks.map(r=>r.finding.text).join(' ');
  assert.match(texts,/Reach may slow/); assert.doesNotMatch(texts,/Old claim|Wrong plan/);
  assert.equal(highlights.risks[0].finding.text,'Owner coverage is unknown.');
  assert.equal(highlights.risks.find(r=>r.assessment.agent_id==='marketing').finding.evidence_refs[0],'ev_workflow');
});
test('failed responses never become advice and identical findings do not fill all three cards',()=>{
  const a=perspective('marketing','Reach may slow.');
  const failed={...perspective('marketing','Unsafe replacement.',5,'response'),status:'unavailable'};
  const highlights=story.decisionHighlights([a,failed,perspective('sales','Reach may slow.')],decisionPackage);
  assert.equal(highlights.risks.length,1); assert.equal(highlights.risks[0].finding.text,'Reach may slow.');
});
test('decision leads with review guidance while retaining the engine output and collapsed full concerns',()=>{
  const events=[event('agent_completed',perspective('marketing','Reach may slow.')),event('package_ready',decisionPackage)];
  const html=render(events);
  for(const text of ['Review the risks before acting','Model recommendation:','Act now','$62.4K','What could go wrong','Reach may slow.','Before you decide','ev_workflow','Verify transition costs.']) assert.ok(html.includes(text),text);
  assert.doesNotMatch(html,/<details[^>]* open/);
  assert.ok(html.indexOf('Review the risks before acting')<html.indexOf('Recorded engine comparison.'));
});
test('saved packages without history open on the decision and acknowledge missing risk summaries',()=>{
  const html=renderToStaticMarkup(React.createElement(ReviewStory,{events:[],complete:true,decisionPackage}));
  assert.match(html,/No department risk summaries are available/);
  assert.match(html,/Full review &amp; calculation/);
  assert.match(html,/Review the risks before acting/);
});
test('missing and infeasible recommendations cannot appear as a go-ahead',()=>{
  const html=render([event('package_ready',{...decisionPackage,recommendation:null})]);
  assert.match(html,/Request a complete analysis/);
  const failed=render([event('package_ready',{...decisionPackage,futures:{rows:[{...decisionPackage.futures.rows[0],feasible:false}]}})]);
  assert.match(failed,/Rework the plan before approval/);
  assert.match(failed,/Fails modeled constraints/);
  const inaction=render([event('package_ready',{...decisionPackage,recommendation:{...decisionPackage.recommendation,future:'inaction',plan_id:null}})]);
  assert.match(inaction,/Keep the current plan unchanged/);
});
