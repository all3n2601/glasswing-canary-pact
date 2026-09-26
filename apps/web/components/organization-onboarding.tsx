"use client";

import type { OrganizationProfile } from "@canary-pact/contracts";
import { ArrowLeft, ArrowRight, Building2, Check, CircleDollarSign, Network, ShieldCheck, Sparkles, Users } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatCompactCurrency } from "@/lib/formatters";

const steps = [
  { label: "Organization", icon: Building2 },
  { label: "Departments", icon: Users },
  { label: "Priorities", icon: Sparkles },
  { label: "Analysis", icon: ShieldCheck },
] as const;

const fieldLabel = "mb-2 block text-[11px] font-semibold text-zinc-600";
const fieldClass = "h-11 rounded-xl border-zinc-200 bg-white text-sm shadow-none focus-visible:border-zinc-400 focus-visible:ring-zinc-200";

export function OrganizationOnboarding({ profile }: { profile: OrganizationProfile }) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [organization, setOrganization] = useState(profile.organization);
  const [departments, setDepartments] = useState(profile.departments);
  const [riskAppetite, setRiskAppetite] = useState(profile.settings.risk_appetite);
  const [horizon, setHorizon] = useState(profile.settings.default_horizon_days);
  const enabledDepartments = departments.filter((department) => department.enabled);
  const totals = useMemo(() => ({
    headcount: enabledDepartments.reduce((sum, department) => sum + department.actual_fte, 0),
    budget: enabledDepartments.reduce((sum, department) => sum + department.annual_budget_usd, 0),
  }), [enabledDepartments]);

  const next = () => {
    if (step < steps.length - 1) setStep((current) => current + 1);
    else router.push("/settings/organization?onboarded=true");
  };

  return (
    <main className="min-h-screen bg-white p-3 text-zinc-950 sm:p-5">
      <div className="mx-auto grid min-h-[calc(100vh-24px)] max-w-[1440px] overflow-hidden rounded-[28px] border border-zinc-200 bg-white lg:grid-cols-[290px_1fr] sm:min-h-[calc(100vh-40px)]">
        <aside className="border-b border-zinc-200 bg-zinc-950 p-6 text-white lg:border-b-0 lg:border-r lg:p-8">
          <div className="flex items-center gap-2.5 font-semibold"><span className="grid size-8 place-items-center rounded-lg bg-white text-zinc-950"><Network className="size-4" /></span>Canary Pact</div>
          <p className="mt-3 text-[10px] text-zinc-500">Connected to the company API</p>
          <div className="mt-8 lg:mt-20"><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Set up your twin</p><h1 className="mt-3 text-2xl font-semibold leading-tight tracking-[-0.035em]">Give every simulation the right company context.</h1></div>
          <nav className="mt-7 grid grid-cols-4 gap-2 lg:mt-10 lg:grid-cols-1" aria-label="Onboarding progress">
            {steps.map((item, index) => {
              const Icon = item.icon;
              const active = index === step;
              const complete = index < step;
              return <button key={item.label} type="button" onClick={() => setStep(index)} className={`flex min-w-0 items-center gap-3 rounded-xl p-2.5 text-left transition-colors ${active ? "bg-white text-zinc-950" : "text-zinc-500 hover:bg-white/5 hover:text-white"}`}><span className={`grid size-8 shrink-0 place-items-center rounded-lg ${active ? "bg-zinc-950 text-white" : complete ? "bg-emerald-500/15 text-emerald-400" : "bg-white/5"}`}>{complete ? <Check className="size-4" /> : <Icon className="size-4" />}</span><span className="hidden text-xs font-medium lg:block">{item.label}</span></button>;
            })}
          </nav>
          <p className="mt-10 hidden text-[11px] leading-5 text-zinc-500 lg:block">You can change every analysis preference later. Human approval and people anonymization remain protected.</p>
        </aside>

        <section className="flex min-h-[720px] flex-col">
          <header className="flex h-20 items-center justify-between border-b border-zinc-100 px-6 sm:px-10"><div><span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-400">Step {step + 1} of {steps.length}</span><p className="mt-0.5 text-sm font-semibold">{steps[step].label}</p></div><Button variant="ghost" className="text-zinc-500" onClick={() => router.push("/")}>Exit setup</Button></header>

          <div className="flex-1 px-6 py-10 sm:px-10 lg:px-16 lg:py-14">
            <motion.div key={step} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mx-auto max-w-[820px]">
              {step === 0 ? (
                <>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-600">Organization identity</p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-5xl">Start with the company we are modeling.</h2>
                  <p className="mt-4 max-w-xl text-sm leading-6 text-zinc-500">These details establish the baseline used by department agents, sector defaults, and every decision package.</p>
                  <div className="mt-10 grid gap-5 sm:grid-cols-2">
                    <label><span className={fieldLabel}>Display name</span><Input className={fieldClass} value={organization.display_name} onChange={(event) => setOrganization({ ...organization, display_name: event.target.value })} /></label>
                    <label><span className={fieldLabel}>Legal name</span><Input className={fieldClass} value={organization.legal_name} onChange={(event) => setOrganization({ ...organization, legal_name: event.target.value })} /></label>
                    <label><span className={fieldLabel}>Primary sector</span><select className={`${fieldClass} w-full px-3`} value={organization.sector} onChange={(event) => setOrganization({ ...organization, sector: event.target.value as typeof organization.sector })}><option value="technology_saas">Technology & SaaS</option><option value="financial_services">Financial services</option><option value="healthcare">Healthcare</option><option value="professional_services">Professional services</option><option value="retail_consumer">Retail & consumer</option><option value="manufacturing">Manufacturing</option><option value="other">Other</option></select></label>
                    <label><span className={fieldLabel}>Business model</span><select className={`${fieldClass} w-full px-3`} value={organization.business_model} onChange={(event) => setOrganization({ ...organization, business_model: event.target.value as typeof organization.business_model })}><option value="b2b">B2B</option><option value="b2c">B2C</option><option value="b2b2c">B2B2C</option><option value="marketplace">Marketplace</option><option value="mixed">Mixed</option></select></label>
                    <label><span className={fieldLabel}>Headquarters</span><Input className={fieldClass} value={organization.headquarters_country} onChange={(event) => setOrganization({ ...organization, headquarters_country: event.target.value.toUpperCase().slice(0, 2) })} /></label>
                    <label><span className={fieldLabel}>Company size</span><select className={`${fieldClass} w-full px-3`} value={organization.size_band} onChange={(event) => setOrganization({ ...organization, size_band: event.target.value as typeof organization.size_band })}><option value="startup">Startup · under 50</option><option value="smb">SMB · 50–249</option><option value="mid_market">Mid-market · 250–999</option><option value="enterprise">Enterprise · 1,000–9,999</option><option value="large_enterprise">Large enterprise · 10,000+</option></select></label>
                    <label className="sm:col-span-2"><span className={fieldLabel}>Company context</span><textarea className="min-h-28 w-full resize-none rounded-xl border border-zinc-200 bg-white p-3 text-sm leading-6 outline-none transition-shadow focus:border-zinc-400 focus:ring-3 focus:ring-zinc-200" value={organization.description} onChange={(event) => setOrganization({ ...organization, description: event.target.value })} /></label>
                  </div>
                </>
              ) : null}

              {step === 1 ? (
                <>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-blue-600">Department map</p>
                  <div className="mt-3 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-3xl font-semibold tracking-[-0.045em] sm:text-5xl">Who should be in the room?</h2><p className="mt-4 max-w-xl text-sm leading-6 text-zinc-500">Choose the departments the organizational twin should represent. Staffing and budget establish scale, not performance.</p></div><div className="shrink-0 text-right text-xs text-zinc-500"><strong className="block text-xl text-zinc-950">{enabledDepartments.length}</strong>departments</div></div>
                  <div className="mt-8 grid gap-3 sm:grid-cols-2">
                    {departments.map((department) => <button key={department.department_id} type="button" onClick={() => setDepartments((items) => items.map((item) => item.department_id === department.department_id ? { ...item, enabled: !item.enabled } : item))} className={`flex items-center gap-4 rounded-2xl border p-4 text-left transition-all ${department.enabled ? "border-zinc-300 bg-white shadow-sm" : "border-zinc-200 bg-zinc-50 opacity-55"}`}><span className={`grid size-10 shrink-0 place-items-center rounded-xl ${department.enabled ? "bg-zinc-950 text-white" : "bg-zinc-200 text-zinc-500"}`}><Users className="size-4" /></span><span className="min-w-0 flex-1"><strong className="block text-sm">{department.name}</strong><span className="mt-1 block truncate text-[10px] text-zinc-500">{department.actual_fte} FTE · {formatCompactCurrency(department.annual_budget_usd)}</span></span><span className={`grid size-5 place-items-center rounded-full border ${department.enabled ? "border-emerald-500 bg-emerald-500 text-white" : "border-zinc-300"}`}>{department.enabled ? <Check className="size-3" /> : null}</span></button>)}
                  </div>
                  <div className="mt-6 grid gap-3 rounded-2xl bg-zinc-950 p-5 text-white sm:grid-cols-2"><div><span className="text-[10px] text-zinc-500">Modeled headcount</span><strong className="mt-1 block text-2xl">{totals.headcount} FTE</strong></div><div><span className="text-[10px] text-zinc-500">Modeled annual budget</span><strong className="mt-1 block text-2xl">{formatCompactCurrency(totals.budget)}</strong></div></div>
                </>
              ) : null}

              {step === 2 ? (
                <>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-600">Strategic priorities</p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-5xl">What should every decision protect?</h2>
                  <p className="mt-4 max-w-xl text-sm leading-6 text-zinc-500">Agents use this ranked list to explain trade-offs. It does not override hard constraints or human approval.</p>
                  <div className="mt-9 space-y-3">{organization.strategic_priorities.map((priority, index) => <div key={priority.id} className="grid grid-cols-[42px_1fr] items-center gap-3 rounded-2xl border border-zinc-200 p-3"><span className="grid size-10 place-items-center rounded-xl bg-violet-50 text-sm font-semibold text-violet-700">{index + 1}</span><Input className={`${fieldClass} border-0 bg-transparent px-1 focus-visible:ring-0`} value={priority.text} onChange={(event) => setOrganization({ ...organization, strategic_priorities: organization.strategic_priorities.map((item) => item.id === priority.id ? { ...item, text: event.target.value } : item) })} /></div>)}</div>
                  <div className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-5"><div className="flex gap-3"><Sparkles className="mt-0.5 size-4 shrink-0 text-amber-700" /><div><strong className="text-sm">Why ranking matters</strong><p className="mt-1 text-xs leading-5 text-amber-900/70">When two plans have similar financial outcomes, Canary Pact uses these priorities to explain which trade-off better matches company strategy.</p></div></div></div>
                </>
              ) : null}

              {step === 3 ? (
                <>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-rose-600">Analysis defaults</p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-5xl">Set the lens, not the answer.</h2>
                  <p className="mt-4 max-w-xl text-sm leading-6 text-zinc-500">These settings control how scenarios are explored. Every result records the settings version that produced it.</p>
                  <div className="mt-9 grid gap-5 sm:grid-cols-2">
                    <div className="rounded-2xl border border-zinc-200 p-5 sm:col-span-2"><span className={fieldLabel}>Risk appetite</span><div className="grid gap-2 sm:grid-cols-3">{(["conservative", "balanced", "aggressive"] as const).map((option) => <button key={option} type="button" onClick={() => setRiskAppetite(option)} className={`rounded-xl border px-4 py-3 text-left capitalize transition-all ${riskAppetite === option ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-200 bg-white text-zinc-600"}`}><strong className="text-sm">{option}</strong><span className={`mt-1 block text-[10px] ${riskAppetite === option ? "text-zinc-400" : "text-zinc-500"}`}>{option === "conservative" ? "Surface risk earlier" : option === "balanced" ? "Balance value and exposure" : "Favor upside potential"}</span></button>)}</div></div>
                    <label><span className={fieldLabel}>Default simulation horizon</span><select className={`${fieldClass} w-full px-3`} value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>365 days</option></select></label>
                    <div><span className={fieldLabel}>Default futures</span><div className={`${fieldClass} flex items-center gap-2 px-3 text-xs text-zinc-600`}><Check className="size-3.5 text-emerald-600" />Act now · Inaction · Delay</div></div>
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 sm:col-span-2"><div className="flex gap-3"><ShieldCheck className="size-4 shrink-0 text-emerald-700" /><div><strong className="text-xs">Protected controls</strong><p className="mt-1 text-[11px] leading-5 text-emerald-900/70">Human approval and anonymized people data stay enabled. They cannot be switched off in this environment.</p></div></div></div>
                  </div>
                </>
              ) : null}
            </motion.div>
          </div>

          <footer className="flex items-center justify-between border-t border-zinc-100 px-6 py-5 sm:px-10"><Button variant="ghost" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}><ArrowLeft />Back</Button><div className="hidden items-center gap-2 text-[10px] text-zinc-400 sm:flex"><CircleDollarSign className="size-3.5" />Money remains stored in USD</div><Button onClick={next} className="bg-zinc-950 text-white hover:bg-zinc-800">{step === steps.length - 1 ? "Finish setup" : "Continue"}<ArrowRight /></Button></footer>
        </section>
      </div>
    </main>
  );
}
