"use client";

import type { DecisionBrief, DecisionDraft, UserPublic } from "@canary-pact/contracts/generated";
import { ArrowRight, Building2, Check, ChevronLeft, ChevronRight, Clock3, FileText, Info, LoaderCircle, Mic, MicOff, Play, ShieldCheck, TriangleAlert, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

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
export function DecisionComposer({ user, submitting, error, onClose, onSubmit }: {
  user: UserPublic | null;
  submitting: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (brief: DecisionBrief, assessingDepartmentIds: string[]) => Promise<void>;
}) {
  const [prompt, setPrompt] = useState("");
  const [horizonDays, setHorizonDays] = useState(365);
  const [draft, setDraft] = useState<DecisionDraft | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const promptBeforeSpeechRef = useRef("");
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const titleRef = useRef<HTMLHeadingElement | null>(null);
  const promptRef = useRef<HTMLTextAreaElement | null>(null);
  const busy = submitting || drafting;

  useEffect(() => {
    const dialog = dialogRef.current;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    return () => { dialog?.close(); previouslyFocused?.focus(); };
  }, []);

  useEffect(() => {
    if (draft) titleRef.current?.focus();
    else promptRef.current?.focus();
    dialogRef.current?.querySelector("[data-composer-content]")?.scrollTo(0, 0);
  }, [draft]);

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
    if (!user || prompt.trim().length < 10 || busy) return;
    if (draft) { await onSubmit(draft.brief, draft.assessing_department_ids ?? []); return; }
    recognitionRef.current?.stop();
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

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="decision-title"
      aria-describedby="decision-description"
      onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}
      onClick={(event) => {
        if (busy || event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
      }}
      className="fixed inset-0 m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-[720px] overflow-hidden rounded-3xl border border-zinc-200/80 bg-white p-0 text-foreground shadow-[0_32px_100px_rgb(15_23_42/.24)] backdrop:bg-slate-950/35 backdrop:backdrop-blur-sm"
    >
      <form className="flex max-h-[calc(100dvh-2rem-2px)] flex-col" aria-busy={busy} onSubmit={(event) => void submit(event)}>
        <header className="shrink-0 border-b border-zinc-100 px-5 pb-5 pt-5 sm:px-8 sm:pt-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
              <span className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600"><FileText aria-hidden="true" className="size-4" /></span>
              Decision composer
            </div>
            <Button type="button" variant="ghost" size="icon" disabled={busy} className="size-8 rounded-full text-zinc-400 hover:bg-zinc-100" onClick={onClose} aria-label="Close decision composer"><X /></Button>
          </div>
          <h1 ref={titleRef} tabIndex={-1} id="decision-title" className="mt-5 text-2xl font-semibold leading-tight tracking-[-0.035em] outline-none sm:text-[28px]">{draft ? "Review your decision" : "What change are you considering?"}</h1>
          <p id="decision-description" className="mt-2 text-sm leading-6 text-zinc-500">{draft ? "Check the interpretation and assumptions before departments assess the impact." : "Describe the change and what you want to achieve. You’ll review a brief before any analysis begins."}</p>
          <ol aria-label="Decision progress" className="mt-5 flex items-center gap-3 text-xs">
            <li aria-current={!draft ? "step" : undefined} className={`flex items-center gap-2 ${draft ? "text-zinc-500" : "font-medium text-slate-800"}`}><span className={`grid size-5 place-items-center rounded-full text-[10px] ${draft ? "bg-emerald-50 text-emerald-700" : "bg-slate-800 text-white"}`}>{draft ? <Check aria-hidden="true" className="size-3" /> : "1"}</span>Describe</li>
            <li aria-hidden="true" className="h-px w-8 bg-zinc-200" />
            <li aria-current={draft ? "step" : undefined} className={`flex items-center gap-2 ${draft ? "font-medium text-slate-800" : "text-zinc-400"}`}><span className={`grid size-5 place-items-center rounded-full text-[10px] ${draft ? "bg-slate-800 text-white" : "border border-zinc-200"}`}>2</span>Review & run</li>
          </ol>
        </header>

        <div data-composer-content className="min-h-0 space-y-5 overflow-y-auto overscroll-contain px-5 py-5 sm:px-8 sm:py-6">
          {!user ? <div className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 sm:flex-row sm:items-center sm:justify-between"><div><strong className="text-sm text-amber-950">Sign in to create a decision run</strong><p className="mt-1 text-xs text-amber-900/70">Save drafts and analysis to your workspace.</p></div><Button asChild className="shrink-0 bg-zinc-950 text-white"><Link href="/login?next=/simulate">Sign in <ChevronRight /></Link></Button></div> : null}

          {draft ? <>
            <section aria-label="Interpreted decision" className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/60">
              <div className="p-4 sm:p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500"><span>Interpreted decision</span><span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-medium normal-case tracking-normal">Draft · for review</span></div>
                <h2 className="mt-3 break-words text-xl font-semibold leading-snug tracking-[-0.025em] sm:text-[22px]">{draft.brief.title}</h2>
                <p className="mt-2 break-words text-sm leading-6 text-zinc-500">{draft.brief.statement}</p>
              </div>
              <dl className="grid grid-cols-2 divide-x divide-slate-200 border-t border-slate-200 bg-white/70 py-4 sm:grid-cols-3">
                <div className="min-w-0 px-4 sm:px-5"><dt className="text-[11px] text-zinc-500">Decision type</dt><dd className="mt-1.5 break-words text-sm font-semibold capitalize">{draft.brief.decision_type.replaceAll("_", " ")}</dd></div>
                <div className="px-4 sm:px-5"><dt className="text-[11px] text-zinc-500">Departments assessing</dt><dd className="mt-1.5 text-sm font-semibold tabular-nums">{assessingDepartmentIds.length}</dd></div>
                <div className="col-span-2 mt-4 flex items-center gap-2 border-t border-slate-200 px-4 pt-3 text-zinc-500 sm:col-span-1 sm:mt-0 sm:block sm:border-t-0 sm:px-5 sm:pt-0"><dt className="flex items-center gap-1.5 text-[11px]"><Clock3 aria-hidden="true" className="size-3" />Time horizon</dt><dd className="text-xs font-semibold text-foreground sm:mt-1.5 sm:text-sm">{draft.brief.horizon_days ?? horizonDays} days</dd></div>
              </dl>
            </section>

            <section aria-label="Matched entities" className="flex flex-wrap items-center gap-2.5">
              <span className="mr-1 text-xs text-zinc-500">Matched entities <span className="ml-1 text-zinc-400">{matchedEntityIds.length}</span></span>
              {matchedEntityIds.length ? matchedEntityIds.map((id) => <span key={id} title={id} className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600"><Building2 aria-hidden="true" className="size-3.5 shrink-0 text-zinc-400" /><span className="break-all capitalize">{id.replace(/^(dept|vendor|employee|workflow|system|dataset|kpi)_/, "").replaceAll("_", " ")}</span></span>) : <span className="text-xs text-zinc-500">No known entities matched.</span>}
            </section>

            {draftWarnings.length ? <section aria-labelledby="decision-warnings" className="rounded-xl border border-amber-200 bg-amber-50/70 p-4"><h3 id="decision-warnings" className="flex items-center gap-2 text-xs font-semibold text-amber-900"><TriangleAlert aria-hidden="true" className="size-4" />Needs attention</h3><ul className="mt-3 space-y-2.5 pl-6 text-xs leading-5 text-amber-900">{draftWarnings.map((message, index) => <li key={`${index}-${message}`} className="list-disc break-words pl-1 marker:text-amber-400">{message}</li>)}</ul></section> : null}

            {draftAssumptions.length ? <section aria-labelledby="decision-assumptions" className="rounded-xl border border-zinc-200 p-4"><h3 id="decision-assumptions" className="flex items-center gap-2 text-xs font-semibold text-zinc-700"><Info aria-hidden="true" className="size-4 text-slate-400" />Assumptions to review<span className="ml-auto font-normal text-zinc-400">{draftAssumptions.length}</span></h3><ul className="mt-3 space-y-2.5 pl-6 text-xs leading-5 text-zinc-600">{draftAssumptions.map((message, index) => <li key={`${index}-${message}`} className="list-disc break-words pl-1 marker:text-zinc-300">{message}</li>)}</ul></section> : null}

            <div className="flex items-start gap-2.5 text-[11px] leading-[18px] text-zinc-500"><ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-slate-400" /><p><span className="font-medium text-zinc-600">Analysis only. You stay in control.</span> Agents flag risks and missing evidence. Impacts without validated calculation rules remain unquantified. Real decisions require human approval.</p></div>
          </> : <>
            <div>
              <div className="mb-2.5 flex items-center justify-between gap-3"><label htmlFor="decision-prompt" className="text-xs font-semibold text-zinc-700">Your proposed decision</label><Button type="button" variant="ghost" size="sm" className={listening ? "bg-rose-50 text-rose-700 hover:bg-rose-100" : "text-zinc-500 hover:bg-zinc-100"} onClick={toggleDictation} disabled={!speechSupported || busy} aria-pressed={listening}>{listening ? <MicOff /> : <Mic />}{listening ? "Stop dictation" : "Dictate"}</Button></div>
              <textarea ref={promptRef} id="decision-prompt" value={prompt} disabled={busy} onChange={(event) => setPrompt(event.target.value)} minLength={10} maxLength={4000} required aria-describedby="decision-prompt-help" placeholder="For example, consolidate our data vendors while protecting the coverage our teams rely on…" className="min-h-40 w-full resize-y rounded-xl border border-zinc-200 bg-zinc-50/60 p-4 text-base leading-7 outline-none transition-shadow placeholder:text-zinc-400 focus:border-slate-400 focus:bg-white focus:ring-3 focus:ring-slate-100 disabled:opacity-60 sm:text-sm sm:leading-6" />
              <div className="mt-2 flex items-start justify-between gap-4 text-[11px] leading-4"><p id="decision-prompt-help" className={speechError ? "text-rose-600" : "text-zinc-500"}>{speechError ?? "Include your objective, timing, and anything that must be protected."}</p><span className="shrink-0 tabular-nums text-zinc-400">{prompt.length.toLocaleString()} / 4,000</span></div>
            </div>
            <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3"><Clock3 aria-hidden="true" className="size-4 text-slate-400" /><div><label htmlFor="decision-horizon" className="text-xs font-semibold text-zinc-700">Assessment horizon</label><p className="mt-0.5 text-[11px] text-zinc-500">How far ahead should we assess the effects?</p></div></div><select id="decision-horizon" value={horizonDays} disabled={busy} onChange={(event) => setHorizonDays(Number(event.target.value))} className="h-10 rounded-lg border border-zinc-200 bg-white px-3 text-base outline-none focus-visible:ring-3 focus-visible:ring-slate-200 sm:text-sm"><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>365 days</option><option value={730}>2 years</option></select></div>
          </>}
        </div>

        <footer className="shrink-0 border-t border-zinc-200/80 bg-zinc-50/70 px-5 py-4 sm:px-8">
          {draftError || error ? <p role="alert" className="mb-3 max-h-24 overflow-y-auto rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs leading-5 text-rose-700">{draftError ?? error}</p> : null}
          <div className="flex flex-col-reverse items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            {draft ? <Button type="button" variant="ghost" disabled={busy} className="h-11 px-2 text-xs text-zinc-500 hover:bg-zinc-100 sm:px-3 sm:text-sm" onClick={() => setDraft(null)}><ChevronLeft />Back to edit</Button> : <span className="hidden items-center gap-2 text-xs text-zinc-500 sm:flex"><ShieldCheck aria-hidden="true" className="size-4 text-slate-400" />Review before you run</span>}
            <Button type="submit" disabled={!user || prompt.trim().length < 10 || busy} className={`h-11 rounded-xl bg-slate-900 px-4 text-xs text-white shadow-sm hover:bg-slate-800 sm:px-5 sm:text-sm ${draft ? "" : "w-full sm:w-auto"}`}>
              {busy ? <LoaderCircle aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : draft ? <Play aria-hidden="true" className="size-3.5 fill-current" /> : null}
              <span aria-live="polite">{drafting ? "Interpreting…" : submitting ? "Starting…" : draft ? "Run department analysis" : "Review decision"}</span>
              {!draft && !busy ? <ArrowRight aria-hidden="true" /> : null}
            </Button>
          </div>
          {draft ? <p className="mt-3 text-[10px] leading-4 text-zinc-500 sm:text-right">Live department agents · Unavailable agents appear as missing perspectives.</p> : null}
        </footer>
      </form>
    </dialog>
  );
}
