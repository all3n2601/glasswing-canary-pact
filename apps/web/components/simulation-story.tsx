"use client";

import type { DecisionPackage, Impact } from "@canary-pact/contracts/generated";
import { ArrowLeft, ArrowRight, Lightbulb } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { OfficeScene } from "@/components/office-scene";
import { RunDataState } from "@/components/run-data-state";
import { SiteHeader } from "@/components/site-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLastDecisionPackage } from "@/lib/use-last-decision-package";
import { cn } from "@/lib/utils";

interface StoryChapter {
  label: string;
  day: number;
  title: string;
  body: string;
  insight: string;
  tone: "source" | "negative" | "positive";
  facts: string[];
}

function magnitude(impact: Impact) {
  const value = Math.abs(impact.magnitude);
  if (impact.unit === "usd") return `$${value >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)}M` : `${Math.round(value / 1_000)}K`}`;
  return `${Number.isInteger(value) ? value : value.toFixed(2)} ${impact.unit}`;
}

function chaptersFromPackage(decisionPackage: DecisionPackage): StoryChapter[] {
  const result = decisionPackage.portfolios.recommended?.result ?? decisionPackage.portfolios.naive.result;
  const impacts = [...(result.impacts ?? [])].sort((left, right) => left.first_effect_day - right.first_effect_day).slice(0, 4);
  const chapters: StoryChapter[] = [{
    label: "Decision",
    day: 0,
    title: decisionPackage.brief.title,
    body: decisionPackage.brief.statement,
    insight: `${decisionPackage.brief.candidate_interventions.length} interventions are evaluated against ${decisionPackage.brief.constraints?.length ?? 0} constraints.`,
    tone: "source",
    facts: [`${decisionPackage.brief.horizon_days ?? 0}-day horizon`, decisionPackage.brief.decision_type.replaceAll("_", " ")],
  }];
  impacts.forEach((impact) => chapters.push({
    label: impact.level.replaceAll("_", " "),
    day: impact.first_effect_day,
    title: impact.metric.replaceAll("_", " "),
    body: `${impact.affected_entity} changes by ${magnitude(impact)} according to the ${impact.origin} result.`,
    insight: impact.assumptions?.[0] ?? `${impact.category.replaceAll("_", " ")} impact with ${Math.round(impact.confidence * 100)}% confidence.`,
    tone: impact.polarity === "harm" ? "negative" : "positive",
    facts: [`Severity ${impact.severity}`, `${Math.round(impact.confidence * 100)}% confidence`, impact.polarity],
  }));
  chapters.push({
    label: "Outcome",
    day: decisionPackage.brief.horizon_days ?? 0,
    title: "Company outcome",
    body: decisionPackage.blast_radius_act_now.outcome.headline,
    insight: decisionPackage.recommendation?.headline ?? "No recommendation was supplied by the backend.",
    tone: ["critical", "high"].includes(decisionPackage.blast_radius_act_now.outcome.risk_level) ? "negative" : "positive",
    facts: [`Risk ${decisionPackage.blast_radius_act_now.outcome.risk_level}`, result.feasible ? "Feasible" : "Infeasible", `${result.affected_department_ids?.length ?? 0} departments affected`],
  });
  return chapters;
}

export function SimulationStory() {
  const { decisionPackage, loading, error } = useLastDecisionPackage();
  const story = useMemo(() => decisionPackage ? chaptersFromPackage(decisionPackage) : [], [decisionPackage]);
  const [index, setIndex] = useState(0);
  if (!decisionPackage || !story.length) return <main className="min-h-screen bg-white pb-20 text-zinc-950"><SiteHeader /><RunDataState loading={loading} error={error} /></main>;
  const chapter = story[Math.min(index, story.length - 1)];

  return (
    <main className="min-h-screen bg-white pb-5 text-zinc-950">
      <SiteHeader />
      <header className="mx-auto grid h-20 max-w-[1500px] grid-cols-[1fr_auto] items-center px-5 md:grid-cols-[1fr_auto_1fr] md:px-7">
        <Button asChild variant="ghost" className="justify-self-start"><Link href="/simulate"><ArrowLeft />Back to office</Link></Button>
        <div className="hidden flex-col items-center gap-1 md:flex"><strong className="text-lg font-semibold tracking-[-.025em]">{decisionPackage.brief.title}</strong><span className="text-[10px] text-zinc-500">Run {decisionPackage.run_id}</span></div>
        <Button asChild variant="outline" className="justify-self-end rounded-xl border-zinc-200"><Link href="/compare">Compare scenarios</Link></Button>
      </header>

      <section className="relative mx-3 h-[calc(100vh-184px)] min-h-[660px] overflow-hidden rounded-[28px] border border-zinc-200 bg-[radial-gradient(circle_at_62%_42%,white,#f4f7f4_78%)] md:mx-auto md:max-w-[1500px]">
        <div className="absolute inset-0" aria-hidden="true"><OfficeScene day={chapter.day} interactive={false} /></div>
        <article className="absolute left-5 right-5 top-6 z-10 max-w-xl md:left-11 md:right-auto md:top-11">
          <Badge variant="outline" className="rounded-full border-zinc-200 bg-white uppercase tracking-[.14em] text-zinc-500">Chapter {index + 1} · Day {chapter.day}</Badge>
          <h1 className="mt-4 text-[clamp(2.5rem,4vw,3.9rem)] font-semibold leading-[.98] tracking-[-.055em]">{chapter.title}</h1>
          <p className="mt-4 max-w-lg text-sm leading-6 text-zinc-500">{chapter.body}</p>
          <div className="mt-5 flex flex-wrap gap-2">{chapter.facts.map((fact) => <Badge variant="outline" className="border-zinc-200 bg-white/90 px-3 py-2 shadow-none" key={fact}>{fact}</Badge>)}</div>
        </article>

        <Card className={cn("absolute bottom-28 right-4 z-10 w-[min(290px,calc(100%-32px))] rounded-[20px] border-l-4 border-zinc-200 bg-white/95 shadow-[0_18px_50px_rgb(0_0_0/.08)] backdrop-blur-xl md:bottom-28 md:right-9", chapter.tone === "negative" ? "border-l-rose-500" : chapter.tone === "positive" ? "border-l-emerald-500" : "border-l-zinc-950")}>
          <CardContent className="p-5"><span className="flex items-center gap-2 text-[9px] font-extrabold tracking-[.1em] text-zinc-500 uppercase"><Lightbulb className="size-4 text-amber-500" />What this means</span><p className="mt-2 text-base font-semibold leading-snug">{chapter.insight}</p><Link className="mt-3 inline-block text-[10px] font-bold text-zinc-950" href="/evidence">Inspect evidence and assumptions →</Link></CardContent>
        </Card>

        <Card className="absolute bottom-3 left-3 right-3 z-20 rounded-[20px] border-zinc-200 bg-white/95 shadow-[0_14px_40px_rgb(0_0_0/.07)] backdrop-blur-xl md:bottom-5 md:left-1/2 md:right-auto md:w-[min(720px,calc(100%-80px))] md:-translate-x-1/2">
          <CardContent className="grid min-h-[68px] gap-1 p-2" style={{ gridTemplateColumns: `42px repeat(${story.length}, minmax(0, 1fr)) 42px` }}>
            <Button variant="ghost" size="icon" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={index === 0} aria-label="Previous chapter"><ArrowLeft /></Button>
            {story.map((item, itemIndex) => <button className={cn("flex min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-[9px] font-bold text-zinc-500 transition-colors", itemIndex === index && "bg-zinc-100 text-zinc-950")} type="button" key={`${item.label}-${item.day}-${itemIndex}`} onClick={() => setIndex(itemIndex)}><i className={cn("grid size-6 place-items-center rounded-full bg-zinc-100 not-italic", itemIndex === index && "bg-zinc-950 text-white")}>{itemIndex + 1}</i><span className="hidden sm:block">{item.label}</span></button>)}
            <Button variant="ghost" size="icon" onClick={() => setIndex((value) => Math.min(story.length - 1, value + 1))} disabled={index === story.length - 1} aria-label="Next chapter"><ArrowRight /></Button>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
