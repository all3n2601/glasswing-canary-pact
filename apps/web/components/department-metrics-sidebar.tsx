"use client";

import type { DepartmentDetail, Entity, StrategicPriority } from "@canary-pact/contracts/generated";
import { Activity, AlertTriangle, Building2, CircleDollarSign, FileText, FolderKanban, GitBranch, Lightbulb, LoaderCircle, ShieldCheck, Target, Users, WalletCards, X } from "lucide-react";
import { motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatCompactCurrency } from "@/lib/formatters";
import type { DepartmentSimulationView } from "@/lib/simulation-view";

const toneStyles = {
  source: "bg-blue-50 text-blue-700",
  positive: "bg-emerald-50 text-emerald-700",
  negative: "bg-rose-50 text-rose-700",
  neutral: "bg-zinc-100 text-zinc-600",
} as const;

function formatBaseline(entity: Entity) {
  const value = entity.kpi_baseline;
  if (value === null || value === undefined) return "Not reported";
  if (entity.kpi_unit === "usd") return formatCompactCurrency(value);
  if (entity.kpi_unit === "percent") return `${value}%`;
  if (entity.kpi_unit === "days") return `${value} days`;
  return `${value}${entity.kpi_unit ? ` ${entity.kpi_unit}` : ""}`;
}

function ProjectCard({ project }: { project: Entity }) {
  const completion = Math.round((project.completion_pct ?? 0) * 100);
  return <article className="rounded-2xl border border-zinc-200 p-3.5">
    <div className="flex items-start justify-between gap-3"><strong className="text-xs leading-5">{project.name}</strong><Badge className="shrink-0 border-0 bg-blue-50 text-[9px] text-blue-700">{completion}% complete</Badge></div>
    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-100"><div className="h-full rounded-full bg-blue-500" style={{ width: `${completion}%` }} /></div>
    <div className="mt-3 grid grid-cols-2 gap-2 text-[9px] text-zinc-500">
      <span><strong className="block text-[11px] text-zinc-800">{project.remaining_cost_usd != null ? formatCompactCurrency(project.remaining_cost_usd) : "Not reported"}</strong>Remaining spend</span>
      <span><strong className="block text-[11px] text-zinc-800">{project.expected_completion_day != null ? `Day ${project.expected_completion_day}` : "Not reported"}</strong>Expected finish</span>
    </div>
    <p className="mt-3 border-t border-zinc-100 pt-3 text-[9px] leading-4 text-zinc-500">Decision checkpoint: simulate whether to continue, delay, or resequence before changing the plan.</p>
  </article>;
}

export function DepartmentMetricsSidebar({ scenarioOnly = false, departments, department, detail, detailLoading, detailError, strategicPriorities, scenarioStarted, onSelect, onClose }: { scenarioOnly?: boolean; departments: DepartmentSimulationView[]; department: DepartmentSimulationView; detail?: DepartmentDetail; detailLoading: boolean; detailError?: string; strategicPriorities: StrategicPriority[]; scenarioStarted: boolean; onSelect: (departmentId: string) => void; onClose: () => void }) {
  const ownedEntities = detail?.owned_entities ?? [];
  const projects = ownedEntities.filter((entity) => entity.type === "project");
  const baselineKpis = ownedEntities.filter((entity) => entity.type === "kpi");
  const costReviewCandidates = ownedEntities
    .filter((entity) => ["vendor", "system", "dataset"].includes(entity.type) && (entity.annual_cost_usd ?? 0) > 0)
    .sort((left, right) => (right.annual_cost_usd ?? 0) - (left.annual_cost_usd ?? 0))
    .slice(0, 3);
  const gaps = detail?.profile.gaps ?? [];

  return (
    <motion.aside
      initial={{ opacity: 0, x: 28 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 28 }}
      transition={{ duration: 0.2 }}
      className="absolute bottom-4 right-3 top-[88px] z-40 flex w-[min(420px,calc(100%-24px))] flex-col overflow-hidden rounded-[24px] border border-white bg-white/96 shadow-[0_24px_80px_rgb(0_0_0/.18)] backdrop-blur-xl sm:right-5"
      role="dialog"
      aria-label={`${department.name} department metrics`}
    >
      <header className="flex items-start justify-between gap-4 border-b border-zinc-100 p-5">
        <div className="min-w-0">
          <Badge className="border-0 bg-zinc-100 text-[9px] uppercase tracking-[.12em] text-zinc-500">{scenarioOnly ? "Scenario declaration" : "Company API data"}</Badge>
          <h2 className="mt-3 truncate text-2xl font-semibold tracking-[-.04em]">{department.name}</h2>
          <p className="mt-1 text-[11px] leading-5 text-zinc-500">{department.mission}</p>
        </div>
        <Button variant="ghost" size="icon" className="shrink-0 text-zinc-400" onClick={onClose} aria-label="Close department metrics"><X /></Button>
      </header>

      {scenarioOnly ? <p className="px-5 pt-3 text-[11px] leading-5 text-zinc-500">Proposed department. Existing projects, KPIs and qualified workflow owners have not been established.</p> : null}
      {detail && !detail.profile.agent_id ? <p className="px-5 pt-3 text-[10px] text-amber-700">Department perspective unavailable: no specialist is mapped. Cross-company reviewers can still assess the proposal.</p> : null}
      <div className="border-b border-zinc-100 px-5 py-3">
        <label className="text-[9px] font-semibold uppercase tracking-[.12em] text-zinc-400" htmlFor="department-selector">Department</label>
        <select id="department-selector" className="mt-1 h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-xs font-semibold outline-none focus:border-zinc-400" value={department.departmentId} onChange={(event) => onSelect(event.target.value)}>
          {departments.map((item) => <option key={item.departmentId} value={item.departmentId}>{item.name}</option>)}
        </select>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-5">
        <section className="grid grid-cols-2 gap-2" aria-label={scenarioStarted ? "Selected scenario metrics" : "Department baseline metrics"}>
          {[
            { label: "Modeled FTE", value: department.headcount.toLocaleString("en-US", {maximumFractionDigits: 2}), icon: Users },
            { label: "Annual budget", value: formatCompactCurrency(department.annualBudgetUsd), icon: WalletCards },
            { label: "Utilisation", value: scenarioOnly ? "Not modeled" : `${Math.round(department.utilisation * 100)}%`, icon: Activity },
            { label: "Maturity", value: scenarioOnly ? "Not modeled" : `${department.maturityLevel} / 5`, icon: Building2 },
          ].map((metric) => { const Icon = metric.icon; return <div key={metric.label} className="rounded-2xl border border-zinc-200 p-3"><Icon className="size-3.5 text-zinc-400" /><strong className="mt-3 block text-lg tracking-[-.03em]">{metric.value}</strong><span className="text-[9px] text-zinc-500">{metric.label}</span></div>; })}
        </section>

        {detailLoading ? <div className="flex items-center gap-2 rounded-2xl bg-zinc-50 p-4 text-[11px] text-zinc-500"><LoaderCircle className="size-4 animate-spin" />Loading department work and operating context…</div> : null}
        {detailError ? <div className="flex items-start gap-2 rounded-2xl border border-amber-100 bg-amber-50 p-4 text-[11px] leading-5 text-amber-900"><AlertTriangle className="mt-0.5 size-4 shrink-0" />{detailError}</div> : null}

        {!scenarioOnly && !detailLoading && !detailError ? <section>
          <h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><FolderKanban className="size-3.5" />Current projects</h3>
          {projects.length ? <div className="mt-3 space-y-2">{projects.map((project) => <ProjectCard key={project.id} project={project} />)}</div> : <div className="mt-3 rounded-2xl border border-dashed border-zinc-200 p-4 text-[11px] leading-5 text-zinc-500">No active projects are recorded for this department in the current company twin.</div>}
        </section> : null}

        {!detailLoading && !detailError && baselineKpis.length ? <section>
          <h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><Target className="size-3.5" />Current KPIs</h3>
          <div className="mt-3 grid grid-cols-2 gap-2">{baselineKpis.map((kpi) => <div key={kpi.id} className="rounded-xl border border-zinc-200 p-3"><strong className="block text-base">{formatBaseline(kpi)}</strong><span className="text-[9px] text-zinc-500">{kpi.name}</span></div>)}</div>
        </section> : null}

        {!detailLoading && !detailError && (costReviewCandidates.length || gaps.length || strategicPriorities.length) ? <section>
          <h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><Lightbulb className="size-3.5" />Decision opportunities</h3>
          <p className="mt-2 text-[10px] leading-4 text-zinc-500">Evidence-backed areas worth evaluating. These are review prompts, not predicted savings or automatic recommendations.</p>
          <div className="mt-3 space-y-2">
            {costReviewCandidates.map((entity) => <article key={entity.id} className="rounded-xl border border-emerald-100 bg-emerald-50/70 p-3"><div className="flex items-center gap-2"><CircleDollarSign className="size-3.5 text-emerald-700" /><strong className="text-[11px]">Review {entity.name}</strong></div><p className="mt-1.5 text-[10px] leading-4 text-emerald-950/70">{formatCompactCurrency(entity.annual_cost_usd ?? 0)} in annual cost is recorded. Simulate consolidation, reduction, or substitution before acting.</p></article>)}
            {gaps.slice(0, 2).map((gap) => <article key={gap.id} className="rounded-xl border border-amber-100 bg-amber-50/70 p-3"><strong className="text-[11px]">Address {gap.name}</strong><p className="mt-1.5 text-[10px] leading-4 text-amber-950/70">Recorded {gap.category} gap · severity {gap.severity}/5. Test an investment or mitigation decision against the affected work.</p></article>)}
            {strategicPriorities.slice(0, 2).map((priority) => <article key={priority.id} className="rounded-xl border border-blue-100 bg-blue-50/70 p-3"><strong className="text-[11px]">Strategic priority #{priority.rank}</strong><p className="mt-1.5 text-[10px] leading-4 text-blue-950/70">{priority.text}</p></article>)}
          </div>
        </section> : null}

        <section>
          <div className="flex items-center justify-between gap-3"><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Scenario impact</h3><Badge className={`border-0 text-[9px] ${toneStyles[department.tone]}`}>{scenarioStarted ? department.severity : "Not simulated"}</Badge></div>
          <div className="mt-3 rounded-2xl bg-zinc-50 p-4">
            <strong className="text-sm">{scenarioStarted ? department.label : "Run the simulation to reveal impact"}</strong>
            <p className="mt-2 text-[11px] leading-5 text-zinc-500">{scenarioStarted ? department.summary : "Baseline department metrics are available now. Scenario-specific impacts, evidence, and mitigations appear after a run completes."}</p>
            {scenarioStarted && Number.isFinite(department.startsAt) ? <p className="mt-2 text-[10px]">First effect: day {department.startsAt}{department.peaksAt !== undefined ? ` · Peak: day ${department.peaksAt}` : ""}</p> : null}
            {scenarioStarted && department.confidence !== undefined ? <div className="mt-3 flex items-center justify-between border-t border-zinc-200 pt-3 text-[10px]"><span className="text-zinc-500">Confidence</span><strong>{Math.round(department.confidence * 100)}%</strong></div> : null}
          </div>
        </section>

        {scenarioStarted && department.kpis.length ? <section><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Modeled KPI changes</h3><div className="mt-3 grid grid-cols-2 gap-2">{department.kpis.map((kpi,index) => <div key={`${kpi.label}-${index}`} className="rounded-xl border border-zinc-200 p-3"><strong className="block text-base">{kpi.value}</strong><span className="text-[9px] text-zinc-500">{kpi.label}</span></div>)}</div></section> : null}

        {scenarioStarted && department.workflows.length ? <section><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Affected workflows</h3><div className="mt-3 flex flex-wrap gap-2">{department.workflows.map((workflow) => <span key={workflow} className="rounded-full border border-zinc-200 px-2.5 py-1.5 text-[9px] font-medium text-zinc-600">{workflow}</span>)}</div></section> : null}

        {scenarioStarted && department.dependencyPath.length ? <section><h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><GitBranch className="size-3.5" />Dependency path</h3><ol className="mt-3 space-y-2">{department.dependencyPath.map((node, index) => <li key={`${node}-${index}`} className="flex items-center gap-2 text-[10px] text-zinc-600"><span className="grid size-5 shrink-0 place-items-center rounded-full bg-zinc-950 text-[8px] text-white">{index + 1}</span>{node}</li>)}</ol></section> : null}

        {scenarioStarted ? <section className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4"><h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-emerald-700"><ShieldCheck className="size-3.5" />Suggested mitigation</h3><p className="mt-2 text-[11px] leading-5 text-emerald-950/70">{department.mitigation}</p></section> : null}

        {scenarioStarted ? <section><h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><FileText className="size-3.5" />Evidence</h3>{!department.evidence.length ? <p className="mt-2 text-[11px] text-zinc-500">No source evidence is attached to this modeled change.</p> : null}<ul className="mt-3 space-y-2">{department.evidence.map((item) => <li key={item} className="text-[10px] text-zinc-500">• {item}</li>)}</ul></section> : null}
      </div>
    </motion.aside>
  );
}
