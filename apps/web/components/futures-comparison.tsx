"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { RunDataState } from "@/components/run-data-state";
import { SiteHeader } from "@/components/site-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLastDecisionPackage } from "@/lib/use-last-decision-package";
import { cn } from "@/lib/utils";

function money(value: number | null | undefined) {
  if (value === null || value === undefined) return "Not available";
  const absolute = Math.abs(value);
  const formatted = absolute >= 1_000_000 ? `$${(absolute / 1_000_000).toFixed(1)}M` : `$${Math.round(absolute / 1_000)}K`;
  return value < 0 ? `−${formatted}` : formatted;
}

export function FuturesComparison() {
  const { decisionPackage, loading, error } = useLastDecisionPackage();
  if (!decisionPackage) return <main className="min-h-screen bg-white pb-20 text-zinc-950"><SiteHeader /><RunDataState loading={loading} error={error} /></main>;

  const comparison = decisionPackage.futures;
  return (
    <main className="min-h-screen bg-white pb-20 text-zinc-950">
      <SiteHeader />
      <section className="mx-auto grid max-w-[1320px] items-end gap-8 px-5 pb-14 pt-16 lg:grid-cols-[1.2fr_.8fr] lg:gap-20 lg:px-8 lg:pt-24">
        <div><Badge variant="outline" className="rounded-full border-zinc-200 bg-white uppercase tracking-[.14em] text-zinc-500">Decision {decisionPackage.decision_id}</Badge><h1 className="mt-5 max-w-4xl text-5xl font-semibold leading-[.96] tracking-[-.06em] sm:text-6xl lg:text-8xl">Compare the futures, not just the savings.</h1></div>
        <p className="mb-2 text-sm leading-7 text-zinc-500">{comparison.headline}</p>
      </section>
      <section className="mx-auto grid max-w-[1320px] gap-4 px-5 lg:grid-cols-3 lg:px-8">
        {comparison.rows.map((row, index) => {
          const recommended = comparison.best_row_index === index;
          return <Card className={cn("min-h-[420px] rounded-[24px] border-zinc-200 bg-white shadow-none", recommended && "border-zinc-950 shadow-[0_18px_50px_rgb(0_0_0/.08)]")} key={row.result_id}>
            <CardHeader><Badge variant={recommended ? "positive" : row.feasible ? "secondary" : "negative"} className="uppercase tracking-[.08em]">{recommended ? "Best modeled future" : row.feasible ? "Feasible" : "Infeasible"}</Badge><CardTitle className="mt-5 font-sans text-3xl tracking-[-.035em]">{row.label}</CardTitle><CardDescription className="leading-6 text-zinc-500">{row.future.replaceAll("_", " ")} · {Math.round(row.p_better_than_inaction * 100)}% probability of outperforming inaction</CardDescription></CardHeader>
            <CardContent className="mt-auto"><dl className="mb-7">{[["Net value", money(row.net_value_p50_usd), "text-emerald-600"], ["Cost of delay", money(row.cost_of_delay_usd), "text-rose-600"], ["Risk score", row.risk_score.toFixed(1), ""]].map(([label, value, color]) => <div className="flex items-center justify-between border-t border-zinc-100 py-3" key={label}><dt className="text-[10px] text-zinc-500">{label}</dt><dd className={cn("text-xl font-semibold", color)}>{value}</dd></div>)}</dl><Button asChild variant="ghost" className="px-0 text-zinc-950"><Link href="/story">View this run <ArrowRight /></Link></Button></CardContent>
          </Card>;
        })}
      </section>
      <section className="mx-5 mt-5 flex max-w-[1256px] flex-col items-start justify-between gap-6 rounded-[24px] bg-zinc-950 p-8 text-white lg:mx-auto lg:flex-row lg:items-center">
        <div><Badge className="bg-white/10 uppercase tracking-[.14em] text-zinc-300">Human checkpoint</Badge><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em]">Canary Pact recommends. Leadership decides.</h2></div><Button asChild size="lg" className="rounded-xl bg-white text-zinc-950 hover:bg-zinc-200"><Link href="/evidence">Review the evidence</Link></Button>
      </section>
    </main>
  );
}
