"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Event, SimulationResult } from "@canary-pact/contracts/generated";
import { boardParticipants } from "@/lib/run-events";
import { OfficeScene } from "./office-scene";
import { ReviewStory } from "./review-story";
import { canaryApi } from "@/lib/canary-api-client";
import type { Evidence } from "@canary-pact/contracts/generated";
import { useAuth } from "./auth-provider";

export function BoardReview({events, complete, error, result, version, runId, packageReady}: {packageReady: boolean; runId: string; events: Event[]; complete: boolean; error: string | null; result?: SimulationResult; version?: string}) {
  const [selectedKey, setSelectedKey] = useState("");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceStatus, setEvidenceStatus] = useState("");
  const evidenceRequest = useRef<AbortController | null>(null);
  const {user} = useAuth();
  const [decisionStatus, setDecisionStatus] = useState("");
  const [deciding, setDeciding] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [decision, setDecision] = useState<"approve"|"reject"|"request_scenario">("request_scenario");
  const [notes, setNotes] = useState("");
  const [page, setPage] = useState(0);
  const [cameraReset, setCameraReset] = useState(0);
  const participants = useMemo(() => boardParticipants(events), [events]);
  const seats = useMemo(() => [...new Map(participants.map(p => [p.agentId, p])).values()], [participants]);
  const seatPage = Math.min(page, Math.max(0, Math.ceil(seats.length / 12) - 1));
  const selected = participants.find(p => p.key === selectedKey) ?? participants.at(-1);
  const assessment = selected?.assessment;
  const output = assessment?.status === "ok" ? assessment.output : null;
  const challenge = assessment?.status === "ok" ? assessment.challenge : null;
  useEffect(()=>{
    setEvidence(null);setEvidenceStatus("");
    return () => evidenceRequest.current?.abort();
  },[selected?.key, runId]);
  const selectParticipant = (key: string) => {
    evidenceRequest.current?.abort();
    setSelectedKey(key);
    const agentId = participants.find(p => p.key === key)?.agentId;
    const index = seats.findIndex(p => p.agentId === agentId);
    if (index >= 0) setPage(Math.floor(index / 12));
  };
  const showEvidence = async (id: string) => {
    evidenceRequest.current?.abort();
    const controller = new AbortController();
    evidenceRequest.current = controller;
    setEvidence(null);setEvidenceStatus("Loading source…");
    try {
      const source = await canaryApi.officeEvidence(runId,id,controller.signal);
      if (!controller.signal.aborted) {setEvidence(source);setEvidenceStatus("");}
    } catch(error) {
      if (!controller.signal.aborted) setEvidenceStatus(error instanceof Error ? error.message : "Source unavailable");
    }
  };
  const recordDecision = async () => {
    setDeciding(true);
    try {
      const package_hash = await canaryApi.packageHash(runId);
      await canaryApi.decide(runId,{decision,notes,package_hash});
      setRecorded(decision !== "request_scenario");
      setDecisionStatus(decision === "request_scenario" ? "Scenario request recorded." : "Human decision recorded. No organizational changes were executed.");
    } catch(error) {setDecisionStatus(error instanceof Error ? error.message : "Could not record decision");}
    finally {setDeciding(false);}
  };
  const name = (id: string) => id.replaceAll("_", " ").replace(/\b\w/g, x => x.toUpperCase());
  return <section className="absolute inset-x-4 top-24 bottom-20 grid gap-4 overflow-auto md:grid-cols-[minmax(0,1fr)_340px]" aria-label="Board review">
    <div className="flex min-h-[540px] min-w-0 flex-col md:min-h-0">
    <div className="z-10 shrink-0 rounded-2xl border border-white bg-white/95 p-4 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-700">{complete ? "Recorded decision review" : "Live department analysis"}</p>
      <div className="mt-1 flex items-center justify-between gap-3"><h2 className="text-xl font-semibold">Decision review</h2><button className="rounded-lg border px-2 py-1 text-xs" onClick={()=>setCameraReset(value=>value+1)}>Reset board camera</button></div>
      <p className="mt-1 text-xs text-zinc-500">{participants.length} assessments · Evidence-linked department review <span className="ml-2 text-[10px] text-zinc-400" title={version}>Baseline {version ?? "loading"}</span></p>
      {error ? <p role="alert" className="mt-2 text-xs text-amber-700">Reconnecting: {error}. Received findings remain visible.</p> : null}
      {events.some(e=>e.type==="run_failed") ? <p role="alert" className="mt-2 text-xs text-amber-700">This run failed. Only the findings received before failure are shown.</p> : null}
      {!events.length && !error ? <p role="status" className="mt-3 text-xs">Waiting for real run events…</p> : null}

    </div>
    <div className="mt-3 flex min-h-[320px] flex-1 md:min-h-0 flex-col overflow-hidden"><ReviewStory key={runId} events={events} complete={complete} onEvidence={id => void showEvidence(id)} /></div>
    <details className="mt-3 rounded-xl border bg-white p-3 text-xs"><summary className="cursor-pointer font-medium">View participants around the table</summary><div className="relative mt-2 h-[300px] overflow-hidden rounded-2xl"><OfficeScene day={-1} board resetKey={cameraReset} participants={seats.slice(seatPage*12, seatPage*12+12).map(p => ({key:p.key, name:name(p.agentId), status:p.status, selected:p.agentId===selected?.agentId}))} onParticipantSelect={selectParticipant} /></div></details></div>
    <aside className="z-10 overflow-auto rounded-2xl border border-white bg-white/95 p-4 shadow-lg" aria-label="Agent findings">
      <label className="block text-xs font-medium">Department perspective<select className="mt-2 w-full rounded-lg border bg-white p-2 text-xs" value={selected?.key ?? ""} onChange={e => selectParticipant(e.target.value)}><option value="" disabled>Select an assessment</option>{participants.map(p => <option key={p.key} value={p.key}>{name(p.agentId)} · {p.planId ?? "Review"} · {p.assessment?.pass_type?.replaceAll("_"," ") ?? "in progress"} · {p.status}</option>)}</select></label>
      {seats.length > 12 ? <div className="mt-2 flex justify-between text-xs"><button disabled={seatPage===0} onClick={() => setPage(seatPage-1)}>Previous seats</button><span>{seatPage*12+1}–{Math.min((seatPage+1)*12,seats.length)} of {seats.length}</span><button disabled={(seatPage+1)*12>=seats.length} onClick={() => setPage(seatPage+1)}>Next seats</button></div> : null}
        {evidenceStatus ? <p role="status">{evidenceStatus}</p> : null}
        {evidence ? <article className="rounded-xl border p-3"><strong>{evidence.id}</strong><p className="mt-2">{evidence.snippet}</p><p className="mt-2 text-zinc-500">Source: {evidence.document_id} · {evidence.source_type}</p></article> : null}
      {selected ? <div className="mt-5 space-y-4 text-xs leading-5"><h3 className="text-lg font-semibold">{name(selected.agentId)}</h3>
        {selected.status === "analyzing" ? <p role="status">Analyzing the decision. Findings have not arrived.</p> : null}
        {selected.status === "unavailable" ? <p className="rounded-xl bg-amber-50 p-3 text-amber-900">Perspective unavailable. {selected.reason} No advice has been substituted.</p> : null}
        {output || challenge ? <p className="text-zinc-500">Open the assessment for this perspective’s reasoning, assumptions, and sources.</p> : null}
        {output || challenge ? <details className="rounded-xl border p-3"><summary className="cursor-pointer font-semibold">Full department assessment</summary><div className="mt-3 space-y-4">
        {output ? <><div><strong>Act now</strong><p className="mt-1 text-zinc-600">{output.act_now_view.summary}</p></div><div><strong>Do not act</strong><p className="mt-1 text-zinc-600">{output.inaction_view.summary}</p></div>
          {(output.act_now_view.failure_modes ?? []).map((f,i)=><p key={i} className="rounded-xl bg-amber-50 p-3">{f.text}</p>)}
          {(output.objections ?? []).map((o,i)=><p key={i}><strong>Objection · </strong>{o.text}</p>)}
          {(output.assumptions ?? []).map((a,i)=><p key={i}><strong>Assumption · </strong>{a}</p>)}
          <p>Confidence {Math.round(output.confidence*100)}%</p>
          <div><strong>Evidence references</strong>{(output.evidence_refs ?? []).length ? output.evidence_refs?.map(id=><p key={id} className="font-mono text-[10px]"><button className="underline" onClick={()=>void showEvidence(id)}>{id}</button></p>) : <p className="text-amber-700">No supporting evidence supplied.</p>}</div>
        </> : null}
        {challenge ? <><h4 className="font-semibold">Challenge review</h4>{[...(challenge.unsupported_assumptions ?? []), ...(challenge.inaction_underestimated ?? []), ...(challenge.circular_logic ?? [])].map((f,i)=><p key={i} className="rounded-xl bg-amber-50 p-3">Unresolved: {f.text}</p>)}{(challenge.objections ?? []).map((o,i)=><p key={i}>{o.text}</p>)}{!(challenge.unsupported_assumptions?.length || challenge.objections?.length || challenge.inaction_underestimated?.length || challenge.circular_logic?.length) ? <p>No objections were supplied in this assessment.</p> : null}</> : null}
        </div></details> : null}
        {assessment ? <details className="border-t pt-3"><summary className="cursor-pointer">Validated assessment</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-words text-[10px]">{JSON.stringify(assessment,null,2)}</pre></details> : null}
      </div> : <p className="mt-5 text-xs text-zinc-500">No department assessments received yet.</p>}
      {complete && packageReady && result ? <div className="mt-3 space-y-2 border-t pt-3 text-xs"><strong>Human decision</strong><p className="text-zinc-500">Records a decision on the full package. Changes to the company require a separate human action.</p>{events.some(e=>e.type==="human_decision_recorded" && "decision" in e.payload && e.payload.decision!=="request_scenario") || recorded ? <p>A final decision has been recorded.</p> : user?.role === "approver" ? <><select aria-label="Human decision" className="w-full rounded border p-2" value={decision} onChange={e=>setDecision(e.target.value as typeof decision)}><option value="request_scenario">Request another scenario</option><option value="reject">Reject package</option><option value="approve" disabled={!result.feasible}>Approve package</option></select><textarea aria-label="Decision notes" placeholder="Decision notes" className="w-full rounded border p-2" value={notes} onChange={e=>setNotes(e.target.value)}/><button disabled={deciding || (decision==="approve" && !result.feasible)} onClick={()=>void recordDecision()} className="rounded-lg bg-zinc-900 px-3 py-2 text-white disabled:opacity-50">{deciding ? "Recording…" : "Record human decision"}</button></> : <p>An approver can record the final decision.</p>}{decisionStatus ? <p role="status">{decisionStatus}</p> : null}</div> : null}
    </aside>
  </section>;
}
