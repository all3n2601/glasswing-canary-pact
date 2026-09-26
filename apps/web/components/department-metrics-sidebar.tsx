"use client";

import { Activity, Building2, FileText, GitBranch, ShieldCheck, Users, WalletCards, X } from "lucide-react";
import { motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DepartmentSimulationView } from "@/lib/simulation-demo-data";

const toneStyles = {
  source: "bg-blue-50 text-blue-700",
  positive: "bg-emerald-50 text-emerald-700",
  negative: "bg-rose-50 text-rose-700",
  neutral: "bg-zinc-100 text-zinc-600",
} as const;

function formatBudget(value: number) {
  return `$${(value / 1_000_000).toFixed(1)}M`;
}

export function DepartmentMetricsSidebar({ departments, department, scenarioStarted, onSelect, onClose }: { departments: DepartmentSimulationView[]; department: DepartmentSimulationView; scenarioStarted: boolean; onSelect: (departmentId: string) => void; onClose: () => void }) {
  return (
    <motion.aside
      initial={{ opacity: 0, x: 28 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 28 }}
      transition={{ duration: 0.2 }}
      className="absolute bottom-4 right-3 top-[88px] z-40 flex w-[min(390px,calc(100%-24px))] flex-col overflow-hidden rounded-[24px] border border-white bg-white/96 shadow-[0_24px_80px_rgb(0_0_0/.18)] backdrop-blur-xl sm:right-5"
      role="dialog"
      aria-label={`${department.name} department metrics`}
    >
      <header className="flex items-start justify-between gap-4 border-b border-zinc-100 p-5">
        <div className="min-w-0">
          <Badge className="border-0 bg-zinc-100 text-[9px] uppercase tracking-[.12em] text-zinc-500">{scenarioStarted ? "Backend scenario result" : "Organization baseline"}</Badge>
          <h2 className="mt-3 truncate text-2xl font-semibold tracking-[-.04em]">{department.name}</h2>
          <p className="mt-1 text-[11px] leading-5 text-zinc-500">{department.mission}</p>
        </div>
        <Button variant="ghost" size="icon" className="shrink-0 text-zinc-400" onClick={onClose} aria-label="Close department metrics"><X /></Button>
      </header>

      <div className="border-b border-zinc-100 px-5 py-3">
        <label className="text-[9px] font-semibold uppercase tracking-[.12em] text-zinc-400" htmlFor="department-selector">Department</label>
        <select id="department-selector" className="mt-1 h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-xs font-semibold outline-none focus:border-zinc-400" value={department.departmentId} onChange={(event) => onSelect(event.target.value)}>
          {departments.map((item) => <option key={item.departmentId} value={item.departmentId}>{item.name}</option>)}
        </select>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-5">
        <section className="grid grid-cols-2 gap-2" aria-label="Department baseline metrics">
          {[
            { label: "Headcount", value: String(department.headcount), icon: Users },
            { label: "Annual budget", value: formatBudget(department.annualBudgetUsd), icon: WalletCards },
            { label: "Utilisation", value: `${Math.round(department.utilisation * 100)}%`, icon: Activity },
            { label: "Maturity", value: `${department.maturityLevel} / 5`, icon: Building2 },
          ].map((metric) => { const Icon = metric.icon; return <div key={metric.label} className="rounded-2xl border border-zinc-200 p-3"><Icon className="size-3.5 text-zinc-400" /><strong className="mt-3 block text-lg tracking-[-.03em]">{metric.value}</strong><span className="text-[9px] text-zinc-500">{metric.label}</span></div>; })}
        </section>

        <section>
          <div className="flex items-center justify-between gap-3"><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Scenario impact</h3><Badge className={`border-0 text-[9px] ${toneStyles[department.tone]}`}>{scenarioStarted ? department.severity : "Not simulated"}</Badge></div>
          <div className="mt-3 rounded-2xl bg-zinc-50 p-4">
            <strong className="text-sm">{scenarioStarted ? department.label : "Run the simulation to reveal impact"}</strong>
            <p className="mt-2 text-[11px] leading-5 text-zinc-500">{scenarioStarted ? department.summary : "Baseline department metrics are available now. Scenario-specific impacts, evidence, and mitigations appear after the sample run starts."}</p>
            {scenarioStarted ? <div className="mt-3 flex items-center justify-between border-t border-zinc-200 pt-3 text-[10px]"><span className="text-zinc-500">Confidence</span><strong>{Math.round(department.confidence * 100)}%</strong></div> : null}
          </div>
        </section>

        {scenarioStarted && department.kpis.length ? <section><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">KPIs</h3><div className="mt-3 grid grid-cols-2 gap-2">{department.kpis.map((kpi) => <div key={kpi.label} className="rounded-xl border border-zinc-200 p-3"><strong className="block text-base">{kpi.value}</strong><span className="text-[9px] text-zinc-500">{kpi.label}</span></div>)}</div></section> : null}

        {scenarioStarted && department.workflows.length ? <section><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Affected workflows</h3><div className="mt-3 flex flex-wrap gap-2">{department.workflows.map((workflow) => <span key={workflow} className="rounded-full border border-zinc-200 px-2.5 py-1.5 text-[9px] font-medium text-zinc-600">{workflow}</span>)}</div></section> : null}

        {scenarioStarted && department.findings?.length ? <section><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Agent findings</h3><ul className="mt-3 space-y-2">{department.findings.map((finding) => <li key={finding} className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-[10px] leading-4 text-amber-950/75">{finding}</li>)}</ul></section> : null}

        {scenarioStarted && department.questions?.length ? <section><h3 className="text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">Open questions</h3><ul className="mt-3 space-y-2">{department.questions.map((question) => <li key={question} className="text-[10px] leading-4 text-zinc-500">• {question}</li>)}</ul></section> : null}

        {scenarioStarted ? <section><h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><GitBranch className="size-3.5" />Dependency path</h3><ol className="mt-3 space-y-2">{department.dependencyPath.map((node, index) => <li key={`${node}-${index}`} className="flex items-center gap-2 text-[10px] text-zinc-600"><span className="grid size-5 shrink-0 place-items-center rounded-full bg-zinc-950 text-[8px] text-white">{index + 1}</span>{node}</li>)}</ol></section> : null}

        {scenarioStarted ? <section className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4"><h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-emerald-700"><ShieldCheck className="size-3.5" />Suggested mitigation</h3><p className="mt-2 text-[11px] leading-5 text-emerald-950/70">{department.mitigation}</p></section> : null}

        {scenarioStarted ? <section><h3 className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400"><FileText className="size-3.5" />Evidence</h3><ul className="mt-3 space-y-2">{department.evidence.map((item) => <li key={item} className="text-[10px] text-zinc-500">• {item}</li>)}</ul></section> : null}
      </div>
    </motion.aside>
  );
}
