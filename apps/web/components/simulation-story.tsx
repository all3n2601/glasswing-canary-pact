"use client";

import { ArrowLeft, ArrowRight, Lightbulb } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { OfficeScene } from "./office-scene";
import { SiteHeader } from "./site-header";

const story = [
  { label: "Decision", day: 0, title: "A cost decision enters the organization", body: "Leadership proposes reducing engineering capacity by 20% for the next quarter.", insight: "The saving is immediate. Delivery effects have not appeared yet.", tone: "source", facts: ["Engineering −20%", "90-day horizon", "72% confidence"] },
  { label: "Capacity", day: 18, title: "Teams re-plan around reduced capacity", body: "Engineering protects critical operations, leaving less capacity for planned product work.", insight: "Two initiatives become sensitive to a small additional delay.", tone: "source", facts: ["2 initiatives exposed", "Operations protected", "Finance +$3.0M"] },
  { label: "Roadmap", day: 35, title: "Roadmap pressure emerges", body: "Reduced throughput shifts Product’s expected delivery window by five weeks.", insight: "The financial benefit remains, but commercial risk is now visible.", tone: "negative", facts: ["Delay +5 weeks", "3 milestones moved", "78% confidence"] },
  { label: "Customers", day: 65, title: "Commitments reach customer-facing teams", body: "Sales and Customer Success must renegotiate expectations for affected accounts.", insight: "The strongest mitigation is protecting the two commitment-critical initiatives.", tone: "negative", facts: ["4 accounts exposed", "Churn risk +3%", "$4.2M at risk"] },
  { label: "Outcome", day: 90, title: "Savings and risk can now be compared", body: "The proposal saves operating cost, but creates more expected commercial risk than leadership intended.", insight: "Recommended: reduce lower-priority work before reducing platform capacity.", tone: "positive", facts: ["Savings +$3.0M", "Revenue risk $4.2M", "Mitigation available"] },
] as const;

export function SimulationStory() {
  const [index, setIndex] = useState(2);
  const chapter = story[index];

  return (
    <main className="min-h-screen bg-white pb-5 text-zinc-950">
      <SiteHeader />
      <header className="mx-auto grid h-20 max-w-[1500px] grid-cols-[1fr_auto] items-center px-5 md:grid-cols-[1fr_auto_1fr] md:px-7">
        <Button asChild variant="ghost" className="justify-self-start"><Link href="/simulate"><ArrowLeft />Back to office</Link></Button>
        <div className="hidden flex-col items-center gap-1 md:flex"><strong className="text-lg font-semibold tracking-[-.025em]">Engineering capacity reduction</strong><span className="text-[10px] text-zinc-500">90-day simulation · 72% confidence</span></div>
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
          <CardContent className="grid min-h-[68px] grid-cols-[42px_repeat(5,1fr)_42px] gap-1 p-2">
            <Button variant="ghost" size="icon" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={index === 0} aria-label="Previous chapter"><ArrowLeft /></Button>
            {story.map((item, itemIndex) => <button className={cn("flex min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-[9px] font-bold text-zinc-500 transition-colors", itemIndex === index && "bg-zinc-100 text-zinc-950")} type="button" key={item.label} onClick={() => setIndex(itemIndex)}><i className={cn("grid size-6 place-items-center rounded-full bg-zinc-100 not-italic", itemIndex === index && "bg-zinc-950 text-white")}>{itemIndex + 1}</i><span className="hidden sm:block">{item.label}</span></button>)}
            <Button variant="ghost" size="icon" onClick={() => setIndex((value) => Math.min(story.length - 1, value + 1))} disabled={index === story.length - 1} aria-label="Next chapter"><ArrowRight /></Button>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
