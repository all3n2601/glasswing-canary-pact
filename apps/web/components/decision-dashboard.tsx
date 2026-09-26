"use client";

import type { OrganizationProfile } from "@canary-pact/contracts";
import type { DecisionPackage } from "@canary-pact/contracts/generated";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Building2, Check, FileText, Gauge, Map, Mic, Pause, Play, Settings2, Sparkles, Users, WalletCards, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { AuthControls } from "@/components/auth-controls";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { canaryApi, waitForPackage } from "@/lib/canary-api-client";
import { applyDecisionPackage, buildDepartmentSimulation } from "@/lib/simulation-demo-data";

import { DepartmentMetricsSidebar } from "./department-metrics-sidebar";
import { OfficeScene } from "./office-scene";
import { Brand } from "./site-header";

const chapters = [{ day: 0, label: "Decision" }, { day: 18, label: "Capacity" }, { day: 35, label: "Roadmap" }, { day: 60, label: "Customers" }, { day: 90, label: "Outcome" }] as const;
const examples = ["Cut $2M in annual cost without breaking compliance or critical systems"] as const;

function money(value: number) {
  const absolute = Math.abs(value);
  const display = absolute >= 1_000_000 ? `$${(absolute / 1_000_000).toFixed(1)}M` : `$${Math.round(absolute / 1_000)}K`;
  return value < 0 ? `−${display}` : display;
}

export function DecisionDashboard({ profile, connection }: { profile: OrganizationProfile; connection: "live" | "offline_fallback" }) {
  const decision = examples[0];
  const [composerOpen, setComposerOpen] = useState(false);
  const [day, setDay] = useState(0);
  const [running, setRunning] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [decisionPackage, setDecisionPackage] = useState<DecisionPackage | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setDay((current) => {
      if (current >= 90) { setRunning(false); return 90; }
      return Math.min(90, current + 1);
    }), 85);
    return () => window.clearInterval(timer);
  }, [running]);

  const baselineDepartments = useMemo(() => buildDepartmentSimulation(profile), [profile]);
  const departments = useMemo(
    () => decisionPackage ? applyDecisionPackage(baselineDepartments, decisionPackage) : baselineDepartments,
    [baselineDepartments, decisionPackage],
  );
  const currentChapter = useMemo(() => [...chapters].reverse().find((chapter) => day >= chapter.day) ?? chapters[0], [day]);
  const selectedDepartment = useMemo(() => departments.find((department) => department.departmentId === selectedDepartmentId) ?? null, [departments, selectedDepartmentId]);
  const simulate = async () => {
    setSubmitting(true);
    setSimulationError(null);
    try {
      const replay = await canaryApi.playReplay("sample_run", 4);
      window.localStorage.setItem("canary:last-run-id", replay.run_id);
      setComposerOpen(false);
      setDay(0);
      setHasStarted(true);
      setRunning(true);
      setDecisionPackage(await waitForPackage(replay.run_id));
    } catch (error) {
      setHasStarted(false);
      setRunning(false);
      setComposerOpen(true);
      setSimulationError(error instanceof Error ? error.message : "The simulation could not be started.");
    } finally {
      setSubmitting(false);
    }
  };
  const org = profile.organization;
  const recommendedResult = decisionPackage?.portfolios.recommended?.result ?? decisionPackage?.portfolios.naive.result;

  const metrics = hasStarted
    ? [
        { value: decisionPackage ? String(departments.filter((department) => department.tone !== "neutral").length) : "…", label: "Teams affected", icon: Users, tone: "bg-blue-50 text-blue-700" },
        { value: recommendedResult ? money(recommendedResult.value.gross_savings_usd) : "…", label: "Gross savings", icon: Gauge, tone: "bg-amber-50 text-amber-700" },
        { value: recommendedResult ? money(recommendedResult.value.net_value_usd) : "…", label: "Net value", icon: WalletCards, tone: "bg-rose-50 text-rose-700" },
      ]
    : [
        { value: String(departments.length), label: "Departments", icon: Building2, tone: "bg-blue-50 text-blue-700" },
        { value: String(org.total_headcount_fte), label: "Modeled FTE", icon: Users, tone: "bg-violet-50 text-violet-700" },
        { value: `$${(org.total_annual_budget_usd / 1_000_000).toFixed(1)}M`, label: "Annual budget", icon: WalletCards, tone: "bg-emerald-50 text-emerald-700" },
      ];

  return (
    <main className="relative h-dvh min-h-[640px] overflow-hidden bg-[radial-gradient(circle_at_50%_30%,#fff_0%,#f4f7f4_58%,#e8eee9_100%)]">
      <section className="absolute inset-0" aria-label="Interactive company office simulation">
        <OfficeScene day={hasStarted ? day : -1} departments={departments} selectedDepartmentId={selectedDepartmentId ?? undefined} showAllDepartmentLabels onDepartmentSelect={setSelectedDepartmentId} />
      </section>

      <header className="absolute inset-x-3 top-3 z-30 flex h-16 items-center justify-between rounded-2xl border border-white/90 bg-white/88 px-3 shadow-[0_12px_45px_rgb(40_55_50/.1)] backdrop-blur-xl sm:inset-x-5 sm:px-4">
        <div className="flex items-center gap-4">
          <Brand />
          <span className="hidden h-6 w-px bg-zinc-200 md:block" />
          <div className="hidden md:block"><strong className="block text-[11px]">{org.display_name}</strong><span className="text-[9px] text-zinc-400">Organization twin</span></div>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <nav className="hidden items-center gap-1 md:flex" aria-label="Simulation navigation">
            <Button asChild variant="ghost" size="sm" className="text-zinc-950"><Link href="/simulate"><Play />Simulation</Link></Button>
            <Button asChild variant="ghost" size="sm" className="text-zinc-500"><Link href="/story"><FileText />Storyboard</Link></Button>
            <Button asChild variant="ghost" size="sm" className="text-zinc-500"><Link href="/settings/organization"><Settings2 />Settings</Link></Button>
          </nav>
          <span className="hidden h-6 w-px bg-zinc-200 sm:block" />
          <div className="hidden items-center gap-2 px-2 text-[10px] font-medium text-zinc-500 lg:flex"><span className={`size-2 rounded-full ${connection === "live" ? "bg-emerald-500 shadow-[0_0_0_4px_rgb(16_185_129/.11)]" : "bg-amber-500"}`} />{connection === "live" ? "Twin synchronized" : "Offline baseline"}</div>
          <AuthControls compact />
          <Button className="h-10 rounded-xl bg-zinc-950 px-3.5 text-white hover:bg-zinc-800 sm:px-4" onClick={() => setComposerOpen(true)}><Sparkles />Make a decision</Button>
        </div>
      </header>

      <div className={`absolute inset-x-3 top-[88px] z-20 flex justify-center transition-[right] sm:inset-x-auto sm:justify-end ${selectedDepartment ? "lg:right-[430px]" : "sm:right-5"}`}>
        <div className="grid w-full max-w-[570px] grid-cols-3 gap-2">
          {metrics.map((metric) => { const Icon = metric.icon; return <motion.div key={metric.label} layout className="flex min-w-0 items-center gap-2 rounded-2xl border border-white/95 bg-white/88 p-2 shadow-[0_10px_35px_rgb(40_55_50/.09)] backdrop-blur-xl sm:gap-3 sm:p-2.5"><span className={`grid size-9 shrink-0 place-items-center rounded-xl sm:size-10 ${metric.tone}`}><Icon className="size-4" /></span><div className="min-w-0"><strong className="block truncate text-xs sm:text-sm">{metric.value}</strong><span className="block truncate text-[8px] text-zinc-500 sm:text-[9px]">{metric.label}</span></div></motion.div>; })}
        </div>
      </div>

      {!hasStarted ? (
        <div className="absolute bottom-5 left-1/2 z-20 w-[min(560px,calc(100%-24px))] -translate-x-1/2 rounded-2xl border border-white/95 bg-white/88 p-3 shadow-[0_12px_45px_rgb(40_55_50/.1)] backdrop-blur-xl sm:flex sm:items-center sm:justify-between sm:gap-4 sm:px-4">
          <div className="min-w-0"><span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-400">Ready to simulate</span><p className="mt-0.5 truncate text-xs font-semibold">Your organization baseline is loaded.</p></div>
          <Button className="mt-2 w-full shrink-0 bg-zinc-950 text-white hover:bg-zinc-800 sm:mt-0 sm:w-auto" onClick={() => setComposerOpen(true)}>Make a decision <ArrowRight /></Button>
        </div>
      ) : (
        <Card className="absolute bottom-4 left-1/2 z-20 w-[min(560px,calc(100%-24px))] -translate-x-1/2 border-white/95 bg-white/90 shadow-[0_12px_45px_rgb(40_55_50/.1)] backdrop-blur-xl">
          <CardContent className="grid h-[62px] grid-cols-[44px_auto_1fr_auto] items-center gap-2 p-2 pr-3 text-[10px] font-bold text-zinc-500 sm:grid-cols-[44px_auto_1fr_auto_auto]">
            <Button className="size-11 rounded-xl bg-zinc-950 p-0 text-white hover:bg-zinc-800" type="button" onClick={() => { if (day >= 90) setDay(0); setRunning((value) => !value); }} aria-label={running ? "Pause simulation" : "Play simulation"}>{running ? <Pause className="fill-current" /> : <Play className="fill-current" />}</Button>
            <span>Day {day}</span>
            <input className="w-full accent-zinc-950" type="range" min="0" max="90" value={day} onChange={(event) => { setRunning(false); setDay(Number(event.target.value)); }} aria-label="Simulation day" />
            <span>Day 90</span>
            <Badge className="hidden min-w-16 justify-center border-0 bg-zinc-100 text-zinc-600 sm:inline-flex">{currentChapter.label}</Badge>
          </CardContent>
        </Card>
      )}

      <div className="absolute bottom-4 left-3 z-20 flex items-center gap-2 sm:left-5">
        <Button className="border-white bg-white/90 text-zinc-700 shadow-lg backdrop-blur hover:bg-white" variant="outline" size="sm" onClick={() => setSelectedDepartmentId(selectedDepartmentId ?? departments[0]?.departmentId ?? null)}><Map />Explore departments</Button>
        {hasStarted ? <div className="hidden items-center gap-3 rounded-xl border border-white bg-white/90 px-3 py-2 text-[9px] font-semibold text-zinc-500 shadow-lg backdrop-blur md:flex"><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-emerald-500" />Benefit</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-rose-500" />Risk</span></div> : null}
      </div>
      {!selectedDepartment ? <p className="absolute bottom-5 right-5 z-10 hidden text-[9px] text-zinc-400 md:block">Drag to rotate · scroll to zoom</p> : null}

      <AnimatePresence>
        {selectedDepartment ? <DepartmentMetricsSidebar departments={departments} department={selectedDepartment} scenarioStarted={hasStarted && decisionPackage !== null} onSelect={setSelectedDepartmentId} onClose={() => setSelectedDepartmentId(null)} /> : null}
      </AnimatePresence>

      <AnimatePresence>
        {composerOpen ? (
          <motion.div className="absolute inset-0 z-50 grid place-items-center bg-zinc-950/20 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => { if (event.currentTarget === event.target) setComposerOpen(false); }}>
            <motion.div role="dialog" aria-modal="true" aria-labelledby="decision-title" className="w-full max-w-[640px] rounded-[26px] border border-white bg-white p-5 shadow-[0_30px_100px_rgb(0_0_0/.22)] sm:p-7" initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.98 }} transition={{ duration: 0.22 }}>
              <div className="flex items-start justify-between gap-4"><div><span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-blue-600">Prepared simulation</span><h1 id="decision-title" className="mt-2 text-3xl font-semibold tracking-[-0.045em]">Run the verified decision replay</h1><p className="mt-2 max-w-lg text-xs leading-5 text-zinc-500">This starts the backend’s saved, deterministic scenario and loads its resulting decision package.</p></div><Button variant="ghost" size="icon" className="shrink-0 text-zinc-400" onClick={() => setComposerOpen(false)} aria-label="Close decision composer"><X /></Button></div>
              <form className="mt-7" onSubmit={(event) => { event.preventDefault(); if (decision.trim()) void simulate(); }}>
                <label className="flex min-h-[72px] items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-2.5"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white text-blue-600 shadow-sm"><Mic className="size-5" /></span><span className="sr-only">Decision to simulate</span><Input readOnly className="h-auto min-w-0 flex-1 border-0 bg-transparent px-0 text-sm font-semibold shadow-none focus-visible:ring-0" value={decision} /></label>
                {simulationError ? <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-700">{simulationError}</p> : null}
                <div className="mt-7 flex items-center justify-between border-t border-zinc-100 pt-5"><span className="hidden items-center gap-2 text-[10px] text-zinc-400 sm:flex"><Check className="size-3 text-emerald-600" />Human approval remains required</span><Button type="submit" disabled={!decision.trim() || submitting} className="ml-auto bg-zinc-950 px-5 text-white hover:bg-zinc-800"><Play className="fill-current" />{submitting ? "Starting replay…" : "Simulate decision"}</Button></div>
              </form>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </main>
  );
}
