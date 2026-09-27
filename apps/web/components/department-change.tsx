"use client";
import { useEffect, useRef, useState } from "react";
import type { OrganizationProfile } from "@canary-pact/contracts";
import type { BlastRadius, DecisionBrief, DepartmentEdit, OrganizationChange, SimulationResult, UserPublic } from "@canary-pact/contracts/generated";
import { canaryApi } from "@/lib/canary-api-client";
import { normalizeProfile } from "@/lib/organization-profile";

export function DepartmentChange({profile, selectedId, user, onClose, onSaved, onPreview, onRun}: {
  profile: OrganizationProfile; selectedId?: string | null; user: UserPublic | null; onClose: () => void;
  onSaved: (profile: OrganizationProfile) => void; onPreview: (brief: DecisionBrief, result: SimulationResult, blast: BlastRadius) => void;
  onRun: (brief: DecisionBrief, departments: string[]) => Promise<void>;
}) {
  const form = useRef<HTMLFormElement>(null);
  useEffect(()=>{form.current?.querySelector<HTMLElement>("input,select,textarea")?.focus();},[]);
  const selected = profile.departments.find(d=>d.department_id===selectedId);
  const [mode,setMode] = useState<"scenario"|"baseline">("scenario");
  const [action,setAction] = useState(selected ? "reduce" : "create");
  const [department,setDepartment] = useState<DepartmentEdit>({department_id:selected?.department_id ?? `dept_${crypto.randomUUID().replaceAll("-", "").slice(0,12)}`, name:selected?.name ?? "", mission:selected?.mission ?? "", actual_fte:selected?.actual_fte ?? 0, annual_budget_usd:selected?.annual_budget_usd ?? 0, utilisation:selected?.utilisation ?? 0, active:true, agent_id:selected?.agent_id ?? null, assumption:""});
  const [amount,setAmount] = useState(20);
  const [day,setDay] = useState(0);
  const [destination,setDestination] = useState("");
  const [workflowIds,setWorkflowIds] = useState<string[]>([]);
  const [workflowsLoading,setWorkflowsLoading] = useState(false);
  const [workflows,setWorkflows] = useState<Array<{id:string;name:string}>>([]);
  const [error,setError] = useState<string|null>(null);
  const [busy,setBusy] = useState(false);
  const [preview,setPreview] = useState<{brief:DecisionBrief;result:SimulationResult}|null>(null);
  const update = (values:Partial<DepartmentEdit>)=>{setDepartment(old=>({...old,...values}));setPreview(null);};
  const loadWorkflows = async () => {
    if (!selected) return;
    setWorkflowsLoading(true);setError(null);
    try {const detail=await canaryApi.department(selected.department_id);setWorkflows((detail.owned_entities ?? []).filter(e=>e.type==="workflow"));}
    catch(e) {setError(e instanceof Error ? e.message : "Could not load workflows");}
    finally {setWorkflowsLoading(false);}
  };
  const submit = async (event:React.FormEvent) => {
    event.preventDefault();if(busy)return;setBusy(true);setError(null);setPreview(null);
    try {
      if (!user) throw new Error("Sign in before saving or simulating a department change.");
      if (mode === "baseline") {
        if (!profile.twin_version) throw new Error("Reload the current company before saving.");
        onSaved(normalizeProfile(await canaryApi.saveDepartment({expected_twin_version:profile.twin_version,department})));onClose();return;
      }
      const id=`change_${crypto.randomUUID().replaceAll("-", "").slice(0,12)}`;
      const target=action==="create" ? department.department_id : selected?.department_id;
      if (!target) throw new Error("Select a department first.");
      if (action==="transfer" && workflowIds.length===0) throw new Error("Choose at least one workflow to transfer.");
      const changes:OrganizationChange[]=[];
      if (action==="create") changes.push({intervention_id:id,operation:"create",department_id:target,new_department:department});
      if (action==="close") changes.push({intervention_id:id,operation:"close",department_id:target});
      if (action==="transfer") changes.push({intervention_id:id,operation:"transfer",department_id:target,destination_department_id:destination,workflow_ids:workflowIds});
      const brief:DecisionBrief={decision_id:`dec_${id}`,decision_type:"restructure",title:`${action} ${department.name}`,statement:department.assumption || `Test ${action} for ${department.name}.`,goal:{metric:"net_value_usd",target:0,unit:"usd",direction:"at_least"},horizon_days:365,candidate_interventions:[{id,kind:"action",type:action==="reduce"?"reduce_capacity":action==="add"?"add_capacity":"assess_change",target_entity_id:target,amount_pct:["reduce","add"].includes(action)?amount:undefined,start_day:day,rationale:department.assumption || "User requested department scenario"}],organization_changes:changes,constraints:[],created_by:user.user_id};
      const calculated=await canaryApi.officePreview({brief,expected_twin_version:profile.twin_version});
      const result=calculated.result;
      setPreview({brief,result});onPreview(brief,result,calculated.blast_radius);
    } catch(e) {setError(e instanceof Error?e.message:"Could not apply department change");}
    finally {setBusy(false);}
  };
  return <div className="absolute inset-0 z-50 grid place-items-center overflow-auto bg-zinc-950/25 p-4 backdrop-blur-sm"><form ref={form} onKeyDown={event=>{
    if(event.key==="Escape" && !busy){event.preventDefault();onClose();}
    if(event.key!=="Tab")return;
    const fields=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)')];
    const first=fields[0],last=fields.at(-1);
    if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
  }} onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="department-change-title" className="my-auto w-full max-w-xl space-y-4 rounded-3xl bg-white p-6 shadow-xl">
    <fieldset disabled={busy} className="space-y-4">
    <div className="flex justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-700">Organization workshop</p><h2 id="department-change-title" className="mt-1 text-xl font-semibold">{selected ? selected.name : "Add a department"}</h2></div><button type="button" onClick={onClose} aria-label="Close department editor">✕</button></div>
    <div className="flex gap-2 text-xs"><button type="button" className={`rounded-lg border p-2 ${mode==="scenario"?"bg-zinc-900 text-white":""}`} onClick={()=>{setMode("scenario");setPreview(null);}}>Test a proposed change</button><button type="button" className={`rounded-lg border p-2 ${mode==="baseline"?"bg-zinc-900 text-white":""}`} onClick={()=>{setMode("baseline");setPreview(null);}}>Edit company baseline</button></div>
    <p className="text-xs leading-5 text-zinc-500">{mode==="scenario"?"Preview consequences on an isolated scenario. Your saved company remains unchanged.":"Saving creates a new company version. Existing runs retain their original baseline."}</p>
    {mode==="scenario" && selected ? <label className="block text-xs">Proposed change<select className="mt-1 w-full rounded-lg border p-2" value={action} onChange={e=>{setAction(e.target.value);setPreview(null);if(e.target.value==="transfer")void loadWorkflows();}}><option value="reduce">Reduce capacity</option><option value="add">Add capacity</option><option value="close">Close department</option><option value="transfer">Transfer workflow ownership</option></select></label>:null}
    {mode==="baseline" || action==="create" ? <div className="grid grid-cols-2 gap-3 text-xs"><label>Name<input required minLength={2} maxLength={80} className="mt-1 w-full rounded-lg border p-2" value={department.name} onChange={e=>update({name:e.target.value})}/></label><label>Modeled FTE<input required type="number" min={0} step="0.1" className="mt-1 w-full rounded-lg border p-2" value={department.actual_fte} onChange={e=>update({actual_fte:Number(e.target.value)})}/></label><label className="col-span-2">Mission<input required minLength={2} className="mt-1 w-full rounded-lg border p-2" value={department.mission} onChange={e=>update({mission:e.target.value})}/></label><label>Annual budget (USD)<input required type="number" min={0} className="mt-1 w-full rounded-lg border p-2" value={department.annual_budget_usd} onChange={e=>update({annual_budget_usd:Number(e.target.value)})}/></label><label>Specialist<select className="mt-1 w-full rounded-lg border p-2" value={department.agent_id ?? ""} onChange={e=>update({agent_id:e.target.value||null})}><option value="">Not mapped</option>{["finance","engineering","ai_data","operations","product","marketing","sales","customer_success","compliance","people_knowledge"].map(id=><option key={id}>{id}</option>)}</select></label>{selected ? <label className="col-span-2 flex gap-2"><input type="checkbox" checked={department.active} onChange={e=>update({active:e.target.checked})}/>Active in baseline (archiving requires resolved ownership and zero staffing/budget)</label>:null}</div>:null}
    {mode==="scenario" ? <div className="flex gap-4 text-xs">{["reduce","add"].includes(action)?<label className="flex-1">Capacity change (%)<input required className="mt-1 w-full rounded-lg border p-2" type="number" min={0} max={100} value={amount} onChange={e=>{setAmount(Number(e.target.value));setPreview(null);}}/></label>:null}<label className="flex-1">Effective day<input required className="mt-1 w-full rounded-lg border p-2" type="number" min={0} max={364} value={day} onChange={e=>{setDay(Number(e.target.value));setPreview(null);}}/></label></div>:null}
    {action==="transfer" && mode==="scenario"?<div className="space-y-2 text-xs"><label>Receiving department<select required className="ml-2 rounded border p-2" value={destination} onChange={e=>{setDestination(e.target.value);setPreview(null);}}><option value="">Choose</option>{profile.departments.filter(d=>(d.active ?? d.enabled) && d.department_id!==selectedId).map(d=><option key={d.department_id} value={d.department_id}>{d.name}</option>)}</select></label>{workflows.map(w=><label key={w.id} className="flex gap-2"><input type="checkbox" checked={workflowIds.includes(w.id)} onChange={e=>{setWorkflowIds(ids=>e.target.checked?[...ids,w.id]:ids.filter(id=>id!==w.id));setPreview(null);}}/>{w.name}</label>)}{workflowsLoading?<p role="status">Loading owned workflows…</p>:!workflows.length?<p>No owned workflows available for transfer.</p>:null}</div>:null}
    <label className="block text-xs">Evidence or explicit modeling assumption<textarea required minLength={10} maxLength={300} className="mt-1 w-full rounded-lg border p-2" value={department.assumption} onChange={e=>update({assumption:e.target.value})}/></label>
    {error?<p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{error}</p>:null}
    {preview?<div className="rounded-xl bg-emerald-50 p-3 text-xs"><strong>Calculated preview ready</strong><p className="mt-1">{preview.result.feasible?"Passes supplied constraints":"Does not meet the objective or constraints"}. {preview.result.impacts?.length ?? 0} reported impacts. Full analysis applies company settings and agent review.</p></div>:null}
    <div className="flex justify-end gap-2"><button type="submit" disabled={busy} className="rounded-xl bg-zinc-900 px-4 py-2 text-xs text-white disabled:opacity-50">{busy?"Working…":mode==="baseline"?"Save company version":"Calculate preview"}</button>{preview && mode==="scenario"?<><button type="button" className="rounded-xl border px-3 py-2 text-xs" onClick={onClose}>Explore preview</button><button type="button" className="rounded-xl border px-3 py-2 text-xs" onClick={()=>{onClose();void onRun(preview.brief,[department.department_id]);}}>Run agent review</button></>:null}</div>
    </fieldset>
  </form></div>;
}
