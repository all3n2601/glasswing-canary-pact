"use client";

import type { DecisionBrief, DecisionDraft, RunState, UserPublic } from "@canary-pact/contracts/generated";
import { Check, ChevronLeft, ChevronRight, LoaderCircle, Mic, MicOff, Play, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { canaryApi } from "@/lib/canary-api-client";

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type AnalysisMode = "live" | "replay" | "mock";

const runPhases: Array<{ status: RunState["status"]; label: string }> = [
  { status: "validating", label: "Validate brief" },
  { status: "building_futures", label: "Build futures" },
  { status: "optimizing", label: "Check quantified feasibility" },
  { status: "running_agents", label: "Run every department" },
  { status: "propagating", label: "Trace blast radius" },
  { status: "challenging", label: "Challenge assumptions" },
  { status: "comparing_futures", label: "Compare futures" },
  { status: "mitigating", label: "Test mitigations" },
  { status: "generating_package", label: "Build decision package" },
  { status: "awaiting_approval", label: "Ready for review" },
];

function RunProgress({ run }: { run: RunState }) {
  const activeIndex = runPhases.findIndex((phase) => phase.status === run.status);
  const effectiveIndex = run.status === "completed" ? runPhases.length : Math.max(0, activeIndex);
  return <div className="mt-7">
    <div className="flex items-center justify-between gap-4"><div><Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700">Live run</Badge><h2 className="mt-3 text-2xl font-semibold tracking-[-.04em]">Every department is assessing the proposal.</h2></div><LoaderCircle className="size-6 shrink-0 animate-spin text-blue-600" /></div>
    <ol className="mt-6 grid gap-2 sm:grid-cols-2">{runPhases.map((phase, index) => { const complete = index < effectiveIndex || run.status === "completed"; const active = phase.status === run.status; return <li key={phase.status} className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-xs ${active ? "border-blue-300 bg-blue-50 text-blue-800" : complete ? "border-emerald-100 bg-emerald-50 text-emerald-800" : "border-zinc-200 text-zinc-400"}`}><span className={`grid size-6 shrink-0 place-items-center rounded-full ${active ? "bg-blue-600 text-white" : complete ? "bg-emerald-600 text-white" : "bg-zinc-100"}`}>{complete ? <Check className="size-3.5" /> : index + 1}</span><span className="font-semibold">{phase.label}</span></li>; })}</ol>
  </div>;
}

export function DecisionComposer({ user, submitting, run, error, onClose, onSubmit, onReplay }: {
  user: UserPublic | null;
  submitting: boolean;
  run: RunState | null;
  error: string | null;
  onClose: () => void;
  onSubmit: (brief: DecisionBrief, mode: AnalysisMode) => Promise<void>;
  onReplay: () => Promise<void>;
}) {
  const [prompt, setPrompt] = useState("");
  const [horizonDays, setHorizonDays] = useState(365);
  const [mode, setMode] = useState<AnalysisMode>("mock");
  const [draft, setDraft] = useState<DecisionDraft | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const promptBeforeSpeechRef = useRef("");

  useEffect(() => {
    const speechWindow = window as typeof window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    setSpeechSupported(Boolean(speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition));
    return () => recognitionRef.current?.stop();
  }, []);

  const toggleDictation = () => {
    if (listening) { recognitionRef.current?.stop(); return; }
    const speechWindow = window as typeof window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) { setSpeechError("Voice dictation is unavailable in this browser."); return; }
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = navigator.language || "en-US";
    promptBeforeSpeechRef.current = prompt.trim();
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map((result) => result[0]?.transcript ?? "").join(" ").trim();
      setPrompt([promptBeforeSpeechRef.current, transcript].filter(Boolean).join(" "));
    };
    recognition.onerror = () => { setSpeechError("Dictation stopped. Check microphone permission and try again."); setListening(false); };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setSpeechError(null);
    setListening(true);
    recognition.start();
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!user || prompt.trim().length < 10) return;
    if (draft) { await onSubmit(draft.brief, mode); return; }
    setDrafting(true);
    setDraftError(null);
    try {
      setDraft(await canaryApi.draftDecision({ prompt: prompt.trim(), horizon_days: horizonDays }));
    } catch (nextError) {
      setDraftError(nextError instanceof Error ? nextError.message : "The decision could not be interpreted.");
    } finally {
      setDrafting(false);
    }
  };
  const matchedEntityIds = draft?.matched_entity_ids ?? [];
  const assessingDepartmentIds = draft?.assessing_department_ids ?? [];
  const draftWarnings = draft?.warnings ?? [];
  const draftAssumptions = draft?.assumptions ?? [];

  return <div className="absolute inset-0 z-50 grid place-items-center overflow-y-auto bg-zinc-950/25 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (!submitting && event.currentTarget === event.target) onClose(); }}>
    <div role="dialog" aria-modal="true" aria-labelledby="decision-title" className="my-auto w-full max-w-[760px] rounded-[28px] border border-white bg-white p-5 shadow-[0_30px_100px_rgb(0_0_0/.24)] sm:p-7">
      <div className="flex items-start justify-between gap-4"><div><span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-blue-600">Decision composer</span><h1 id="decision-title" className="mt-2 text-3xl font-semibold tracking-[-0.045em]">What decision is the company considering?</h1><p className="mt-2 max-w-xl text-xs leading-5 text-zinc-500">Describe any proposed company decision. The backend will resolve known entities, create a reviewable brief, and ask every department to assess its exposure.</p></div><Button variant="ghost" size="icon" disabled={submitting} className="shrink-0 text-zinc-400" onClick={onClose} aria-label="Close decision composer"><X /></Button></div>

      {run && submitting ? <RunProgress run={run} /> : <form className="mt-7 space-y-6" onSubmit={(event) => void submit(event)}>
        {!user ? <div className="flex flex-col gap-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 sm:flex-row sm:items-center sm:justify-between"><div><strong className="text-sm text-amber-950">Sign in to create a decision run</strong><p className="mt-1 text-[11px] text-amber-900/70">Decision drafts and runs are tied to a workspace identity.</p></div><Button asChild className="shrink-0 bg-zinc-950 text-white"><Link href="/login?next=/simulate">Sign in <ChevronRight /></Link></Button></div> : null}

        {draft ? <div className="space-y-4">
          <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4"><span className="text-[9px] font-semibold uppercase tracking-[0.15em] text-zinc-500">Review interpreted decision</span><h2 className="mt-2 text-xl font-semibold">{draft.brief.title}</h2><p className="mt-2 text-sm leading-6 text-zinc-600">{draft.brief.statement}</p></div>
          <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-zinc-200 p-3"><span className="text-[9px] text-zinc-500">Inferred type</span><strong className="mt-1 block text-xs capitalize">{draft.brief.decision_type.replaceAll("_", " ")}</strong></div><div className="rounded-xl border border-zinc-200 p-3"><span className="text-[9px] text-zinc-500">Known entities matched</span><strong className="mt-1 block text-xs">{matchedEntityIds.length}</strong></div><div className="rounded-xl border border-zinc-200 p-3"><span className="text-[9px] text-zinc-500">Departments assessing</span><strong className="mt-1 block text-xs">{assessingDepartmentIds.length}</strong></div></div>
          {matchedEntityIds.length ? <div className="flex flex-wrap gap-2">{matchedEntityIds.map((id) => <Badge key={id} variant="outline">{id}</Badge>)}</div> : null}
          {[...draftWarnings, ...draftAssumptions].map((message, index) => <p key={`${index}-${message}`} className={`rounded-xl border p-3 text-[11px] leading-5 ${index < draftWarnings.length ? "border-amber-200 bg-amber-50 text-amber-900" : "border-blue-100 bg-blue-50 text-blue-900"}`}>{message}</p>)}
          <p className="text-[10px] leading-4 text-zinc-500">Agents identify risks and missing evidence. Deterministic calculations remain unquantified when the engine has no validated rule for the proposed action, and human approval is always required.</p>
        </div> : <>
          <label><span className="mb-2 flex items-center justify-between gap-3"><span className="text-[11px] font-semibold text-zinc-600">Decision prompt</span><Button type="button" variant={listening ? "default" : "outline"} size="sm" className={listening ? "bg-rose-600 text-white hover:bg-rose-700" : ""} onClick={toggleDictation} disabled={!speechSupported}>{listening ? <MicOff /> : <Mic />}{listening ? "Stop dictation" : "Dictate"}</Button></span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} minLength={10} maxLength={4000} required placeholder="For example: Should we move customer support to a third-party provider next quarter while protecting enterprise retention and response times?" className="min-h-40 w-full rounded-xl border border-zinc-200 p-3 text-sm leading-6 outline-none focus:border-zinc-400 focus:ring-3 focus:ring-zinc-200" />{speechError ? <span className="mt-1.5 block text-[10px] text-rose-600">{speechError}</span> : <span className="mt-1.5 block text-[10px] text-zinc-500">Dictation only fills the prompt. You review the interpreted decision before it runs.</span>}</label>
          <label><span className="mb-2 block text-[11px] font-semibold text-zinc-600">Assessment horizon</span><select value={horizonDays} onChange={(event) => setHorizonDays(Number(event.target.value))} className="h-11 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm"><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>365 days</option><option value={730}>2 years</option></select></label>
        </>}

        <div className="grid gap-4 border-t border-zinc-100 pt-5 sm:grid-cols-[1fr_auto] sm:items-end"><label><span className="mb-2 block text-[10px] font-semibold text-zinc-500">Department analysis</span><select value={mode} onChange={(event) => setMode(event.target.value as AnalysisMode)} className="h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-xs sm:w-60"><option value="mock">Offline deterministic agents</option><option value="replay">Recorded agents with fallback</option><option value="live">Live department agents</option></select></label><div className="flex flex-col-reverse gap-2 sm:flex-row"><Button type="button" variant="outline" disabled={submitting || drafting} onClick={() => void onReplay()}><RotateCcw />Run saved demo</Button><Button type="submit" disabled={!user || prompt.trim().length < 10 || submitting || drafting} className="bg-zinc-950 px-5 text-white hover:bg-zinc-800">{submitting || drafting ? <LoaderCircle className="animate-spin" /> : draft ? <Play className="fill-current" /> : null}{drafting ? "Interpreting…" : submitting ? "Starting…" : draft ? "Run all departments" : "Review decision"}</Button></div></div>
        {draft ? <Button type="button" variant="ghost" className="-mt-3 text-zinc-500" onClick={() => setDraft(null)}><ChevronLeft />Back to edit</Button> : null}
        {draftError || error ? <p role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs text-rose-700">{draftError ?? error}</p> : null}
      </form>}
    </div>
  </div>;
}
