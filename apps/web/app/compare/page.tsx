import type { Metadata } from "next";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SiteHeader } from "@/components/site-header";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Compare scenarios · Canary Pact", description: "Compare possible organizational futures and their tradeoffs." };

const scenarios = [
  { name: "Reduce capacity by 20%", description: "Apply the proposed reduction evenly across engineering work.", savings: "$3.0M", risk: "$4.2M", delay: "5 weeks", status: "Higher risk", tone: "risk" },
  { name: "Protect critical capacity", description: "Preserve platform and commitment-critical teams; pause lower-priority work.", savings: "$2.4M", risk: "$1.1M", delay: "2 weeks", status: "Recommended", tone: "recommended" },
  { name: "Delay planned hiring", description: "Keep current delivery capacity and defer open headcount into next quarter.", savings: "$1.8M", risk: "$0.6M", delay: "1 week", status: "Lower impact", tone: "neutral" },
] as const;

export default function ComparePage() {
  return (
    <main className="min-h-screen bg-white pb-20 text-zinc-950">
      <SiteHeader />
      <section className="mx-auto grid max-w-[1320px] items-end gap-8 px-5 pb-14 pt-16 lg:grid-cols-[1.2fr_.8fr] lg:gap-20 lg:px-8 lg:pt-24">
        <div><Badge variant="outline" className="rounded-full border-zinc-200 bg-white uppercase tracking-[.14em] text-zinc-500">Prepared demonstration · 90 days</Badge><h1 className="mt-5 max-w-4xl text-5xl font-semibold leading-[.96] tracking-[-.06em] sm:text-6xl lg:text-8xl">Compare the futures, not just the savings.</h1></div>
        <p className="mb-2 text-sm leading-7 text-zinc-500">Every alternative is evaluated against the same company baseline, constraints, and confidence threshold.</p>
      </section>
      <section className="mx-auto grid max-w-[1320px] gap-4 px-5 lg:grid-cols-3 lg:px-8">
        {scenarios.map((scenario) => <Card className={cn("min-h-[420px] rounded-[24px] border-zinc-200 bg-white shadow-none", scenario.tone === "recommended" && "border-zinc-950 shadow-[0_18px_50px_rgb(0_0_0/.08)]")} key={scenario.name}>
          <CardHeader><Badge variant={scenario.tone === "risk" ? "negative" : scenario.tone === "recommended" ? "positive" : "secondary"} className="uppercase tracking-[.08em]">{scenario.status}</Badge><CardTitle className="mt-5 font-sans text-3xl tracking-[-.035em]">{scenario.name}</CardTitle><CardDescription className="leading-6 text-zinc-500">{scenario.description}</CardDescription></CardHeader>
          <CardContent className="mt-auto"><dl className="mb-7">{[["Cost savings", scenario.savings, "text-emerald-600"], ["Revenue at risk", scenario.risk, "text-rose-600"], ["Roadmap delay", scenario.delay, ""]].map(([label, value, color]) => <div className="flex items-center justify-between border-t border-zinc-100 py-3" key={label}><dt className="text-[10px] text-zinc-500">{label}</dt><dd className={cn("text-xl font-semibold", color)}>{value}</dd></div>)}</dl><Button asChild variant="ghost" className="px-0 text-zinc-950"><Link href="/story">View this future <ArrowRight /></Link></Button></CardContent>
        </Card>)}
      </section>
      <section className="mx-5 mt-5 flex max-w-[1256px] flex-col items-start justify-between gap-6 rounded-[24px] bg-zinc-950 p-8 text-white lg:mx-auto lg:flex-row lg:items-center">
        <div><Badge className="bg-white/10 uppercase tracking-[.14em] text-zinc-300">Human checkpoint</Badge><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em]">Canary Pact recommends. Leadership decides.</h2></div><Button asChild size="lg" className="rounded-xl bg-white text-zinc-950 hover:bg-zinc-200"><Link href="/evidence">Review the evidence</Link></Button>
      </section>
    </main>
  );
}
