"use client";

import type { OrganizationProfile } from "@canary-pact/contracts";
import { ArrowLeft, Building2, Check, ChevronRight, CircleGauge, Clock3, FileText, Network, Save, Settings2, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const tabs = [
  { id: "general", label: "General", icon: Building2 },
  { id: "departments", label: "Departments", icon: Users },
  { id: "simulation", label: "Simulation", icon: Clock3 },
  { id: "risk", label: "Risk & guardrails", icon: ShieldCheck },
] as const;

type TabId = (typeof tabs)[number]["id"];
const labelClass = "mb-2 block text-[11px] font-semibold text-zinc-600";
const fieldClass = "h-11 rounded-xl border-zinc-200 bg-white text-sm shadow-none focus-visible:border-zinc-400 focus-visible:ring-zinc-200";

export function OrganizationSettings({ profile }: { profile: OrganizationProfile }) {
  const [activeTab, setActiveTab] = useState<TabId>("general");
  const [organization, setOrganization] = useState(profile.organization);
  const [departments, setDepartments] = useState(profile.departments);
  const [settings, setSettings] = useState(profile.settings);
  const [saved, setSaved] = useState(false);
  const riskTotal = useMemo(() => Object.values(settings.risk_weights).reduce((sum, weight) => sum + weight, 0), [settings.risk_weights]);
  const activeLabel = tabs.find((tab) => tab.id === activeTab)?.label;

  const save = () => {
    if (riskTotal !== 100) return;
    setSettings((current) => ({ ...current, settings_version: current.settings_version + 1, updated_at: new Date().toISOString() }));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2400);
  };

  return (
    <main className="min-h-screen bg-white p-3 text-zinc-950 sm:p-5">
      <div className="mx-auto min-h-[calc(100vh-24px)] max-w-[1500px] overflow-hidden rounded-[28px] border border-zinc-200 bg-white sm:min-h-[calc(100vh-40px)]">
        <header className="flex h-20 items-center justify-between border-b border-zinc-200 px-5 sm:px-8">
          <div className="flex items-center gap-4"><Link href="/" className="grid size-9 place-items-center rounded-xl bg-zinc-950 text-white" aria-label="Canary Pact home"><Network className="size-4" /></Link><div><div className="flex items-center gap-2"><strong className="text-sm">{organization.display_name}</strong><Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-[9px] text-zinc-500">Mock organization</Badge></div><span className="text-[10px] text-zinc-400">Organization settings · v{settings.settings_version}</span></div></div>
          <div className="flex items-center gap-2"><Button asChild variant="ghost" className="hidden text-zinc-500 sm:inline-flex"><Link href="/simulate"><ArrowLeft />Back to simulator</Link></Button><Button onClick={save} disabled={riskTotal !== 100} className="bg-zinc-950 text-white hover:bg-zinc-800">{saved ? <Check /> : <Save />}{saved ? "Saved" : "Save changes"}</Button></div>
        </header>

        <div className="grid lg:grid-cols-[260px_1fr]">
          <aside className="border-b border-zinc-200 p-4 lg:min-h-[calc(100vh-120px)] lg:border-b-0 lg:border-r lg:p-6">
            <p className="px-3 text-[9px] font-semibold uppercase tracking-[0.18em] text-zinc-400">Organization</p>
            <nav className="mt-3 grid grid-cols-2 gap-1 sm:grid-cols-4 lg:grid-cols-1" aria-label="Organization settings">
              {tabs.map((tab) => { const Icon = tab.icon; return <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs font-medium transition-colors ${activeTab === tab.id ? "bg-zinc-950 text-white" : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950"}`}><Icon className="size-4" />{tab.label}</button>; })}
            </nav>
            <div className="mt-8 hidden rounded-2xl border border-zinc-200 bg-zinc-50 p-4 lg:block"><div className="flex items-center justify-between"><span className="text-[10px] font-semibold">Twin readiness</span><span className="text-[10px] font-semibold text-emerald-600">82%</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-200"><div className="h-full w-[82%] rounded-full bg-emerald-500" /></div><p className="mt-3 text-[10px] leading-4 text-zinc-500">Identity, departments, and analysis defaults are ready. Evidence coverage is still being modeled.</p></div>
            <Button asChild variant="outline" className="mt-3 hidden w-full border-zinc-200 bg-white text-xs lg:inline-flex"><Link href="/onboarding">Run setup again <ChevronRight /></Link></Button>
          </aside>

          <section className="px-6 py-9 sm:px-10 lg:px-14 lg:py-12">
            <div className="mx-auto max-w-[960px]">
              <div className="border-b border-zinc-200 pb-7"><p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-zinc-400">Settings</p><h1 className="mt-2 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">{activeLabel}</h1><p className="mt-2 text-sm text-zinc-500">Changes create a new settings version. Existing simulation runs keep the version they started with.</p></div>

              {activeTab === "general" ? <div className="pt-8">
                <SettingsSection title="Organization identity" description="Shared context used in every simulation and decision package.">
                  <div className="grid gap-5 sm:grid-cols-2"><label><span className={labelClass}>Display name</span><Input className={fieldClass} value={organization.display_name} onChange={(event) => setOrganization({ ...organization, display_name: event.target.value })} /></label><label><span className={labelClass}>Legal name</span><Input className={fieldClass} value={organization.legal_name} onChange={(event) => setOrganization({ ...organization, legal_name: event.target.value })} /></label><label><span className={labelClass}>Sector</span><select className={`${fieldClass} w-full px-3`} value={organization.sector} onChange={(event) => setOrganization({ ...organization, sector: event.target.value as typeof organization.sector })}><option value="technology_saas">Technology & SaaS</option><option value="financial_services">Financial services</option><option value="healthcare">Healthcare</option><option value="professional_services">Professional services</option><option value="other">Other</option></select></label><label><span className={labelClass}>Sub-sector</span><Input className={fieldClass} value={organization.sub_sector ?? ""} onChange={(event) => setOrganization({ ...organization, sub_sector: event.target.value })} /></label><label><span className={labelClass}>Headquarters</span><Input className={fieldClass} value={organization.headquarters_country} onChange={(event) => setOrganization({ ...organization, headquarters_country: event.target.value.toUpperCase().slice(0, 2) })} /></label><label><span className={labelClass}>Operating regions</span><Input className={fieldClass} value={organization.operating_regions.join(", ")} onChange={(event) => setOrganization({ ...organization, operating_regions: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} /></label></div>
                </SettingsSection>
                <SettingsSection title="Display preferences" description="Formatting only. Monetary values remain stored as whole US dollars.">
                  <div className="grid gap-5 sm:grid-cols-3"><label><span className={labelClass}>Currency</span><select className={`${fieldClass} w-full px-3`} value={settings.display_currency} onChange={(event) => setSettings({ ...settings, display_currency: event.target.value })}><option>USD</option><option>EUR</option><option>GBP</option></select></label><label><span className={labelClass}>Money scale</span><select className={`${fieldClass} w-full px-3`} value={settings.money_display_scale} onChange={(event) => setSettings({ ...settings, money_display_scale: event.target.value as typeof settings.money_display_scale })}><option value="auto">Automatic</option><option value="K">Thousands</option><option value="M">Millions</option><option value="B">Billions</option></select></label><label><span className={labelClass}>Timezone</span><select className={`${fieldClass} w-full px-3`} value={settings.timezone} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })}><option>America/New_York</option><option>America/Los_Angeles</option><option>Europe/London</option><option>UTC</option></select></label></div>
                </SettingsSection>
              </div> : null}

              {activeTab === "departments" ? <div className="pt-8"><SettingsSection title="Department profiles" description="Staffing and budget describe operating scale. They are not employee performance measures."><div className="overflow-hidden rounded-2xl border border-zinc-200"><div className="hidden grid-cols-[1.3fr_.7fr_.8fr_.6fr] gap-3 bg-zinc-50 px-4 py-3 text-[9px] font-semibold uppercase tracking-wider text-zinc-400 sm:grid"><span>Department</span><span>Headcount</span><span>Budget</span><span>Utilization</span></div>{departments.map((department) => <div key={department.department_id} className="grid gap-3 border-t border-zinc-100 p-4 first:border-t-0 sm:grid-cols-[1.3fr_.7fr_.8fr_.6fr] sm:items-center"><div><strong className="text-sm">{department.name}</strong><p className="mt-1 line-clamp-1 text-[10px] text-zinc-500">{department.mission}</p></div><label><span className="mb-1 block text-[9px] text-zinc-400 sm:hidden">Headcount</span><Input className="h-9 border-zinc-200" type="number" min={0} value={department.actual_fte} onChange={(event) => setDepartments((items) => items.map((item) => item.department_id === department.department_id ? { ...item, actual_fte: Number(event.target.value) } : item))} /></label><label><span className="mb-1 block text-[9px] text-zinc-400 sm:hidden">Budget USD</span><Input className="h-9 border-zinc-200" type="number" min={0} step={100000} value={department.annual_budget_usd} onChange={(event) => setDepartments((items) => items.map((item) => item.department_id === department.department_id ? { ...item, annual_budget_usd: Number(event.target.value) } : item))} /></label><span className={`w-fit rounded-full px-2 py-1 text-[10px] font-semibold ${department.utilisation > 1 ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>{Math.round(department.utilisation * 100)}%</span></div>)}</div></SettingsSection></div> : null}

              {activeTab === "simulation" ? <div className="pt-8"><SettingsSection title="Scenario defaults" description="Pre-filled on every new decision brief and editable per simulation."><div className="grid gap-5 sm:grid-cols-2"><label><span className={labelClass}>Default horizon</span><select className={`${fieldClass} w-full px-3`} value={settings.default_horizon_days} onChange={(event) => setSettings({ ...settings, default_horizon_days: Number(event.target.value) })}><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>365 days</option></select></label><label><span className={labelClass}>Default delay</span><select className={`${fieldClass} w-full px-3`} value={settings.default_delay_days} onChange={(event) => setSettings({ ...settings, default_delay_days: Number(event.target.value) })}><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option></select></label><label><span className={labelClass}>Propagation depth</span><Input className={fieldClass} type="number" min={1} max={6} value={settings.propagation_max_hops} onChange={(event) => setSettings({ ...settings, propagation_max_hops: Number(event.target.value) })} /></label><label><span className={labelClass}>Minimum impact threshold</span><Input className={fieldClass} type="number" min={0} max={1} step={0.01} value={settings.min_impact_threshold} onChange={(event) => setSettings({ ...settings, min_impact_threshold: Number(event.target.value) })} /></label></div></SettingsSection><SettingsSection title="Analysis mode" description="Replay is the deterministic, presentation-safe default."><div className="grid gap-3 sm:grid-cols-3">{(["replay", "mock", "live"] as const).map((mode) => <button key={mode} type="button" onClick={() => setSettings({ ...settings, llm_mode: mode })} className={`rounded-2xl border p-4 text-left transition-all ${settings.llm_mode === mode ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-200"}`}><strong className="text-sm capitalize">{mode}</strong><p className={`mt-1 text-[10px] leading-4 ${settings.llm_mode === mode ? "text-zinc-400" : "text-zinc-500"}`}>{mode === "replay" ? "Saved, reproducible assessments" : mode === "mock" ? "Structured placeholder outputs" : "Current agent models"}</p></button>)}</div></SettingsSection></div> : null}

              {activeTab === "risk" ? <div className="pt-8"><SettingsSection title="Risk appetite" description="Adjusts thresholds and tie-breaking; it never bypasses hard constraints."><div className="grid gap-3 sm:grid-cols-3">{(["conservative", "balanced", "aggressive"] as const).map((appetite) => <button key={appetite} type="button" onClick={() => setSettings({ ...settings, risk_appetite: appetite })} className={`rounded-2xl border p-4 text-left transition-all ${settings.risk_appetite === appetite ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-200"}`}><strong className="text-sm capitalize">{appetite}</strong><p className={`mt-1 text-[10px] ${settings.risk_appetite === appetite ? "text-zinc-400" : "text-zinc-500"}`}>{appetite === "conservative" ? "Flag exposure earlier" : appetite === "balanced" ? "Balance value and risk" : "Favor upside potential"}</p></button>)}</div></SettingsSection><SettingsSection title="Risk weights" description="Weights must total 100%. Deterministic scoring uses these values."><div className="space-y-4">{Object.entries(settings.risk_weights).map(([key, value]) => <label key={key} className="grid grid-cols-[1fr_70px] items-center gap-4"><span className="text-xs capitalize text-zinc-600">{key.replaceAll("_", " ")}</span><Input className="h-9 border-zinc-200 text-right" type="number" min={0} max={100} value={value} onChange={(event) => setSettings({ ...settings, risk_weights: { ...settings.risk_weights, [key]: Number(event.target.value) } })} /></label>)}<div className={`flex items-center justify-between rounded-xl p-3 text-xs font-semibold ${riskTotal === 100 ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}><span>Total</span><span>{riskTotal}%</span></div></div></SettingsSection><SettingsSection title="Protected controls" description="These safeguards are locked in the demonstration environment."><div className="space-y-3"><LockedControl icon={ShieldCheck} title="Human approval required" detail="Every real organizational decision ends at a human approval gate." /><LockedControl icon={Users} title="People remain anonymized" detail="The twin uses role and person tokens, never employee rankings." /><LockedControl icon={FileText} title="Evidence remains traceable" detail="Reported impacts retain evidence, confidence, and dependency paths." /></div></SettingsSection></div> : null}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

function SettingsSection({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="grid gap-6 border-b border-zinc-100 py-8 last:border-b-0 lg:grid-cols-[240px_1fr]"><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-2 text-[11px] leading-5 text-zinc-500">{description}</p></div><div>{children}</div></section>;
}

function LockedControl({ icon: Icon, title, detail }: { icon: typeof CircleGauge; title: string; detail: string }) {
  return <div className="flex items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-4"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-600 shadow-sm"><Icon className="size-4" /></span><div className="min-w-0 flex-1"><strong className="text-xs">{title}</strong><p className="mt-0.5 text-[10px] leading-4 text-zinc-500">{detail}</p></div><Badge variant="outline" className="border-zinc-200 bg-white text-[9px] text-zinc-500">Locked on</Badge></div>;
}
