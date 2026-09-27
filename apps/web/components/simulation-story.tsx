"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Evidence } from "@canary-pact/contracts/generated";
import { ReviewStory } from "@/components/review-story";
import { RunDataState } from "@/components/run-data-state";
import { SiteHeader } from "@/components/site-header";
import { canaryApi } from "@/lib/canary-api-client";
import { useLastDecisionPackage } from "@/lib/use-last-decision-package";
import { useRunEvents } from "@/lib/use-run-events";

export function SimulationStory() {
  const { decisionPackage, loading, error } = useLastDecisionPackage();
  const runId = decisionPackage?.run_id ?? null;
  const history = useRunEvents(runId);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceStatus, setEvidenceStatus] = useState("");
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), [runId]);
  const showEvidence = async (id: string) => {
    if (!runId) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setEvidence(null); setEvidenceStatus("Loading evidence…");
    try {
      const source = await canaryApi.officeEvidence(runId, id, controller.signal);
      if (!controller.signal.aborted) {setEvidence(source); setEvidenceStatus("");}
    } catch (reason) {
      if (!controller.signal.aborted) setEvidenceStatus(reason instanceof Error ? reason.message : "Evidence unavailable.");
    }
  };
  return <main className="min-h-screen bg-zinc-50 pb-8 text-zinc-950">
    <SiteHeader />
    <div className="mx-auto max-w-6xl px-4 py-6 md:px-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div><Link className="text-xs font-medium text-zinc-500" href="/simulate">← Back to office</Link><h1 className="mt-3 text-3xl font-semibold tracking-tight">How we reached this recommendation</h1><p className="mt-2 text-sm text-zinc-500">Follow the evidence from the original proposal to the human decision.</p></div>
        <Link className="rounded-xl border bg-white px-4 py-2 text-sm" href="/compare">Compare scenarios →</Link>
      </header>
      {!decisionPackage ? <RunDataState loading={loading} error={error} /> : <>
        <p className="mb-3 text-xs text-zinc-500">{decisionPackage.brief.title} · Recorded run {decisionPackage.run_id}</p>
        {history.error ? <p role="alert" className="mb-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">Could not load the full review history: {history.error}. Received findings and the saved package remain available.</p> : null}
        {!history.complete && !history.error ? <p role="status" className="mb-3 text-sm text-zinc-500">Loading recorded assessments and responses…</p> : null}
        <div className="flex h-[calc(100dvh-260px)] min-h-[480px] flex-col"><ReviewStory key={decisionPackage.run_id} events={history.events} complete decisionPackage={decisionPackage} onEvidence={id => void showEvidence(id)} /></div>
        {evidenceStatus || evidence ? <aside aria-label="Source evidence" aria-live="polite" className="fixed inset-x-4 bottom-4 z-30 max-h-[45vh] overflow-auto rounded-xl border border-emerald-200 bg-white p-5 shadow-xl sm:left-auto sm:w-[420px]">
          <button aria-label="Close evidence" className="float-right rounded-md border px-2 py-1 text-xs" onClick={() => {request.current?.abort(); setEvidence(null); setEvidenceStatus("");}}>Close</button>
          {evidenceStatus ? <p className="mr-14 text-sm">{evidenceStatus}</p> : null}
          {evidence ? <article><h2 className="mr-14 break-all text-sm font-semibold">Evidence · {evidence.id}</h2><p className="mt-3 text-sm leading-6">{evidence.snippet}</p><p className="mt-3 text-xs text-zinc-500">{evidence.document_id} · {evidence.source_type}</p></article> : null}</aside> : null}
      </>}
    </div>
  </main>;
}
