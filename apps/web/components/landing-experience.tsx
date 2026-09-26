"use client";

import {
  ArrowRight,
  BadgeDollarSign,
  BarChart3,
  Check,
  CircleDot,
  Headphones,
  Lightbulb,
  Megaphone,
  Network,
  Play,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import Link from "next/link";
import { useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { OfficeScene } from "./office-scene";
import { SiteHeader } from "./site-header";

const orbitConcepts = [
  { label: "Evidence", icon: BadgeDollarSign, position: "left-[8%] top-[35%]", tone: "text-emerald-600" },
  { label: "Workflows", icon: Users, position: "left-[20%] top-[69%]", tone: "text-violet-600" },
  { label: "Constraints", icon: Lightbulb, position: "left-[36%] top-[14%]", tone: "text-amber-500" },
  { label: "Futures", icon: BarChart3, position: "right-[35%] top-[12%]", tone: "text-blue-600" },
  { label: "Monitoring", icon: Megaphone, position: "right-[18%] top-[68%]", tone: "text-rose-500" },
  { label: "Approval", icon: Headphones, position: "right-[7%] top-[34%]", tone: "text-cyan-600" },
] as const;

const steps = [
  { number: "01", title: "State the decision", body: "Type or speak the change you are considering. Canary Pact turns it into a clear scenario." },
  { number: "02", title: "Bring teams together", body: "Relevant department agents meet, exchange context, and trace operational dependencies." },
  { number: "03", title: "See the consequence", body: "Explore the blast radius, timeline, evidence, and safer alternatives before you commit." },
] as const;

const resultCapabilities = [
  { title: "Direct effects", detail: "Calculated from the selected intervention" },
  { title: "Dependent effects", detail: "Traced through the company graph" },
  { title: "Delayed effects", detail: "Placed on the returned simulation timeline" },
] as const;

const reveal = { hidden: { opacity: 0, y: 22 }, visible: { opacity: 1, y: 0 } };

export function LandingExperience() {
  const heroRef = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const { scrollYProgress: heroProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(heroProgress, [0, 1], [0, reduceMotion ? 0 : 80]);
  const heroOpacity = useTransform(heroProgress, [0, 0.85], [1, 0.45]);

  return (
    <main className="min-h-screen overflow-hidden bg-white text-zinc-950">
      <motion.div className="fixed inset-x-0 top-0 z-[60] h-0.5 origin-left bg-zinc-950" style={{ scaleX: scrollYProgress }} />

      <section ref={heroRef} className="relative mx-auto mt-4 min-h-[900px] max-w-[1500px] overflow-hidden rounded-[28px] border border-zinc-200 bg-white sm:mt-6 sm:min-h-[980px]">
        <SiteHeader />

        <motion.div className="relative z-20 mx-auto flex max-w-4xl flex-col items-center px-5 pt-14 text-center sm:pt-20 lg:pt-24" style={{ y: heroY, opacity: heroOpacity }}>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="flex items-center gap-2 text-[11px] font-medium text-zinc-500">
            <span className="flex items-center gap-1.5"><Sparkles className="size-3.5 text-amber-500" /> Decision intelligence</span>
            <span className="text-zinc-300">·</span>
            <span className="flex items-center gap-1.5"><ShieldCheck className="size-3.5 text-emerald-600" /> Human approved</span>
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.72, ease: [0.22, 1, 0.36, 1] }} className="mt-6 max-w-[850px] text-balance text-5xl font-semibold leading-[0.98] tracking-[-0.065em] sm:text-7xl lg:text-[88px]">
            See the ripple before the decision.
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16, duration: 0.65 }} className="mt-6 max-w-xl text-pretty text-sm leading-6 text-zinc-500 sm:text-base">
            Simulate a business decision across your organization and understand who benefits, who carries the risk, and what happens next.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24, duration: 0.65 }} className="mt-7 flex flex-col gap-2.5 sm:flex-row">
            <Button asChild size="lg" className="rounded-xl bg-zinc-950 px-5 text-white hover:bg-zinc-800"><Link href="/simulate">Run a simulation <ArrowRight /></Link></Button>
            <Button asChild size="lg" variant="outline" className="rounded-xl border-zinc-200 bg-white px-5"><Link href="/story"><Play className="size-3.5 fill-current" /> See how it works</Link></Button>
          </motion.div>
        </motion.div>

        <div className="absolute inset-x-0 bottom-[-10px] h-[590px] sm:h-[660px]" aria-label="Connected departments surrounding the organizational office twin">
          {["inset-x-[2%] top-[18%] h-[500px]", "inset-x-[12%] top-[23%] h-[420px]", "inset-x-[23%] top-[29%] h-[330px]"].map((ring, index) => (
            <motion.div key={ring} className={`absolute ${ring} rounded-[50%] border border-zinc-200/80`} animate={reduceMotion ? undefined : { rotate: index % 2 ? [0, -2, 0] : [0, 2, 0] }} transition={{ duration: 10 + index * 3, repeat: Infinity, ease: "easeInOut" }} />
          ))}

          {orbitConcepts.map((concept, index) => {
            const Icon = concept.icon;
            return (
              <motion.div key={concept.label} className={`absolute z-20 ${concept.position} hidden flex-col items-center gap-1.5 sm:flex`} initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1, y: reduceMotion ? 0 : [0, index % 2 ? -7 : 7, 0] }} transition={{ opacity: { delay: 0.45 + index * 0.06 }, scale: { delay: 0.45 + index * 0.06 }, y: { duration: 4 + index * 0.35, repeat: Infinity, ease: "easeInOut" } }}>
                <span className="grid size-12 place-items-center rounded-full border border-zinc-200 bg-white shadow-[0_8px_30px_rgb(0_0_0/.08)]"><Icon className={`size-5 ${concept.tone}`} /></span>
                <span className="rounded-full bg-white/80 px-2 py-1 text-[9px] font-semibold text-zinc-500 backdrop-blur">{concept.label}</span>
              </motion.div>
            );
          })}

          <motion.div className="absolute inset-x-4 bottom-0 z-10 mx-auto h-[380px] max-w-[720px] sm:h-[470px]" initial={{ opacity: 0, y: 55, scale: 0.94 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ delay: 0.35, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>
            <OfficeScene day={-1} interactive={false} />
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-[1320px] border-b border-zinc-200 px-5 py-12 text-center lg:px-8">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400">One decision connects every team</p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-x-10 gap-y-5 text-sm font-semibold text-zinc-400 sm:gap-x-16">
          {["Company twin", "Decision brief", "Constraints", "Simulation", "Evidence", "Approval"].map((stage) => <span key={stage}>{stage}</span>)}
        </div>
      </section>

      <section id="how-it-works" className="mx-auto grid max-w-[1320px] items-center gap-14 px-5 py-24 lg:grid-cols-[0.78fr_1.22fr] lg:px-8 lg:py-36">
        <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.35 }} transition={{ staggerChildren: 0.09 }}>
          <motion.div variants={reveal}><Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-500">The organizational twin</Badge></motion.div>
          <motion.h2 variants={reveal} className="mt-5 max-w-lg text-4xl font-semibold leading-[1.02] tracking-[-0.05em] sm:text-6xl">Your whole company, in one shared picture.</motion.h2>
          <motion.p variants={reveal} className="mt-5 max-w-md text-sm leading-6 text-zinc-500">Canary Pact maps departments, goals, capacity, dependencies, and commitments so every scenario starts with the same truth.</motion.p>
          <motion.div variants={reveal} className="mt-7"><Button asChild variant="outline" className="rounded-xl"><Link href="/evidence">Explore the evidence <ArrowRight /></Link></Button></motion.div>
        </motion.div>

        <motion.div className="relative min-h-[500px] rounded-[30px] border border-zinc-200 bg-[radial-gradient(circle_at_50%_45%,#e6f7ff_0%,#f4fbff_27%,#fff_66%)] p-5 sm:p-10" initial={{ opacity: 0, x: 35 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true, amount: 0.3 }} transition={{ duration: 0.7 }}>
          <div className="absolute inset-x-[8%] top-16 h-px bg-zinc-200" />
          <div className="absolute bottom-16 left-1/2 top-16 w-px bg-zinc-200" />
          <Card className="absolute left-[5%] top-10 w-[230px] border-zinc-200 bg-white shadow-[0_14px_45px_rgb(0_0_0/.08)] sm:left-[10%] sm:w-[270px]">
            <CardContent className="p-4"><span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Decision brief</span><p className="mt-2 text-sm font-semibold">Validated inputs and constraints</p><div className="mt-4 flex items-center gap-2 text-[10px] text-zinc-500"><span className="grid size-6 place-items-center rounded-full bg-zinc-100"><Users className="size-3" /></span>Loaded from the API</div></CardContent>
          </Card>
          <Card className="absolute right-[4%] top-[35%] w-[220px] border-emerald-100 bg-white shadow-[0_18px_55px_rgb(26_150_110/.12)] sm:right-[8%] sm:w-[255px]">
            <CardContent className="p-4"><span className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wider text-emerald-600"><CircleDot className="size-3" /> Benefit found</span><p className="mt-2 text-sm font-semibold">Calculated value is preserved</p><p className="mt-1 text-[10px] text-zinc-500">Backed by a simulation result</p></CardContent>
          </Card>
          <Card className="absolute bottom-10 left-[10%] w-[235px] border-rose-100 bg-white shadow-[0_18px_55px_rgb(220_80_80/.12)] sm:left-[19%] sm:w-[280px]">
            <CardContent className="p-4"><span className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wider text-rose-600"><CircleDot className="size-3" /> Delayed consequence</span><p className="mt-2 text-sm font-semibold">Dependencies expose downstream risk</p><p className="mt-1 text-[10px] text-zinc-500">Timed by the propagation engine</p></CardContent>
          </Card>
        </motion.div>
      </section>

      <section className="border-y border-zinc-200 bg-zinc-50/60">
        <div className="mx-auto max-w-[1320px] px-5 py-24 lg:px-8 lg:py-32">
          <motion.div className="mx-auto max-w-2xl text-center" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.4 }} transition={{ staggerChildren: 0.08 }}>
            <motion.p variants={reveal} className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-400">One understandable flow</motion.p>
            <motion.h2 variants={reveal} className="mt-4 text-4xl font-semibold leading-[1.03] tracking-[-0.05em] sm:text-6xl">From difficult question to defensible decision.</motion.h2>
          </motion.div>
          <motion.div className="mt-16 grid gap-4 md:grid-cols-3" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.25 }} transition={{ staggerChildren: 0.1 }}>
            {steps.map((step) => (
              <motion.div key={step.number} variants={reveal} whileHover={reduceMotion ? undefined : { y: -6 }}>
                <Card className="h-full min-h-[290px] rounded-[24px] border-zinc-200 bg-white shadow-none">
                  <CardContent className="flex h-full flex-col p-7"><span className="text-[10px] font-semibold text-zinc-400">{step.number}</span><span className="mt-10 grid size-10 place-items-center rounded-full bg-zinc-950 text-white">{step.number === "01" ? <Sparkles className="size-4" /> : step.number === "02" ? <Users className="size-4" /> : <Network className="size-4" />}</span><h3 className="mt-6 text-xl font-semibold tracking-[-0.025em]">{step.title}</h3><p className="mt-3 text-sm leading-6 text-zinc-500">{step.body}</p></CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      <section className="mx-auto grid max-w-[1320px] items-center gap-16 px-5 py-24 lg:grid-cols-2 lg:px-8 lg:py-36">
        <motion.div className="relative min-h-[490px] rounded-[30px] border border-zinc-200 bg-[radial-gradient(circle_at_50%_50%,#e6f7ff,#fafafa_58%,#fff)] p-6" initial={{ opacity: 0, x: -35 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true, amount: 0.3 }} transition={{ duration: 0.7 }}>
          <div className="absolute inset-x-6 top-6 flex items-center justify-between text-[9px] font-semibold uppercase tracking-wider text-zinc-400"><span>Simulation timeline</span><span>API results</span></div>
          <div className="absolute inset-x-6 top-16 space-y-3 sm:inset-x-12">
            {resultCapabilities.map((capability, index) => (
              <motion.div key={capability.title} className="grid grid-cols-[36px_1fr] items-center gap-3 rounded-2xl border border-zinc-200 bg-white p-4 shadow-[0_10px_35px_rgb(0_0_0/.06)]" initial={{ opacity: 0, y: 20, scale: 0.97 }} whileInView={{ opacity: 1, y: 0, scale: 1 }} viewport={{ once: true }} transition={{ delay: index * 0.12, duration: 0.5 }}>
                <span className="grid size-9 place-items-center rounded-full bg-zinc-100 text-zinc-700"><CircleDot className="size-4" /></span>
                <div><strong className="block text-sm">{capability.title}</strong><span className="text-[10px] text-zinc-500">{capability.detail}</span></div>
              </motion.div>
            ))}
          </div>
          <div className="absolute bottom-7 left-1/2 w-[72%] -translate-x-1/2 rounded-2xl border border-zinc-200 bg-white/90 p-4 text-center shadow-sm backdrop-blur"><span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Recommendation</span><p className="mt-1 text-sm font-semibold">Rendered from the completed decision package</p></div>
        </motion.div>

        <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.35 }} transition={{ staggerChildren: 0.09 }}>
          <motion.div variants={reveal}><Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-500">Impact storyboard</Badge></motion.div>
          <motion.h2 variants={reveal} className="mt-5 max-w-lg text-4xl font-semibold leading-[1.02] tracking-[-0.05em] sm:text-6xl">Follow the story, not just the score.</motion.h2>
          <motion.p variants={reveal} className="mt-5 max-w-md text-sm leading-6 text-zinc-500">Every result unfolds as an evidence-backed narrative—what changes first, which teams react, where uncertainty remains, and when intervention still helps.</motion.p>
          <motion.ul variants={reveal} className="mt-7 space-y-3 text-sm text-zinc-700">
            {["Positive and negative effects stay visually distinct", "Every claim links back to its source", "People keep final approval at every stage"].map((item) => <li key={item} className="flex items-center gap-2.5"><span className="grid size-5 place-items-center rounded-full bg-emerald-50 text-emerald-600"><Check className="size-3" /></span>{item}</li>)}
          </motion.ul>
          <motion.div variants={reveal} className="mt-8"><Button asChild className="rounded-xl bg-zinc-950 text-white hover:bg-zinc-800"><Link href="/story">View the full story <ArrowRight /></Link></Button></motion.div>
        </motion.div>
      </section>

      <motion.section className="mx-auto my-6 flex min-h-[480px] max-w-[1500px] flex-col items-center justify-center overflow-hidden rounded-[28px] bg-zinc-950 px-5 text-center text-white" initial={{ opacity: 0, y: 25 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.3 }}>
        <div className="relative z-10">
          <span className="mx-auto grid size-11 place-items-center rounded-2xl bg-white text-zinc-950"><Network className="size-5" /></span>
          <h2 className="mx-auto mt-7 max-w-3xl text-4xl font-semibold leading-[1.02] tracking-[-0.05em] sm:text-6xl">Make the decision after you see the consequence.</h2>
          <p className="mx-auto mt-5 max-w-lg text-sm leading-6 text-zinc-400">Load the company twin and run a backend-supported decision scenario.</p>
          <Button asChild size="lg" className="mt-8 rounded-xl bg-white px-5 text-zinc-950 hover:bg-zinc-200"><Link href="/simulate">Enter the simulation <ArrowRight /></Link></Button>
        </div>
      </motion.section>

      <footer className="mx-auto flex max-w-[1320px] flex-col items-center justify-between gap-4 px-5 py-10 text-xs text-zinc-400 sm:flex-row lg:px-8"><span className="font-semibold text-zinc-700">Canary Pact</span><span>Decision intelligence for connected organizations.</span></footer>
    </main>
  );
}
