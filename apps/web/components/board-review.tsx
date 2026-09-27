"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Check, ChevronLeft, ChevronRight, CircleDot, FileText, Focus, ShieldCheck, Users } from "lucide-react";
import { REVIEW_STAGES, reviewSnapshot } from "@/lib/review-story";
import { formatCompactCurrency } from "@/lib/formatters";
import type { Event, SimulationResult } from "@canary-pact/contracts/generated";
import { boardParticipants } from "@/lib/run-events";
import { OfficeScene } from "./office-scene";
import { ReviewStory } from "./review-story";
import { canaryApi } from "@/lib/canary-api-client";
import type { Evidence } from "@canary-pact/contracts/generated";
import { useAuth } from "./auth-provider";

export function BoardReview({events, complete, error, result, version, runId, packageReady}: {packageReady: boolean; runId: string; events: Event[]; complete: boolean; error: string | null; result?: SimulationResult; version?: string}) {
  const [reviewStage, setReviewStage] = useState<number | null>(null);
  const [inspector, setInspector] = useState<"review" | "department">("review");
  const snapshot = useMemo(() => reviewSnapshot(events), [events]);
  const activeStage = reviewStage ?? snapshot.stage;
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
    setInspector("department");
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
  const failed = events.some(event => event.type === "run_failed");
  const readyCount = seats.filter(participant => participant.status === "available").length;
  const analyzingCount = seats.filter(participant => participant.status === "analyzing").length;
  const statusLabel = failed ? "Run interrupted" : complete ? "Recorded review" : "Live review";
  const stageHints = ["The proposed change", "Department perspectives", "Test the assumptions", "Review the replies", "Recalculate the impact", "Make the human call"];
  const statusText = {analyzing: "Analyzing", available: "Findings ready", unavailable: "Unavailable"};
  const chooseStage = (stage: number) => {setReviewStage(stage); setInspector("review");};
  return <section className="board-workspace" aria-label="Board review">
    <header className="board-heading">
      <div className="flex min-w-0 items-center gap-3"><span className="board-heading-icon"><Users size={20}/></span><div><p className="board-eyebrow">Decision workspace</p><h1>The boardroom</h1></div></div>
      <div className="flex items-center gap-3"><span className={`board-live-badge ${failed ? "is-warning" : ""}`}><span/>{statusLabel}</span><span className="board-heading-note">Evidence informs. People decide.</span></div>
    </header>
    {error || failed ? <p role="alert" className="board-alert">{failed ? "This run stopped before completion. Received findings remain available." : `Reconnecting: ${error}. Received findings remain visible.`}</p> : null}
    <div className="board-layout">
      <aside className="board-rail" aria-label="Review context">
        <div className="board-proposal"><p className="board-eyebrow"><FileText size={12}/> On the table</p><h2>{snapshot.brief?.title ?? "Preparing your decision"}</h2><p className="board-proposal-text">{snapshot.brief?.statement ?? "The proposal and its constraints will appear when the run begins."}</p>{snapshot.brief ? <span className="board-horizon">{snapshot.brief.horizon_days}-day horizon</span> : null}</div>
        <div className="board-agenda"><p className="board-eyebrow">Review journey</p><nav aria-label="Review stages">{REVIEW_STAGES.map((label, index) => <button key={label} onClick={() => chooseStage(index)} aria-current={activeStage === index ? "step" : undefined} className={`board-stage ${activeStage === index ? "is-active" : ""}`}><span className="board-stage-number">{index < snapshot.stage ? <Check size={13}/> : `0${index + 1}`}</span><span><strong>{label}</strong><small>{stageHints[index]}</small></span>{activeStage === index ? <ChevronRight size={14}/> : null}</button>)}</nav></div>
        <div className="board-session"><ShieldCheck size={17}/><div><strong>Grounded in your company</strong><p>Every finding links back to the run’s evidence.</p><details><summary>Run & baseline</summary><p className="break-all">{runId}</p><p className="break-all">{version ?? "Loading baseline…"}</p></details></div></div>
      </aside>
      <section className="board-center" aria-label="Board table">
        <div className="board-table-heading"><div><span className="board-eyebrow">Shared perspective</span><h2>One decision. Every angle.</h2></div><button className="board-camera-button" onClick={() => setCameraReset(value => value + 1)} title="Reset board camera" aria-label="Reset board camera"><Focus size={16}/><span>Recenter</span></button></div>
        <div className="board-room">
          <div className="board-room-status"><span className="board-room-dot"/>{seats.length ? `${seats.length} perspectives at the table` : "Waiting for participants"}</div>
          <OfficeScene day={-1} board resetKey={cameraReset} participants={seats.slice(seatPage*12, seatPage*12+12).map(p => ({key:p.key, name:name(p.agentId), status:p.status, selected:p.agentId===selected?.agentId}))} onParticipantSelect={selectParticipant}/>
          {!seats.length ? <div role="status" className="board-waiting"><CircleDot size={22}/><strong>{complete ? "No perspectives recorded" : "The table is ready"}</strong><span>{complete ? "Open the review to inspect the available results." : "Department representatives will join as analysis begins."}</span></div> : null}
        </div>
        <div className="board-roster">
          <div className="board-roster-heading"><span className="board-eyebrow">Around the table</span><span>{readyCount} ready{analyzingCount ? ` · ${analyzingCount} analyzing` : ""}</span></div>
          <div className="board-participants" aria-label="Board participants">{seats.map(p => <button key={p.agentId} onClick={() => selectParticipant(p.key)} aria-pressed={p.agentId === selected?.agentId} className="board-person"><span className={`board-avatar is-${p.status}`}>{name(p.agentId).split(" ").map(part => part[0]).slice(0,2).join("")}<i/></span><span><strong>{name(p.agentId)}</strong><small>{statusText[p.status]}</small></span></button>)}</div>
          {seats.length > 12 ? <div className="board-pagination"><button aria-label="Previous seats" disabled={seatPage===0} onClick={() => setPage(seatPage-1)}><ChevronLeft size={14}/></button><span>Seats {seatPage*12+1}–{Math.min((seatPage+1)*12,seats.length)} of {seats.length} · {seats.length - Math.min(12, seats.length - seatPage*12)} off-table</span><button aria-label="Next seats" disabled={(seatPage+1)*12>=seats.length} onClick={() => setPage(seatPage+1)}><ChevronRight size={14}/></button></div> : null}
        </div>
        <div className="board-context-bar"><div><span className="board-eyebrow">{result ? "Selected outcome" : "Current chapter"}</span><strong>{result ? `${result.feasible ? "Within modeled constraints" : "Outside modeled constraints"} · ${formatCompactCurrency(result.value.net_value_usd)} net value` : REVIEW_STAGES[activeStage]}</strong>{result ? <small>{name(result.future)} · {name(result.plan_id ?? "Baseline")}</small> : <small>{stageHints[activeStage]}</small>}</div><button onClick={() => {setInspector("review"); if(result) setReviewStage(4);}} aria-label="Open review details"><ArrowUpRight size={19}/></button></div>
      </section>
      <aside className="board-inspector" aria-label="Review details">
        <div className="board-inspector-tabs" role="group" aria-label="Inspector view"><button aria-pressed={inspector === "review"} onClick={() => setInspector("review")}><FileText size={14}/>Stage review</button><button aria-pressed={inspector === "department"} onClick={() => setInspector("department")}><Users size={14}/>Department</button></div>
        {evidenceStatus || evidence ? <div className="board-source"><div className="flex items-center justify-between"><span className="board-eyebrow">Source evidence</span><button onClick={() => {evidenceRequest.current?.abort();setEvidence(null);setEvidenceStatus("");}} aria-label="Close source evidence">Close</button></div>{evidenceStatus ? <p role="status">{evidenceStatus}</p> : null}{evidence ? <article><strong>{evidence.id}</strong><p>{evidence.snippet}</p><small>Source: {evidence.document_id} · {evidence.source_type}</small></article> : null}</div> : null}
        {inspector === "review" ? <ReviewStory key={runId} embedded events={events} complete={complete} selectedStage={reviewStage} onStageChange={setReviewStage} onEvidence={id => void showEvidence(id)}/> : <div className="board-department" aria-label="Agent findings">
      <label className="block text-xs font-medium">Department perspective<select className="mt-2 w-full rounded-lg border bg-white p-2 text-xs" value={selected?.key ?? ""} onChange={e => selectParticipant(e.target.value)}><option value="" disabled>Select an assessment</option>{participants.map(p => <option key={p.key} value={p.key}>{name(p.agentId)} · {p.planId ?? "Review"} · {p.assessment?.pass_type?.replaceAll("_"," ") ?? "in progress"} · {p.status}</option>)}</select></label>
      {selected ? <div className="mt-5 space-y-4 text-xs leading-5"><h3 className="text-lg font-semibold">{name(selected.agentId)}</h3>
        {selected.status === "analyzing" ? <p role="status">Analyzing the decision. Findings have not arrived.</p> : null}
        {selected.status === "unavailable" ? <p className="rounded-xl bg-amber-50 p-3 text-amber-900">Perspective unavailable. {selected.reason} No advice has been substituted.</p> : null}
        {output ? <div className="board-claim"><p className="board-eyebrow">Department position</p><p>{output.act_now_view.summary}</p><span>Confidence {Math.round(output.confidence * 100)}%</span></div> : null}
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
      </div>}
      {complete && packageReady && result ? <div className="board-human-decision space-y-2 border-t p-4 text-xs"><strong>Human decision</strong><p className="text-zinc-500">Records a decision on the full package. Changes to the company require a separate human action.</p>{events.some(e=>e.type==="human_decision_recorded" && "decision" in e.payload && e.payload.decision!=="request_scenario") || recorded ? <p>A final decision has been recorded.</p> : user?.role === "approver" ? <><select aria-label="Human decision" className="w-full rounded border p-2" value={decision} onChange={e=>setDecision(e.target.value as typeof decision)}><option value="request_scenario">Request another scenario</option><option value="reject">Reject package</option><option value="approve" disabled={!result.feasible}>Approve package</option></select><textarea aria-label="Decision notes" placeholder="Decision notes" className="w-full rounded border p-2" value={notes} onChange={e=>setNotes(e.target.value)}/><button disabled={deciding || (decision==="approve" && !result.feasible)} onClick={()=>void recordDecision()} className="rounded-lg bg-zinc-900 px-3 py-2 text-white disabled:opacity-50">{deciding ? "Recording…" : "Record human decision"}</button></> : <p>An approver can record the final decision.</p>}{decisionStatus ? <p role="status">{decisionStatus}</p> : null}</div> : null}
      </aside>
    </div>
  </section>;
}
