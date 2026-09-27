"use client";

import type { OrganizationProfile } from "@canary-pact/contracts";
import type { BlastRadius, DecisionBrief, DecisionPackage, DepartmentDetail, DomainGraph, RunState, SimulationResult } from "@canary-pact/contracts/generated";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Building2, Check, FileText, Gauge, LayoutGrid, LoaderCircle, Map as MapIcon, Pause, Play, Settings2, Share2, Sparkles, Users, WalletCards, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, useRef } from "react";

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
import { BoardReview } from "./board-review";
import { DepartmentChange } from "./department-change";
import { normalizeProfile } from "@/lib/organization-profile";
import { reconcileSlots, officePosition } from "@/lib/office-layout";
import { useRunEvents } from "@/lib/use-run-events";
import { boardParticipants } from "@/lib/run-events";
import { OfficeScene } from "./office-scene";
import { Brand } from "./site-header";

const chapters = [{ day: 0, label: "Decision" }, { day: 18, label: "Capacity" }, { day: 35, label: "Roadmap" }, { day: 60, label: "Customers" }, { day: 90, label: "Outcome" }] as const;
const runPhases: Array<{ status: RunState["status"]; label: string }> = [
  { status: "validating", label: "Validating the decision" },
  { status: "building_futures", label: "Building possible futures" },
  { status: "optimizing", label: "Checking quantified feasibility" },
  { status: "running_agents", label: "Teams are assessing exposure" },
  { status: "propagating", label: "Tracing the blast radius" },
  { status: "challenging", label: "Challenging assumptions" },
  { status: "comparing_futures", label: "Comparing futures" },
  { status: "mitigating", label: "Testing mitigations" },
  { status: "generating_package", label: "Building the decision package" },
];

function LiveRunPanel({ run, teamNames }: { run: RunState | null; teamNames: string[] }) {
  const phaseIndex = run ? runPhases.findIndex((phase) => phase.status === run.status) : -1;
  const phase = phaseIndex >= 0 ? runPhases[phaseIndex] : null;
  const completed = run?.assessment_ids?.length ?? 0;
  return <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="absolute left-3 top-[158px] z-20 w-[min(390px,calc(100%-24px))] rounded-2xl border border-white/95 bg-white/90 p-4 shadow-[0_12px_45px_rgb(40_55_50/.12)] backdrop-blur-xl sm:left-5 sm:top-[88px]">
    <div className="flex items-start justify-between gap-4"><div><span className="text-[9px] font-semibold uppercase tracking-[0.15em] text-blue-600">Live simulation</span><h2 className="mt-1 text-sm font-semibold">{phase?.label ?? "Starting live analysis"}</h2><p className="mt-1 text-[10px] text-zinc-500">{completed} live assessment{completed === 1 ? "" : "s"} received</p></div><LoaderCircle className="mt-1 size-5 shrink-0 animate-spin text-blue-600" /></div>
    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-100"><motion.div className="h-full rounded-full bg-blue-600" animate={{ width: `${Math.max(5, ((phaseIndex + 1) / runPhases.length) * 100)}%` }} /></div>
    <div className="mt-4"><span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-zinc-400">Affected teams</span><div className="mt-2 flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">{teamNames.map((name, index) => <span key={`${name}-${index}`} className="inline-flex items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[10px] font-medium text-blue-800"><Check className="size-3" />{name}</span>)}</div></div>
  </motion.section>;
}

function money(value: number) {
  const absolute = Math.abs(value);
  const display = formatCompactCurrency(absolute);
  return value < 0 ? `−${display}` : display;
}

export function DecisionDashboard({ profile: initialProfile }: { profile: OrganizationProfile }) {
  const [currentProfile, setCurrentProfile] = useState(initialProfile);
  const [snapshotProfile, setSnapshotProfile] = useState<OrganizationProfile | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const profile = snapshotProfile ?? currentProfile;
  const live = useRunEvents(runId);
  const [changeOpen, setChangeOpen] = useState(false);
  const [officePage, setOfficePage] = useState(0);
  const [resetCamera, setResetCamera] = useState(0);
  const [resultId, setResultId] = useState("baseline");
  const [preview, setPreview] = useState<{brief: DecisionBrief; result: SimulationResult; blast: BlastRadius} | null>(null);
  const runRequest = useRef<AbortController | null>(null);
  useEffect(() => () => runRequest.current?.abort(), []);
  const slots = useRef<Record<string, number>>({});
  const [layoutRevision, setLayoutRevision] = useState(0);
  const [layoutReady, setLayoutReady] = useState(false);
  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(window.localStorage.getItem(`canary:office-layout:${initialProfile.organization.id}`) ?? "{}");
      if (saved && typeof saved === "object" && !Array.isArray(saved)) {
        const entries = Object.entries(saved);
        if (entries.every(([,slot]) => Number.isInteger(slot) && slot >= 0 && slot < 10000) && new Set(entries.map(([,slot])=>slot)).size === entries.length) {
          slots.current = saved as Record<string,number>;
        }
      }
    } catch { /* Layout preferences are optional; the company remains authoritative. */ }
    setLayoutRevision(value=>value+1);
    setLayoutReady(true);
  }, [initialProfile.organization.id]);
  const { user } = useAuth();
  const [composerOpen, setComposerOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"office" | "graph" | "board">("office");
  const [day, setDay] = useState(0);
  const [running, setRunning] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [decisionPackage, setDecisionPackage] = useState<DecisionPackage | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [assessingDepartmentIds, setAssessingDepartmentIds] = useState<string[]>([]);
  const [companyGraph, setCompanyGraph] = useState<DomainGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [departmentDetails, setDepartmentDetails] = useState<Record<string, DepartmentDetail>>({});
  const [departmentDetailLoadingId, setDepartmentDetailLoadingId] = useState<string | null>(null);
  const [departmentDetailError, setDepartmentDetailError] = useState<{ departmentId: string; message: string } | null>(null);

  const results = useMemo(() => {
    const found = new Map<string, SimulationResult>();
    if (preview) found.set(preview.result.result_id, preview.result);
    for (const event of live.events) if (event.type === "simulation_completed" && "result_id" in event.payload) found.set(event.payload.result_id, event.payload as SimulationResult);
    if (decisionPackage) {
      for (const portfolio of [decisionPackage.portfolios.naive, decisionPackage.portfolios.recommended, ...(decisionPackage.portfolios.alternatives ?? [])]) if (portfolio) found.set(portfolio.result.result_id, portfolio.result);
      for (const mitigation of decisionPackage.mitigations ?? []) found.set(mitigation.after.result_id, mitigation.after);
    }
    return [...found.values()];
  }, [live.events, decisionPackage, preview]);
  const selectedResult = results.find(result => result.result_id === resultId);
  const horizon = preview?.brief.horizon_days ?? decisionPackage?.brief.horizon_days ?? 365;
  useEffect(() => {
    setDepartmentDetails({});setCompanyGraph(null);setGraphLoading(false);setSnapshotProfile(null);
    if (!runId) {setSnapshotProfile(null);return;}
    let active = true;
    void canaryApi.officeProfile(runId).then(value => {if(active) setSnapshotProfile(normalizeProfile(value));})
      .catch(error => {if(active) setSimulationError(error instanceof Error ? error.message : "Run baseline unavailable");});
    return () => {active=false;};
  }, [runId]);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setDay((current) => {
      if (current >= horizon) { setRunning(false); return horizon; }
      return Math.min(horizon, current + 1);
    }), 85);
    return () => window.clearInterval(timer);
  }, [running, horizon]);

  useEffect(() => {
    if (companyGraph) return;
    let active = true;
    setGraphLoading(true);
    setGraphError(null);
    void (runId ? canaryApi.officeGraph(runId) : canaryApi.companyGraph())
      .then((value) => { if (active) setCompanyGraph(value); })
      .catch((error: unknown) => { if (active) setGraphError(error instanceof Error ? error.message : "Could not load the company graph."); })
      .finally(() => { if (active) setGraphLoading(false); });
    return () => { active = false; };
  }, [companyGraph, viewMode, runId]);

  const baselineDepartments = useMemo(() => buildDepartmentSimulation(profile), [profile]);
  const departments = useMemo(() => {
    let base = baselineDepartments;
    if (selectedResult) {
      for (const state of selectedResult.department_states ?? []) if (!base.some(d=>d.departmentId===state.department_id) && day >= state.effective_day) {
        base = [...base, {departmentId:state.department_id,name:state.name,mission:"Proposed department",headcount:state.scenario_fte,annualBudgetUsd:state.scenario_budget_usd,utilisation:0,maturityLevel:1,position:[0,0,0],tone:"neutral",label:"Added in scenario",strength:0.25,startsAt:state.effective_day,severity:"Low",summary:state.modeling_notes?.join(" ") ?? "Capability not modeled",workflows:[],kpis:[],dependencyPath:[],evidence:[],mitigation:"Verify capability and dependencies."}];
      }
      base = applyDecisionPackage(base, decisionPackage, selectedResult).map(d => {
        const state = selectedResult.department_states?.find(s=>s.department_id===d.departmentId);
        return state && day >= state.effective_day ? {...d,headcount:state.scenario_fte,annualBudgetUsd:state.scenario_budget_usd,label:state.lifecycle==="closed"?"Closed · obligations remain":d.label, startsAt:state.lifecycle==="closed"?state.effective_day:d.startsAt, summary:[...new Set([d.summary,...(state.modeling_notes ?? [])])].join(" ")} : d;
      });
    }
    slots.current = reconcileSlots(slots.current, base.map(d=>d.departmentId));
    return base.map(d=>({...d,position:officePosition(slots.current[d.departmentId])}));
  }, [baselineDepartments, decisionPackage, selectedResult, day, layoutRevision]);
  useEffect(() => {
    if (layoutReady) try {window.localStorage.setItem(`canary:office-layout:${profile.organization.id}`, JSON.stringify(Object.fromEntries(Object.entries(slots.current).filter(([id])=>profile.departments.some(d=>d.department_id===id)))));} catch { /* Storage may be disabled. */ }
  }, [departments, layoutReady, profile.organization.id]);
  const displayedDepartments = useMemo(() => {
    if (!submitting || decisionPackage) return departments;
    const affected = new Set(assessingDepartmentIds);
    return departments.map((department) => affected.has(department.departmentId) ? {
      ...department,
      tone: "source" as const,
      label: "Live assessment in progress",
      strength: 0.7,
      startsAt: 0,
      severity: "Medium" as const,
      summary: "This team is evaluating the proposed decision.",
    } : department);
  }, [assessingDepartmentIds, decisionPackage, departments, submitting]);
  const assessingTeamNames = useMemo(() => {
    const affected = new Set(assessingDepartmentIds);
    return departments.filter((department) => affected.has(department.departmentId)).map((department) => department.name);
  }, [assessingDepartmentIds, departments]);
  const currentChapter = useMemo(() => [...chapters].reverse().find((chapter) => day >= chapter.day) ?? chapters[0], [day]);
  const selectedDepartment = useMemo(() => departments.find((department) => department.departmentId === selectedDepartmentId) ?? null, [departments, selectedDepartmentId]);
  const selectedDepartmentDetail = selectedDepartmentId ? departmentDetails[selectedDepartmentId] : undefined;
  const scenarioOnlyDepartment = Boolean(selectedDepartmentId && !profile.departments.some(d=>d.department_id===selectedDepartmentId));
  const selectedStrategicPriorities = useMemo(() => {
    const kpiIds = new Set(selectedDepartmentDetail?.profile.kpi_ids ?? []);
    return profile.organization.strategic_priorities.filter((priority) => priority.kpi_ids.some((id) => kpiIds.has(id)));
  }, [profile.organization.strategic_priorities, selectedDepartmentDetail]);
  useEffect(() => {
    if (!selectedDepartmentId || scenarioOnlyDepartment || departmentDetails[selectedDepartmentId]) return;
    let active = true;
    setDepartmentDetailLoadingId(selectedDepartmentId);
    setDepartmentDetailError(null);
    void (runId ? canaryApi.officeDepartment(runId, selectedDepartmentId) : canaryApi.department(selectedDepartmentId))
      .then((detail) => { if (active) setDepartmentDetails((current) => ({ ...current, [selectedDepartmentId]: detail })); })
      .catch((error: unknown) => {
        if (!active) return;
        setDepartmentDetailError({ departmentId: selectedDepartmentId, message: error instanceof Error ? error.message : "Could not load department details." });
      })
      .finally(() => { if (active) setDepartmentDetailLoadingId((current) => current === selectedDepartmentId ? null : current); });
    return () => { active = false; };
  }, [departmentDetails, selectedDepartmentId, runId, scenarioOnlyDepartment]);
  const completeRun = async (runId: string, signal: AbortSignal) => {
    signal.throwIfAborted();
    setRunId(runId);
    window.localStorage.setItem("canary:last-run-id", runId);
    const nextPackage = await waitForPackage(runId, 300_000, setRunState, signal);
    signal.throwIfAborted();
    setDecisionPackage(nextPackage);
    setComposerOpen(false);
    setResultId(nextPackage.recommendation?.result_id ?? (nextPackage.portfolios.recommended?.result ?? nextPackage.portfolios.naive.result).result_id);
    setDay(0);
    setHasStarted(true);
    setRunning(true);
  };
  useEffect(() => {
    const runId = window.localStorage.getItem("canary:last-run-id");
    if (!runId) return;
    let active = true;
    const controller = new AbortController();
    runRequest.current = controller;
    void canaryApi.run(runId,controller.signal)
      .then(async (state) => {
        if (!active || controller.signal.aborted) return;
        setRunId(runId);
        setRunState(state);
        if (state.status === "failed") {setSimulationError("This run failed. Its received findings remain available in Board review.");return;}
        const restored = state.package_id
          ? await canaryApi.package(runId,controller.signal)
          : await waitForPackage(runId, 300_000, (next) => { if (active && !controller.signal.aborted) setRunState(next); }, controller.signal);
        if (!active || controller.signal.aborted) return;
        setDecisionPackage(restored);
        setResultId(restored.recommendation?.result_id ?? (restored.portfolios.recommended?.result ?? restored.portfolios.naive.result).result_id);
        setHasStarted(true);
        setDay(0);
      })
      .catch(() => {
        // A missing or inaccessible prior run should not block starting a new one.
      });
    return () => { active = false; controller.abort(); };
  }, []);
  const simulate = async (brief: DecisionBrief, departmentIds: string[]) => {
    runRequest.current?.abort();
    const controller = new AbortController();
    runRequest.current = controller;
    setPreview(null);
    setRunId(null);
    setSnapshotProfile(null);
    setResultId("baseline");
    setSubmitting(true);
    setSimulationError(null);
    setRunState(null);
    setDecisionPackage(null);
    setAssessingDepartmentIds(departmentIds);
    setComposerOpen(false);
    setViewMode("office");
    setHasStarted(false);
    setRunning(false);
    try {
      const created = await canaryApi.createDecision(brief);
      await completeRun(created.run_id,controller.signal);
    } catch (error) {
      if (controller.signal.aborted) return;
      setComposerOpen(true);
      setSimulationError(error instanceof Error ? error.message : "The decision run could not be completed.");
    } finally {
      if (!controller.signal.aborted) setSubmitting(false);
    }
  };
  const closeSimulation = () => {
    runRequest.current?.abort();setSubmitting(false);setOfficePage(0);
    setRunId(null);setSnapshotProfile(null);setPreview(null);setResultId("baseline");
    window.localStorage.removeItem("canary:last-run-id");
    setRunning(false);
    setHasStarted(false);
    setDay(0);
    setDecisionPackage(null);
    setRunState(null);
    setAssessingDepartmentIds([]);
    setSelectedDepartmentId(null);
    setSimulationError(null);
    setComposerOpen(false);
    setViewMode("office");
  };
  const org = profile.organization;
  const recommendedResult = selectedResult;
  const sceneDepartments = displayedDepartments.filter(d => Math.floor(slots.current[d.departmentId]/24)===officePage);
  const officePages = Math.max(1, ...displayedDepartments.map(department=>Math.floor(slots.current[department.departmentId]/24)+1));
  useEffect(()=>{setOfficePage(page=>Math.min(page,officePages-1));},[officePages]);
  const participants = boardParticipants(live.events);
  const dependencyPaths = selectedResult?.impacts?.filter(i=>i.affected_department===selectedDepartmentId && i.first_effect_day<=day).map(i=>[...new Set([i.source_entity, ...(i.dependency_path ?? []), i.affected_department ?? ""].map(id=>companyGraph?.nodes?.find(e=>e.id===id)?.department_id ?? id))]) ?? [];
  const selectedBlast = live.events.findLast(event=>event.type==="blast_radius_ready" && "root_node_id" in event.payload && event.payload.scenario_id===selectedResult?.scenario_id)?.payload as BlastRadius | undefined;
  const packageBlast = selectedResult?.scenario_id===decisionPackage?.blast_radius_act_now.scenario_id ? decisionPackage?.blast_radius_act_now : undefined;

  const metrics = submitting
    ? [
        { value: String(assessingTeamNames.length), label: "Teams assessing", icon: Users, tone: "bg-blue-50 text-blue-700" },
        { value: String(runState?.assessment_ids?.length ?? 0), label: "Assessments received", icon: Gauge, tone: "bg-amber-50 text-amber-700" },
        { value: "Live", label: "Analysis source", icon: Sparkles, tone: "bg-emerald-50 text-emerald-700" },
      ]
    : hasStarted && selectedResult
    ? [
        { value: selectedResult ? String(departments.filter((department) => department.tone !== "neutral").length) : "…", label: "Teams affected", icon: Users, tone: "bg-blue-50 text-blue-700" },
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
      {runId && !snapshotProfile ? <div role="status" className="absolute inset-0 grid place-items-center text-sm">{simulationError ?? "Loading this run’s frozen company baseline…"}</div> : viewMode === "board" ? <BoardReview packageReady={Boolean(decisionPackage)} key={runId} runId={runId!} events={live.events} complete={live.complete} error={live.error} result={selectedResult} version={profile.twin_version} /> : viewMode === "office" ? <section className="absolute inset-0" aria-label="Interactive company office simulation">
        <OfficeScene analyzingDepartmentIds={profile.departments.filter(d=>d.agent_id && participants.some(p=>p.agentId===d.agent_id && p.status==="analyzing")).map(d=>d.department_id)} day={submitting ? 0 : hasStarted ? day : -1} departments={sceneDepartments} resetKey={resetCamera} dependencyPaths={dependencyPaths} participants={participants.map(p=>({key:p.key,name:p.agentId,status:p.status}))} selectedDepartmentId={selectedDepartmentId ?? undefined} showAllDepartmentLabels onDepartmentSelect={setSelectedDepartmentId} />
      </section> : <CompanyGraph graph={companyGraph} blastRadius={selectedBlast ?? packageBlast ?? (selectedResult?.result_id===preview?.result.result_id ? preview?.blast : undefined)} decisionPackage={decisionPackage} selectedResult={selectedResult} day={day} loading={graphLoading} error={graphError} />}

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
          <Button disabled={submitting} className="h-10 rounded-xl bg-zinc-950 px-3.5 text-white hover:bg-zinc-800 sm:px-4" onClick={() => setComposerOpen(true)}>{submitting ? <LoaderCircle className="animate-spin" /> : <Sparkles />}{submitting ? "Analyzing" : "Make a decision"}</Button>
        </div>
      </header>

      <div className={`absolute inset-x-3 top-[88px] z-20 flex justify-center transition-[right] sm:inset-x-auto sm:justify-end ${selectedDepartment ? "lg:right-[460px]" : "sm:right-5"}`}>
        <div className="grid w-full max-w-[570px] grid-cols-3 gap-2">
          {(viewMode === "board" ? [] : metrics).map((metric) => { const Icon = metric.icon; return <motion.div key={metric.label} layout className="flex min-w-0 items-center gap-2 rounded-2xl border border-white/95 bg-white/88 p-2 shadow-[0_10px_35px_rgb(40_55_50/.09)] backdrop-blur-xl sm:gap-3 sm:p-2.5"><span className={`grid size-9 shrink-0 place-items-center rounded-xl sm:size-10 ${metric.tone}`}><Icon className="size-4" /></span><div className="min-w-0"><strong className="block truncate text-xs sm:text-sm">{metric.value}</strong><span className="block truncate text-[8px] text-zinc-500 sm:text-[9px]">{metric.label}</span></div></motion.div>; })}
        </div>
      </div>

      {simulationError && !composerOpen ? <p role="alert" className="absolute top-24 left-5 z-30 max-w-sm rounded-xl bg-red-50 p-3 text-xs text-red-700">{simulationError}</p> : null}
      {submitting && viewMode === "office" ? <LiveRunPanel run={runState} teamNames={assessingTeamNames} /> : null}

      {viewMode === "board" ? null : submitting ? null : !hasStarted ? (
        <div className={`absolute bottom-5 left-1/2 z-20 w-[min(560px,calc(100%-24px))] -translate-x-1/2 rounded-2xl border border-white/95 bg-white/88 p-3 shadow-[0_12px_45px_rgb(40_55_50/.1)] backdrop-blur-xl sm:flex sm:items-center sm:justify-between sm:gap-4 sm:px-4 ${selectedDepartment ? "lg:left-[calc(50%-220px)]" : ""}`}>
          <div className="min-w-0"><span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-400">Ready to simulate</span><p className="mt-0.5 truncate text-xs font-semibold">Your organization baseline is loaded.</p></div>
          <Button className="mt-2 w-full shrink-0 bg-zinc-950 text-white hover:bg-zinc-800 sm:mt-0 sm:w-auto" onClick={() => setComposerOpen(true)}>Make a decision <ArrowRight /></Button>
        </div>
      ) : (
        <Card className={`absolute bottom-4 left-1/2 z-20 w-[min(560px,calc(100%-24px))] -translate-x-1/2 border-white/95 bg-white/90 shadow-[0_12px_45px_rgb(40_55_50/.1)] backdrop-blur-xl ${selectedDepartment ? "lg:left-[calc(50%-220px)]" : ""}`}>
          <CardContent className="grid h-[62px] grid-cols-[44px_auto_1fr_auto_36px] items-center gap-2 p-2 text-[10px] font-bold text-zinc-500 sm:grid-cols-[44px_auto_1fr_auto_auto_auto]">
            <Button className="size-11 rounded-xl bg-zinc-950 p-0 text-white hover:bg-zinc-800" type="button" onClick={() => { if (day >= horizon) setDay(0); setRunning((value) => !value); }} aria-label={running ? "Pause simulation" : "Play simulation"}>{running ? <Pause className="fill-current" /> : <Play className="fill-current" />}</Button>
            <span>Day {day}</span>
            <input className="w-full accent-zinc-950" type="range" min="0" max={horizon} value={day} onChange={(event) => { setRunning(false); setDay(Number(event.target.value)); }} aria-label="Simulation day" />
            <span>Day {horizon}</span>
            <Badge className="hidden min-w-16 justify-center border-0 bg-zinc-100 text-zinc-600 sm:inline-flex">{currentChapter.label}</Badge>
            <Button className="h-9 rounded-lg px-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950" type="button" variant="ghost" size="sm" onClick={closeSimulation} aria-label="Close simulation" title="Close simulation"><X /><span className="hidden sm:inline">Close</span></Button>
          </CardContent>
        </Card>
      )}

      <div className="absolute left-3 top-[158px] z-20 flex max-w-[calc(100%-24px)] flex-wrap gap-2 sm:left-5 sm:top-[168px]">
        {viewMode !== "board" ? <>
          <select aria-label="Select department" className="max-w-48 rounded-xl border bg-white/95 px-3 py-2 text-xs" value={selectedDepartmentId ?? ""} onChange={e=>{setSelectedDepartmentId(e.target.value || null);if(e.target.value)setOfficePage(Math.floor(slots.current[e.target.value]/24));}}><option value="">Explore {departments.length} departments</option>{departments.map(d=><option key={d.departmentId} value={d.departmentId}>{d.name}</option>)}</select>
          <button className="rounded-xl border bg-white/95 px-3 py-2 text-xs" onClick={()=>{setSelectedDepartmentId(null);setChangeOpen(true);}} disabled={submitting || Boolean(runId)}>Add department</button>
          {selectedDepartmentId && !runId ? <button className="rounded-xl border bg-white/95 px-3 py-2 text-xs" onClick={()=>setChangeOpen(true)}>Change department</button>:null}
          <button className="rounded-xl border bg-white/95 px-3 py-2 text-xs" onClick={()=>{setSelectedDepartmentId(null);setResetCamera(k=>k+1);}}>Reset camera</button>
          {officePages>1 ? <select aria-label="Office page" className="rounded-xl border bg-white p-2 text-xs" value={officePage} onChange={e=>setOfficePage(Number(e.target.value))}>{Array.from({length:officePages},(_,i)=><option key={i} value={i}>Office {i+1} of {officePages}</option>)}</select>:null}
          {results.length ? <select aria-label="Compare scenario" className="max-w-60 rounded-xl border bg-white/95 p-2 text-xs" value={resultId} onChange={e=>{setResultId(e.target.value);setRunning(false);}}><option value="baseline">Baseline company</option>{results.map(r=><option key={r.result_id} value={r.result_id}>{r.future.replaceAll("_", " ")} · {r.plan_id ?? (r.future === "inaction" ? "no action" : "preview")}</option>)}</select>:null}
          {preview ? <span className="rounded-xl bg-amber-50 p-2 text-xs text-amber-900">Deterministic preview · agent review not run</span>:null}
        </>:null}
      </div>
      <div className={`absolute left-3 z-20 flex flex-wrap items-center gap-2 sm:left-5 ${viewMode === "board" ? "bottom-4" : "bottom-28 sm:bottom-24"}`}>
        <Button className="border-white bg-white/90 text-zinc-700 shadow-lg backdrop-blur hover:bg-white" variant="outline" size="sm" onClick={() => { setSelectedDepartmentId(null); setViewMode((current) => current === "office" ? "graph" : "office"); }}>{viewMode === "office" ? <Share2 /> : <LayoutGrid />}{viewMode === "office" ? "Dependency map" : "Office view"}</Button>
        {viewMode === "office" ? <Button className="border-white bg-white/90 text-zinc-700 shadow-lg backdrop-blur hover:bg-white" variant="outline" size="sm" onClick={() => setSelectedDepartmentId(selectedDepartmentId ?? departments[0]?.departmentId ?? null)}><MapIcon />Explore departments</Button> : null}
        {runId ? <Button className="border-white bg-white/90" variant="outline" size="sm" onClick={()=>{setSelectedDepartmentId(null);setViewMode("board");}}>Board review</Button>:null}
        {hasStarted ? <div className="hidden items-center gap-3 rounded-xl border border-white bg-white/90 px-3 py-2 text-[9px] font-semibold text-zinc-500 shadow-lg backdrop-blur md:flex"><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-emerald-500" />Benefit</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-rose-500" />Risk</span></div> : null}
      </div>
      {viewMode === "office" && !selectedDepartment ? <p className="absolute bottom-5 right-5 z-10 hidden text-[9px] text-zinc-400 md:block">Drag to rotate · scroll to zoom</p> : null}

      <AnimatePresence>
        {selectedDepartment && viewMode !== "board" ? <DepartmentMetricsSidebar scenarioOnly={scenarioOnlyDepartment} departments={departments} department={selectedDepartment} detail={selectedDepartmentDetail} detailLoading={!scenarioOnlyDepartment && departmentDetailLoadingId === selectedDepartment.departmentId} detailError={!scenarioOnlyDepartment && departmentDetailError?.departmentId === selectedDepartment.departmentId ? departmentDetailError.message : undefined} strategicPriorities={selectedStrategicPriorities} scenarioStarted={hasStarted && Boolean(selectedResult)} onSelect={setSelectedDepartmentId} onClose={() => setSelectedDepartmentId(null)} /> : null}
      </AnimatePresence>

      {changeOpen ? <DepartmentChange profile={currentProfile} selectedId={selectedDepartmentId} user={user} onClose={()=>setChangeOpen(false)} onSaved={value=>{setCurrentProfile(value);setDepartmentDetails({});setCompanyGraph(null);setPreview(null);setResultId("baseline");setHasStarted(false);setRunning(false);setDay(0);}} onPreview={(brief,result,blast)=>{setPreview({brief,result,blast});setResultId(result.result_id);setHasStarted(true);setDay(brief.candidate_interventions[0]?.start_day ?? 0);setViewMode("office");}} onRun={simulate}/> : null}
      <AnimatePresence>
        {composerOpen ? <DecisionComposer user={user} submitting={submitting} error={simulationError} onClose={() => setComposerOpen(false)} onSubmit={simulate} /> : null}
      </AnimatePresence>
    </main>
  );
}
