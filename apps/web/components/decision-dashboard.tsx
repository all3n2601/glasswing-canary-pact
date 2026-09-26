"use client";

import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Building2, Check, FileText, Gauge, LoaderCircle, Map as MapIcon, Mic, Pause, Play, Settings2, Sparkles, Users, WalletCards, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CompanyTwin, ScenarioResult } from "@canary-pact/contracts";
import type { AgentOutput } from "@canary-pact/contracts/generated";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getCompany, getScenarioAssessments, simulateScenario } from "@/lib/api";
import { organizationProfile } from "@/lib/organization-data";
import { demoDepartmentSimulation, type DepartmentSimulationView } from "@/lib/simulation-demo-data";

import { DepartmentMetricsSidebar } from "./department-metrics-sidebar";
import { OfficeScene } from "./office-scene";
import { Brand } from "./site-header";

const chapters = [{ day: 0, label: "Decision" }, { day: 18, label: "Capacity" }, { day: 35, label: "Roadmap" }, { day: 60, label: "Customers" }, { day: 90, label: "Outcome" }] as const;
const examples = [
  { label: "Consolidate redundant data providers", vendorIds: ["vendor_cloud", "vendor_enrichiq"] },
  { label: "Evaluate removing EnrichIQ", vendorIds: ["vendor_enrichiq"] },
  { label: "Stress-test the compliance provider", vendorIds: ["vendor_auditlog"] },
] as const;

const severityOrder = { low: 0, medium: 1, high: 2, critical: 3 } as const;

function formatMoney(value: number) {
  if (Math.abs(value) >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  return `$${(value / 1_000_000).toFixed(1)}M`;
}

function liveDepartmentViews(
  result: ScenarioResult | null,
  assessments: Record<string, AgentOutput>,
  company: CompanyTwin | null,
): DepartmentSimulationView[] {
  if (!result) return demoDepartmentSimulation;
  const entityNames = new Map(company?.entities.map((entity) => [entity.id, entity.name]) ?? []);

  return demoDepartmentSimulation.map((department) => {
    const impacts = result.impacts.filter((impact) => impact.department === department.departmentId);
    const assessment = assessments[department.departmentId];
    if (!impacts.length && !assessment) {
      return {
        ...department,
        tone: "neutral",
        label: "No material impact",
        severity: "Protected",
        confidence: 1,
        summary: "No material impact was returned for this department.",
        workflows: [],
        kpis: [],
        dependencyPath: [department.name],
        evidence: ["Deterministic simulation result"],
        mitigation: result.recommendation,
      };
    }

    const highestImpact = [...impacts].sort(
      (left, right) => severityOrder[right.severity] - severityOrder[left.severity],
    )[0];
    const severity = highestImpact
      ? ({ low: "Low", medium: "Medium", high: "High", critical: "High" } as const)[highestImpact.severity]
      : "Protected";
    const evidence = assessment?.evidence_refs?.length
      ? assessment.evidence_refs
      : ["Deterministic simulation result"];
    const affectedEntities = assessment?.affected_entities?.length
      ? assessment.affected_entities
      : impacts.map((impact) => impact.entityId);
    const path = highestImpact?.path ?? affectedEntities;

    return {
      ...department,
      tone: impacts.length ? "negative" : "neutral",
      label: impacts.length ? (impacts.length === 1 ? "1 modeled impact" : `${impacts.length} modeled impacts`) : "Department assessment",
      strength: impacts.length ? 0.65 : 0.3,
      startsAt: 0,
      severity,
      confidence: assessment?.confidence ?? highestImpact?.confidence ?? 0,
      summary: assessment?.act_now_view.summary ?? highestImpact?.description ?? "Department review completed.",
      workflows: affectedEntities.map((id) => entityNames.get(id) ?? id),
      kpis: [],
      dependencyPath: path.map((id) => entityNames.get(id) ?? id),
      evidence,
      mitigation: result.recommendation,
      findings: [
        ...(assessment?.act_now_view.failure_modes?.map((finding) => finding.text) ?? []),
        ...(assessment?.act_now_view.edge_cases?.map((finding) => finding.text) ?? []),
      ],
      questions: assessment?.questions?.map((question) => question.text) ?? [],
    };
  });
}

export function DecisionDashboard() {
  const [decision, setDecision] = useState("Consolidate redundant data providers");
  const [composerOpen, setComposerOpen] = useState(false);
  const [day, setDay] = useState(0);
  const [running, setRunning] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [company, setCompany] = useState<CompanyTwin | null>(null);
  const [selectedVendorIds, setSelectedVendorIds] = useState<string[]>(["vendor_cloud", "vendor_enrichiq"]);
  const [savingsTargetMillions, setSavingsTargetMillions] = useState(0.5);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [assessments, setAssessments] = useState<Record<string, AgentOutput>>({});
  const [submitting, setSubmitting] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  useEffect(() => {
    void getCompany().then(setCompany).catch(() => setCompany(null));
  }, []);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setDay((current) => {
      if (current >= 90) { setRunning(false); return 90; }
      return Math.min(90, current + 1);
    }), 85);
    return () => window.clearInterval(timer);
  }, [running]);

  const currentChapter = useMemo(() => [...chapters].reverse().find((chapter) => day >= chapter.day) ?? chapters[0], [day]);
  const departmentSimulation = useMemo(
    () => liveDepartmentViews(result, assessments, company),
    [result, assessments, company],
  );
  const selectedDepartment = useMemo(() => departmentSimulation.find((department) => department.departmentId === selectedDepartmentId) ?? null, [departmentSimulation, selectedDepartmentId]);
  const vendors = company?.entities.filter((entity) => entity.kind === "vendor") ?? [];
  const simulate = async () => {
    if (!selectedVendorIds.length) {
      setSimulationError("Select at least one vendor to evaluate.");
      return;
    }
    setSubmitting(true);
    setSimulationError(null);
    try {
      const nextResult = await simulateScenario({
        title: decision.trim(),
        objective: decision.trim(),
        removeEntityIds: selectedVendorIds,
        savingsTarget: savingsTargetMillions * 1_000_000,
        constraints: { compliance_coverage: 1 },
      });
      const nextAssessments = await getScenarioAssessments(nextResult.scenarioId);
      setResult(nextResult);
      setAssessments(nextAssessments);
      setComposerOpen(false);
      setDay(0);
      setHasStarted(true);
      setRunning(true);
    } catch (error) {
      setSimulationError(error instanceof Error ? error.message : "Simulation failed");
    } finally {
      setSubmitting(false);
    }
  };
  const org = organizationProfile.organization;
  const affectedTeamCount = new Set(result?.impacts.map((impact) => impact.department) ?? []).size;

  const metrics = hasStarted
    ? [
        { value: String(affectedTeamCount), label: "Teams affected", icon: Users, tone: "bg-blue-50 text-blue-700" },
        { value: result ? formatMoney(result.netSavings) : "—", label: "Net savings", icon: WalletCards, tone: "bg-emerald-50 text-emerald-700" },
        { value: result?.status.replace("_", " ") ?? "—", label: "Scenario status", icon: Gauge, tone: result?.status === "feasible" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700" },
      ]
    : [
        { value: String(departmentSimulation.length), label: "Departments", icon: Building2, tone: "bg-blue-50 text-blue-700" },
        { value: String(org.total_headcount_fte), label: "Modeled FTE", icon: Users, tone: "bg-violet-50 text-violet-700" },
        { value: `$${(org.total_annual_budget_usd / 1_000_000).toFixed(1)}M`, label: "Annual budget", icon: WalletCards, tone: "bg-emerald-50 text-emerald-700" },
      ];

  return (
    <main className="relative h-dvh min-h-[640px] overflow-hidden bg-[radial-gradient(circle_at_50%_30%,#fff_0%,#f4f7f4_58%,#e8eee9_100%)]">
      <section className="absolute inset-0" aria-label="Interactive company office simulation">
        <OfficeScene day={hasStarted ? day : -1} departments={departmentSimulation} selectedDepartmentId={selectedDepartmentId ?? undefined} showAllDepartmentLabels onDepartmentSelect={setSelectedDepartmentId} />
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
          <div className="hidden items-center gap-2 px-2 text-[10px] font-medium text-zinc-500 lg:flex"><span className="size-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgb(16_185_129/.11)]" />Twin synchronized</div>
          <Button className="h-10 rounded-xl bg-zinc-950 px-3.5 text-white hover:bg-zinc-800 sm:px-4" onClick={() => setComposerOpen(true)}><Sparkles />Make a decision</Button>
        </div>
      </header>

      <div className={`absolute inset-x-3 top-[88px] z-20 flex justify-center transition-[right] sm:inset-x-auto sm:justify-end ${selectedDepartment ? "lg:right-[430px]" : "sm:right-5"}`}>
        <div className="grid w-full max-w-[570px] grid-cols-3 gap-2">
          {metrics.map((metric) => { const Icon = metric.icon; return <motion.div key={metric.label} layout className="flex min-w-0 items-center gap-2 rounded-2xl border border-white/95 bg-white/88 p-2 shadow-[0_10px_35px_rgb(40_55_50/.09)] backdrop-blur-xl sm:gap-3 sm:p-2.5"><span className={`grid size-9 shrink-0 place-items-center rounded-xl sm:size-10 ${metric.tone}`}><Icon className="size-4" /></span><div className="min-w-0"><strong className="block truncate text-xs sm:text-sm">{metric.value}</strong><span className="block truncate text-[8px] text-zinc-500 sm:text-[9px]">{metric.label}</span></div></motion.div>; })}
        </div>
        {result ? <div className="mt-2 w-full max-w-[570px] rounded-2xl border border-white/95 bg-white/90 px-4 py-3 text-[10px] leading-4 text-zinc-600 shadow-[0_10px_35px_rgb(40_55_50/.09)] backdrop-blur-xl"><strong className="mr-2 text-zinc-950">Recommendation</strong>{result.recommendation}</div> : null}
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
        <Button className="border-white bg-white/90 text-zinc-700 shadow-lg backdrop-blur hover:bg-white" variant="outline" size="sm" onClick={() => setSelectedDepartmentId(selectedDepartmentId ?? departmentSimulation[0]?.departmentId ?? null)}><MapIcon />Explore departments</Button>
        {hasStarted ? <div className="hidden items-center gap-3 rounded-xl border border-white bg-white/90 px-3 py-2 text-[9px] font-semibold text-zinc-500 shadow-lg backdrop-blur md:flex"><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-emerald-500" />Benefit</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-rose-500" />Risk</span></div> : null}
      </div>
      {!selectedDepartment ? <p className="absolute bottom-5 right-5 z-10 hidden text-[9px] text-zinc-400 md:block">Drag to rotate · scroll to zoom</p> : null}

      <AnimatePresence>
        {selectedDepartment ? <DepartmentMetricsSidebar departments={departmentSimulation} department={selectedDepartment} scenarioStarted={hasStarted} onSelect={setSelectedDepartmentId} onClose={() => setSelectedDepartmentId(null)} /> : null}
      </AnimatePresence>

      <AnimatePresence>
        {composerOpen ? (
          <motion.div className="absolute inset-0 z-50 grid place-items-center bg-zinc-950/20 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => { if (event.currentTarget === event.target) setComposerOpen(false); }}>
            <motion.div role="dialog" aria-modal="true" aria-labelledby="decision-title" className="max-h-[calc(100dvh-32px)] w-full max-w-[640px] overflow-y-auto rounded-[26px] border border-white bg-white p-5 shadow-[0_30px_100px_rgb(0_0_0/.22)] sm:p-7" initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.98 }} transition={{ duration: 0.22 }}>
              <div className="flex items-start justify-between gap-4"><div><span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-blue-600">New simulation</span><h1 id="decision-title" className="mt-2 text-3xl font-semibold tracking-[-0.045em]">What decision are you considering?</h1><p className="mt-2 max-w-lg text-xs leading-5 text-zinc-500">Describe the change and its timing. You can review the interpreted scope before anything is simulated.</p></div><Button variant="ghost" size="icon" className="shrink-0 text-zinc-400" onClick={() => setComposerOpen(false)} aria-label="Close decision composer"><X /></Button></div>
              <form className="mt-7" onSubmit={(event) => { event.preventDefault(); if (decision.trim()) void simulate(); }}>
                <label className="flex min-h-[72px] items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-2.5 focus-within:border-zinc-400 focus-within:ring-3 focus-within:ring-zinc-100"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white text-blue-600 shadow-sm"><Mic className="size-5" /></span><span className="sr-only">Decision to simulate</span><Input autoFocus className="h-auto min-w-0 flex-1 border-0 bg-transparent px-0 text-sm font-semibold shadow-none focus-visible:ring-0" value={decision} onChange={(event) => setDecision(event.target.value)} placeholder="Describe a decision to simulate" /></label>
                <div className="mt-4"><span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Try an example</span><div className="mt-2 flex flex-wrap gap-2">{examples.map((example) => <button key={example.label} type="button" onClick={() => { setDecision(example.label); setSelectedVendorIds([...example.vendorIds]); }} className="rounded-full border border-zinc-200 bg-white px-3 py-2 text-[10px] font-medium text-zinc-600 transition-colors hover:border-zinc-400 hover:text-zinc-950">{example.label}</button>)}</div></div>
                <fieldset className="mt-5"><legend className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Vendors in scope</legend><div className="mt-2 grid max-h-36 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">{vendors.map((vendor) => { const selected = selectedVendorIds.includes(vendor.id); return <label key={vendor.id} className={`flex cursor-pointer items-center justify-between rounded-xl border px-3 py-2.5 text-[10px] font-semibold ${selected ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-200 text-zinc-600"}`}><span>{vendor.name}</span><input className="sr-only" type="checkbox" checked={selected} onChange={() => setSelectedVendorIds((current) => selected ? current.filter((id) => id !== vendor.id) : [...current, vendor.id])} /><span>{vendor.annualCost ? formatMoney(vendor.annualCost) : ""}</span></label>; })}</div></fieldset>
                <label className="mt-5 block"><span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Savings target, millions USD</span><Input className="mt-2" type="number" min="0" step="0.1" value={savingsTargetMillions} onChange={(event) => setSavingsTargetMillions(Number(event.target.value))} /></label>
                {simulationError ? <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[10px] text-rose-700">{simulationError}</p> : null}
                <div className="mt-7 flex items-center justify-between border-t border-zinc-100 pt-5"><span className="hidden items-center gap-2 text-[10px] text-zinc-400 sm:flex"><Check className="size-3 text-emerald-600" />Human approval remains required</span><Button type="submit" disabled={!decision.trim() || submitting} className="ml-auto bg-zinc-950 px-5 text-white hover:bg-zinc-800">{submitting ? <LoaderCircle className="animate-spin" /> : <Play className="fill-current" />}{submitting ? "Departments analyzing…" : "Simulate decision"}</Button></div>
              </form>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </main>
  );
}
