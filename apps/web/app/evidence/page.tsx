import type { Metadata } from "next";
import { ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Evidence and assumptions · Canary Pact", description: "Inspect the evidence, confidence, and assumptions behind a simulation." };

const claims = [
  ["Engineering capacity falls by 20%", "Approved scenario input", "100%", "Direct"],
  ["Two roadmap initiatives lose critical capacity", "Synthetic capacity plan + dependency map", "82%", "Direct"],
  ["Product delivery moves by five weeks", "Roadmap sequencing model", "78%", "Indirect"],
  ["Four customer commitments become exposed", "Synthetic commitments ledger", "74%", "Delayed"],
] as const;

export default function EvidencePage() {
  return (
    <main className="min-h-screen bg-white pb-20 text-zinc-950">
      <SiteHeader />
      <section className="mx-auto grid max-w-[1320px] items-end gap-7 px-5 pb-12 pt-16 lg:grid-cols-[1.2fr_.8fr] lg:gap-20 lg:px-8 lg:pt-24">
        <div><Badge variant="outline" className="rounded-full border-zinc-200 bg-white uppercase tracking-[.14em] text-zinc-500">Synthetic demonstration evidence</Badge><h1 className="mt-5 max-w-4xl text-5xl font-semibold leading-[.96] tracking-[-.06em] sm:text-6xl lg:text-8xl">Every reported impact should be challengeable.</h1></div>
        <p className="text-sm leading-7 text-zinc-500">This view separates scenario inputs, deterministic calculations, evidence-backed dependencies, and uncertain projections.</p>
      </section>
      <Card className="mx-5 max-w-[1256px] overflow-hidden rounded-[24px] border-zinc-200 bg-white shadow-none lg:mx-auto">
        <CardHeader className="flex flex-row items-center justify-between border-b border-zinc-100 pb-6"><div><Badge variant="outline" className="rounded-full border-zinc-200 text-zinc-500 uppercase tracking-[.14em]">Decision package</Badge><CardTitle className="mt-3 font-sans text-3xl tracking-[-.035em]">Engineering capacity reduction</CardTitle></div><Badge variant="positive"><ShieldCheck />Audit trail complete</Badge></CardHeader>
        <CardContent className="overflow-x-auto p-0"><div className="min-w-[720px]" role="table" aria-label="Evidence supporting simulation impacts"><div className="grid min-h-11 grid-cols-[1.35fr_1fr_.45fr_.4fr] items-center gap-6 bg-zinc-50 px-8 text-[8px] font-extrabold tracking-[.08em] text-zinc-400 uppercase" role="row"><span>Claim</span><span>Evidence</span><span>Confidence</span><span>Timing</span></div>{claims.map(([claim, evidence, confidence, timing]) => <div className="grid min-h-[68px] grid-cols-[1.35fr_1fr_.45fr_.4fr] items-center gap-6 border-b border-zinc-100 px-8 text-[11px] text-zinc-500" role="row" key={claim}><strong className="text-xs text-zinc-950">{claim}</strong><span>{evidence}</span><span>{confidence}</span><span>{timing}</span></div>)}</div></CardContent>
        <CardFooter className="flex-col items-start justify-between gap-5 p-6 lg:flex-row lg:items-center"><p className="text-[11px] text-zinc-500"><strong className="text-zinc-950">Key assumption:</strong> platform and customer-commitment work receive the same reduction as lower-priority work.</p><Button asChild variant="ghost" className="px-0 text-zinc-950"><Link href="/compare">Compare a safer alternative <ArrowRight /></Link></Button></CardFooter>
      </Card>
    </main>
  );
}
