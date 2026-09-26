"use client";

import type { OrganizationProfile } from "@canary-pact/contracts";
import type { DecisionBrief, DecisionPackage, DomainGraph, RunState } from "@canary-pact/contracts/generated";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Building2, FileText, Gauge, LayoutGrid, Map, Pause, Play, Settings2, Share2, Sparkles, Users, WalletCards } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AuthControls } from "@/components/auth-controls";
import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { canaryApi, waitForPackage } from "@/lib/canary-api-client";
import { formatCompactCurrency } from "@/lib/formatters";
import { applyDecisionPackage, buildDepartmentSimulation } from "@/lib/simulation-view";

import { DecisionComposer } from "./decision-composer";
import { CompanyGraph } from "./company-graph";
import { DepartmentMetricsSidebar } from "./department-metrics-sidebar";
import { OfficeScene } from "./office-scene";
import { Brand } from "./site-header";

const chapters = [{ day: 0, label: "Decision" }, { day: 18, label: "Capacity" }, { day: 35, label: "Roadmap" }, { day: 60, label: "Customers" }, { day: 90, label: "Outcome" }] as const;
function money(value: number) {
  const absolute = Math.abs(value);
  const display = formatCompactCurrency(absolute);
  return value < 0 ? `−${display}` : display;
}

export function DecisionDashboard({ profile }: { profile: OrganizationProfile }) {
  const { user } = useAuth();
  const [composerOpen, setComposerOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"office" | "graph">("office");
  const [day, setDay] = useState(0);
  const [running, setRunning] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [decisionPackage, setDecisionPackage] = useState<DecisionPackage | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [companyGraph, setCompanyGraph] = useState<DomainGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setDay((current) => {
      if (current >= 90) { setRunning(false); return 90; }
      return Math.min(90, current + 1);
    }), 85);
    return () => window.clearInterval(timer);
  }, [running]);

  useEffect(() => {
    if (viewMode !== "graph" || companyGraph || graphLoading) return;
    let active = true;
    setGraphLoading(true);
    setGraphError(null);
    void canaryApi.companyGraph()
      .then((value) => { if (active) setCompanyGraph(value); })
      .catch((error: unknown) => { if (active) setGraphError(error instanceof Error ? error.message : "Could not load the company graph."); })
      .finally(() => { if (active) setGraphLoading(false); });
    return () => { active = false; };
  }, [companyGraph, viewMode]);

  const baselineDepartments = useMemo(() => buildDepartmentSimulation(profile), [profile]);
  const departments = useMemo(
    () => decisionPackage ? applyDecisionPackage(baselineDepartments, decisionPackage) : baselineDepartments,
    [baselineDepartments, decisionPackage],
  );
  const currentChapter = useMemo(() => [...chapters].reverse().find((chapter) => day >= chapter.day) ?? chapters[0], [day]);
  const selectedDepartment = useMemo(() => departments.find((department) => department.departmentId === selectedDepartmentId) ?? null, [departments, selectedDepartmentId]);
  const completeRun = async (runId: string) => {
    window.localStorage.setItem("canary:last-run-id", runId);
    const nextPackage = await waitForPackage(runId, 30_000, setRunState);
    setDecisionPackage(nextPackage);
    setComposerOpen(false);
    setViewMode("graph");
    setDay(0);
    setHasStarted(true);
    setRunning(true);
  };
  const replay = async () => {
    setSubmitting(true);
    setSimulationError(null);
    setRunState(null);
    try {
      const replays = await canaryApi.replays();
      if (!replays.length) throw new Error("No backend replay is available.");
      const replay = await canaryApi.playReplay(replays[0].name, 4);
      await completeRun(replay.run_id);
    } catch (error) {
      setHasStarted(false);
      setRunning(false);
      setComposerOpen(true);
      setSimulationError(error instanceof Error ? error.message : "The simulation could not be started.");
    } finally {
      setSubmitting(false);
    }
  };
  const simulate = async (brief: DecisionBrief, mode: "live" | "replay" | "mock") => {
    setSubmitting(true);
    setSimulationError(null);
    setRunState(null);
    setHasStarted(false);
    setRunning(false);
    try {
      const created = await canaryApi.createDecision(brief, mode);
      await completeRun(created.run_id);
    } catch (error) {
      setComposerOpen(true);
      setSimulationError(error instanceof Error ? error.message : "The decision run could not be completed.");
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
        { value: formatCompactCurrency(org.total_annual_budget_usd), label: "Annual budget", icon: WalletCards, tone: "bg-emerald-50 text-emerald-700" },
      ];

  return (
    <main className="relative h-dvh min-h-[640px] overflow-hidden bg-[radial-gradient(circle_at_50%_30%,#fff_0%,#f4f7f4_58%,#e8eee9_100%)]">
      {viewMode === "office" ? <section className="absolute inset-0" aria-label="Interactive company office simulation">
        <OfficeScene day={hasStarted ? day : -1} departments={departments} selectedDepartmentId={selectedDepartmentId ?? undefined} showAllDepartmentLabels onDepartmentSelect={setSelectedDepartmentId} />
      </section> : <CompanyGraph graph={companyGraph} blastRadius={decisionPackage?.blast_radius_act_now} decisionPackage={decisionPackage} day={day} loading={graphLoading} error={graphError} />}

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
          <div className="hidden items-center gap-2 px-2 text-[10px] font-medium text-zinc-500 lg:flex"><span className="size-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgb(16_185_129/.11)]" />Twin synchronized</div>
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
        <Button className="border-white bg-white/90 text-zinc-700 shadow-lg backdrop-blur hover:bg-white" variant="outline" size="sm" onClick={() => { setSelectedDepartmentId(null); setViewMode((current) => current === "office" ? "graph" : "office"); }}>{viewMode === "office" ? <Share2 /> : <LayoutGrid />}{viewMode === "office" ? "Dependency map" : "Office view"}</Button>
        {viewMode === "office" ? <Button className="border-white bg-white/90 text-zinc-700 shadow-lg backdrop-blur hover:bg-white" variant="outline" size="sm" onClick={() => setSelectedDepartmentId(selectedDepartmentId ?? departments[0]?.departmentId ?? null)}><Map />Explore departments</Button> : null}
        {hasStarted ? <div className="hidden items-center gap-3 rounded-xl border border-white bg-white/90 px-3 py-2 text-[9px] font-semibold text-zinc-500 shadow-lg backdrop-blur md:flex"><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-emerald-500" />Benefit</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-rose-500" />Risk</span></div> : null}
      </div>
      {viewMode === "office" && !selectedDepartment ? <p className="absolute bottom-5 right-5 z-10 hidden text-[9px] text-zinc-400 md:block">Drag to rotate · scroll to zoom</p> : null}

      <AnimatePresence>
        {selectedDepartment ? <DepartmentMetricsSidebar departments={departments} department={selectedDepartment} scenarioStarted={hasStarted && decisionPackage !== null} onSelect={setSelectedDepartmentId} onClose={() => setSelectedDepartmentId(null)} /> : null}
      </AnimatePresence>

      <AnimatePresence>
        {composerOpen ? <DecisionComposer user={user} submitting={submitting} run={runState} error={simulationError} onClose={() => setComposerOpen(false)} onSubmit={simulate} onReplay={replay} /> : null}
      </AnimatePresence>
    </main>
  );
}
