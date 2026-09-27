"use client";

import type { OrganizationProfile } from "@canary-pact/contracts";
import type { AgentSkillFile, Criticality, DepartmentContextItemCreate, DepartmentDetail, EvidenceSource } from "@canary-pact/contracts/generated";
import { ArrowLeft, BookOpenText, Building2, Check, ChevronDown, ChevronRight, CircleGauge, Clock3, FileText, LoaderCircle, Network, Plus, Save, Settings2, ShieldCheck, Users, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useSimulationOutcome } from "@/components/simulation-outcome-provider";
import { DepartmentChange } from "@/components/department-change";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { canaryApi } from "@/lib/canary-api-client";
import { formatCompactCurrency, formatWholeNumber } from "@/lib/formatters";

const tabs = [
  { id: "general", label: "General", icon: Building2 },
  { id: "departments", label: "Departments", icon: Users },
  { id: "simulation", label: "Simulation", icon: Clock3 },
  { id: "risk", label: "Risk & guardrails", icon: ShieldCheck },
] as const;

type TabId = (typeof tabs)[number]["id"];
const labelClass = "mb-2 block text-[11px] font-semibold text-zinc-600";
const fieldClass = "h-11 rounded-xl border-zinc-200 bg-white text-sm shadow-none focus-visible:border-zinc-400 focus-visible:ring-zinc-200";
const contextTypes: DepartmentContextItemCreate["entity_type"][] = ["workflow", "system", "project", "kpi", "role", "knowledge_asset"];
const evidenceSources: EvidenceSource[] = ["runbook", "workflow_map", "system_ownership", "kpi_definition", "architecture_note", "activity_log", "knowledge_matrix", "contract", "policy", "incident", "finance_forecast"];
const emptyContextDraft: DepartmentContextItemCreate = { entity_type: "workflow", name: "", criticality: "medium", evidence_title: "", evidence_source: "runbook", evidence_snippet: "" };

import { saveOrganizationProfile } from "@/lib/organization-profile";

export function OrganizationSettings({ profile, agentSkills }: { profile: OrganizationProfile; agentSkills: AgentSkillFile[] }) {
  const { user } = useAuth();
  const { outcome: currentOutcome, setOutcome } = useSimulationOutcome();
  const [addingDepartment, setAddingDepartment] = useState(false);
  const [departmentAdded, setDepartmentAdded] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("general");
  const [organization, setOrganization] = useState(profile.organization);
  const [departments, setDepartments] = useState(profile.departments);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState(profile.departments[0]?.department_id ?? "");
  const [departmentDetails, setDepartmentDetails] = useState<Record<string, DepartmentDetail>>({});
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [addingContext, setAddingContext] = useState(false);
  const [contextDraft, setContextDraft] = useState<DepartmentContextItemCreate>(emptyContextDraft);
  const [contextSaving, setContextSaving] = useState(false);
  const [contextError, setContextError] = useState<string | null>(null);
  const [settings, setSettings] = useState(profile.settings);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [twinVersion, setTwinVersion] = useState(profile.twin_version);
  const outcome = currentOutcome?.organizationId === profile.organization.id
    && (!currentOutcome.preview || currentOutcome.twinVersion === twinVersion) ? currentOutcome : null;
  const riskTotal = useMemo(() => Object.values(settings.risk_weights).reduce((sum, weight) => sum + weight, 0), [settings.risk_weights]);
  const activeLabel = tabs.find((tab) => tab.id === activeTab)?.label;
  const selectedDepartment = departments.find((department) => department.department_id === selectedDepartmentId) ?? departments[0];
  const selectedDepartmentSkill = selectedDepartment ? agentSkills.find((skill) => skill.department_id === selectedDepartment.department_id) : undefined;
  const selectedDepartmentDetail = selectedDepartment ? departmentDetails[selectedDepartment.department_id] : undefined;
  const ownedEntities = selectedDepartmentDetail?.owned_entities ?? [];
  const departmentDocuments = selectedDepartmentDetail?.documents ?? [];
  const departmentConnections = (selectedDepartmentDetail?.channels_in?.length ?? 0) + (selectedDepartmentDetail?.channels_out?.length ?? 0);
  const organizationWideSkills = agentSkills.filter((skill) => skill.department_id === null);
  const departmentTotals = useMemo(() => ({
    headcount: departments.reduce((sum, department) => sum + department.actual_fte, 0),
    budget: departments.reduce((sum, department) => sum + department.annual_budget_usd, 0),
    pressured: departments.filter((department) => department.utilisation > 1).length,
  }), [departments]);

  useEffect(() => {
    if (!selectedDepartment || departmentDetails[selectedDepartment.department_id]) return;
    let cancelled = false;
    setDetailLoadingId(selectedDepartment.department_id);
    setDetailError(null);
    void canaryApi.department(selectedDepartment.department_id)
      .then((detail) => { if (!cancelled) setDepartmentDetails((current) => ({ ...current, [selectedDepartment.department_id]: detail })); })
      .catch((error: unknown) => { if (!cancelled) setDetailError(error instanceof Error ? error.message : "Could not load department context."); })
      .finally(() => { if (!cancelled) setDetailLoadingId(null); });
    return () => { cancelled = true; };
  }, [departmentDetails, selectedDepartment]);

  const save = async () => {
    if (riskTotal !== 100) return;
    setSaving(true);setSaveError(null);
    try {
      const result = await saveOrganizationProfile({...profile,twin_version:twinVersion,organization,departments,settings});
      setTwinVersion(result.twin_version);setDepartments(result.departments);setSettings(result.settings);setSaved(true);
      window.setTimeout(()=>setSaved(false),2400);
    } catch(error) {setSaveError(error instanceof Error ? error.message : "Could not save settings");}
    finally {setSaving(false);}
  };

  const addContext = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedDepartment) return;
    setContextSaving(true);
    setContextError(null);
    try {
      const detail = await canaryApi.addDepartmentContext(selectedDepartment.department_id, contextDraft);
      setDepartmentDetails((current) => ({ ...current, [selectedDepartment.department_id]: detail }));
      const updatedProfile = await canaryApi.organizationProfile();
      setTwinVersion(updatedProfile.twin_version ?? undefined);
      setContextDraft(emptyContextDraft);
      setAddingContext(false);
    } catch (error) {
      setContextError(error instanceof Error ? error.message : "Could not save department context.");
    } finally {
      setContextSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-white p-3 text-zinc-950 sm:p-5">
      <div className="mx-auto min-h-[calc(100vh-24px)] max-w-[1500px] overflow-hidden rounded-[28px] border border-zinc-200 bg-white sm:min-h-[calc(100vh-40px)]">
        {saveError ? <p role="alert" className="rounded-xl bg-red-50 p-3 text-xs text-red-700">{saveError}</p> : null}
      <header className="flex h-20 items-center justify-between border-b border-zinc-200 px-5 sm:px-8">
          <div className="flex items-center gap-4"><Link href="/" className="grid size-9 place-items-center rounded-xl bg-zinc-950 text-white" aria-label="Canary Pact home"><Network className="size-4" /></Link><div><div className="flex items-center gap-2"><strong className="text-sm">{organization.display_name}</strong><Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-[9px] text-zinc-500">API connected</Badge></div><span className="text-[10px] text-zinc-400">Organization settings · v{settings.settings_version}</span></div></div>
          <div className="flex items-center gap-2"><Button asChild variant="ghost" className="hidden text-zinc-500 sm:inline-flex"><Link href="/simulate"><ArrowLeft />Back to simulator</Link></Button><Button onClick={save} disabled={saving || riskTotal !== 100} className="bg-zinc-950 text-white hover:bg-zinc-800">{saved ? <Check /> : <Save />}{saving ? "Saving…" : saved ? "Saved" : "Save changes"}</Button></div>
        </header>

        <div className="grid lg:grid-cols-[260px_1fr]">
          <aside className="border-b border-zinc-200 p-4 lg:min-h-[calc(100vh-120px)] lg:border-b-0 lg:border-r lg:p-6">
            <p className="px-3 text-[9px] font-semibold uppercase tracking-[0.18em] text-zinc-400">Organization</p>
            <nav className="mt-3 grid grid-cols-2 gap-1 sm:grid-cols-4 lg:grid-cols-1" aria-label="Organization settings">
              {tabs.map((tab) => { const Icon = tab.icon; return <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs font-medium transition-colors ${activeTab === tab.id ? "bg-zinc-950 text-white" : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950"}`}><Icon className="size-4" />{tab.label}</button>; })}
            </nav>
            <Button asChild variant="outline" className="mt-3 hidden w-full border-zinc-200 bg-white text-xs lg:inline-flex"><Link href="/onboarding">Run setup again <ChevronRight /></Link></Button>
          </aside>

          <section className="min-w-0 px-6 py-9 sm:px-10 lg:px-14 lg:py-12">
            <div className="mx-auto w-full min-w-0 max-w-[960px]">
              <div className="border-b border-zinc-200 pb-7"><p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-zinc-400">Settings</p><h1 className="mt-2 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">{activeLabel}</h1><p className="mt-2 text-sm text-zinc-500">Changes create a new settings version. Existing simulation runs keep the version they started with.</p></div>

              {activeTab === "general" ? <div className="pt-8">
                <SettingsSection title="Organization identity" description="Shared context used in every simulation and decision package.">
                  <div className="grid gap-5 sm:grid-cols-2"><label><span className={labelClass}>Display name</span><Input className={fieldClass} value={organization.display_name} onChange={(event) => setOrganization({ ...organization, display_name: event.target.value })} /></label><label><span className={labelClass}>Legal name</span><Input className={fieldClass} value={organization.legal_name} onChange={(event) => setOrganization({ ...organization, legal_name: event.target.value })} /></label><label><span className={labelClass}>Sector</span><select className={`${fieldClass} w-full px-3`} value={organization.sector} onChange={(event) => setOrganization({ ...organization, sector: event.target.value as typeof organization.sector })}><option value="technology_saas">Technology & SaaS</option><option value="financial_services">Financial services</option><option value="healthcare">Healthcare</option><option value="professional_services">Professional services</option><option value="other">Other</option></select></label><label><span className={labelClass}>Sub-sector</span><Input className={fieldClass} value={organization.sub_sector ?? ""} onChange={(event) => setOrganization({ ...organization, sub_sector: event.target.value })} /></label><label><span className={labelClass}>Headquarters</span><Input className={fieldClass} value={organization.headquarters_country} onChange={(event) => setOrganization({ ...organization, headquarters_country: event.target.value.toUpperCase().slice(0, 2) })} /></label><label><span className={labelClass}>Operating regions</span><Input className={fieldClass} value={organization.operating_regions.join(", ")} onChange={(event) => setOrganization({ ...organization, operating_regions: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} /></label></div>
                </SettingsSection>
                <SettingsSection title="Display preferences" description="Formatting only. Monetary values remain stored as whole US dollars.">
                  <div className="grid gap-5 sm:grid-cols-3"><label><span className={labelClass}>Currency</span><select className={`${fieldClass} w-full px-3`} value={settings.display_currency} onChange={(event) => setSettings({ ...settings, display_currency: event.target.value })}><option>USD</option><option>EUR</option><option>GBP</option></select></label><label><span className={labelClass}>Money scale</span><select className={`${fieldClass} w-full px-3`} value={settings.money_display_scale} onChange={(event) => setSettings({ ...settings, money_display_scale: event.target.value as typeof settings.money_display_scale })}><option value="auto">Automatic</option><option value="K">Thousands</option><option value="M">Millions</option><option value="B">Billions</option></select></label><label><span className={labelClass}>Timezone</span><select className={`${fieldClass} w-full px-3`} value={settings.timezone} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })}><option>America/New_York</option><option>America/Los_Angeles</option><option>Europe/London</option><option>UTC</option></select></label></div>
                </SettingsSection>
              </div> : null}

              {activeTab === "departments" ? (
                <div className="pt-8">
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-zinc-500">Manage the departments in your company baseline.</p>
                    <Button disabled={saving || contextSaving} onClick={() => { setDepartmentAdded(null); setAddingDepartment(true); }} className="bg-zinc-950 text-white hover:bg-zinc-800"><Plus />Add department</Button>
                  </div>
                  {departmentAdded ? <p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-800">{departmentAdded} added to the company baseline.</p> : null}
                  <div className="grid grid-cols-3 gap-2 sm:gap-3">
                    <DepartmentSummaryCard label="Departments" value={String(departments.length)} detail={`${agentSkills.length} agent files`} />
                    <DepartmentSummaryCard label="Total operating scale" value={String(departmentTotals.headcount)} detail={`${formatCompactCurrency(departmentTotals.budget)} annual budget`} />
                    <DepartmentSummaryCard label="Capacity pressure" value={String(departmentTotals.pressured)} detail={departmentTotals.pressured === 1 ? "department above 100%" : "departments above 100%"} alert={departmentTotals.pressured > 0} />
                  </div>

                  {selectedDepartment ? <div className="mt-5 grid min-w-0 max-w-full overflow-hidden rounded-3xl border border-zinc-200 bg-white lg:grid-cols-[250px_minmax(0,1fr)]">
                    <div className="min-w-0 border-b border-zinc-200 bg-zinc-50/70 p-3 lg:border-b-0 lg:border-r">
                      <div className="flex items-center justify-between px-2 pb-3"><div><h2 className="text-xs font-semibold">Department profiles</h2><p className="mt-1 text-[9px] text-zinc-500">Select one to inspect and edit</p></div><Badge variant="outline" className="border-zinc-200 bg-white text-[9px] text-zinc-500">{departments.length}</Badge></div>
                      <div className="grid w-full min-w-0 grid-flow-col auto-cols-[minmax(180px,1fr)] gap-1.5 overflow-x-auto pb-1 sm:max-h-[520px] sm:grid-flow-row sm:auto-cols-auto sm:grid-cols-2 sm:overflow-x-visible sm:overflow-y-auto sm:pb-0 lg:grid-cols-1" aria-label="Department profiles">
                        {departments.map((department) => {
                          const selected = department.department_id === selectedDepartment.department_id;
                          return <button key={department.department_id} type="button" aria-pressed={selected} onClick={() => setSelectedDepartmentId(department.department_id)} className={`group flex items-center gap-3 rounded-2xl border px-3 py-2.5 text-left transition-all ${selected ? "border-zinc-950 bg-zinc-950 text-white shadow-sm" : "border-transparent bg-white text-zinc-700 hover:border-zinc-200"}`}>
                            <span className={`grid size-8 shrink-0 place-items-center rounded-xl ${selected ? "bg-white/10 text-white" : "bg-zinc-100 text-zinc-500"}`}><Building2 className="size-3.5" /></span>
                            <span className="min-w-0 flex-1"><strong className="block truncate text-[11px]">{department.name}</strong><span className={`mt-0.5 block text-[9px] ${selected ? "text-zinc-400" : "text-zinc-400"}`}>{department.actual_fte} FTE · {formatCompactCurrency(department.annual_budget_usd)}</span></span>
                            <span className={`size-2 shrink-0 rounded-full ${department.utilisation > 1 ? "bg-rose-400" : "bg-emerald-400"}`} aria-label={`${Math.round(department.utilisation * 100)}% utilization`} />
                          </button>;
                        })}
                      </div>
                    </div>

                    <div className="min-w-0 p-5 sm:p-7">
                      <div className="flex flex-col gap-4 border-b border-zinc-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="text-2xl font-semibold tracking-[-.04em]">{selectedDepartment.name}</h2><Badge className={`border-0 text-[9px] ${selectedDepartment.utilisation > 1 ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>{Math.round(selectedDepartment.utilisation * 100)}% utilized</Badge></div><p className="mt-2 max-w-2xl text-[11px] leading-5 text-zinc-500">{selectedDepartment.mission}</p></div>
                        <Badge variant="outline" className="w-fit shrink-0 border-zinc-200 bg-zinc-50 text-[9px] text-zinc-500">{selectedDepartment.enabled ? "Active" : "Inactive"}</Badge>
                      </div>

                      <div className="grid gap-4 py-5 sm:grid-cols-2">
                        <label><span className={labelClass}>Headcount</span><Input className={fieldClass} type="number" min={0} value={selectedDepartment.actual_fte} onChange={(event) => setDepartments((items) => items.map((item) => item.department_id === selectedDepartment.department_id ? { ...item, actual_fte: Number(event.target.value) } : item))} /><span className="mt-1.5 block text-[9px] text-zinc-400">Operating scale, not a performance score</span></label>
                        <label><span className={labelClass}>Annual budget in USD</span><Input aria-label={`${selectedDepartment.name} budget in US dollars`} className={`${fieldClass} tabular-nums`} inputMode="numeric" value={formatWholeNumber(selectedDepartment.annual_budget_usd)} onChange={(event) => { const digits = event.target.value.replace(/\D/g, ""); setDepartments((items) => items.map((item) => item.department_id === selectedDepartment.department_id ? { ...item, annual_budget_usd: Number(digits || 0) } : item)); }} /><span className="mt-1.5 block text-[9px] font-medium text-zinc-500">≈ {formatCompactCurrency(selectedDepartment.annual_budget_usd)} annually</span></label>
                      </div>

                      <div className="mb-4 overflow-hidden rounded-2xl border border-zinc-200">
                        <div className="flex items-center justify-between gap-3 bg-zinc-50/60 p-4">
                          <div><h3 className="text-xs font-semibold">Company context</h3><p className="mt-1 text-[9px] text-zinc-500">Work, assets, and obligations this department can defend with evidence</p></div>
                          <Button type="button" size="sm" variant={addingContext ? "ghost" : "outline"} className="h-8 shrink-0 border-zinc-200 bg-white text-[10px]" onClick={() => { setAddingContext((value) => !value); setContextError(null); }}>{addingContext ? <X /> : <Plus />}{addingContext ? "Cancel" : "Add context"}</Button>
                        </div>

                        {detailLoadingId === selectedDepartment.department_id ? <div className="flex items-center gap-2 border-t border-zinc-200 px-4 py-5 text-[10px] text-zinc-500"><LoaderCircle className="size-4 animate-spin" />Loading saved department context…</div> : null}
                        {detailError ? <div className="border-t border-rose-100 bg-rose-50 px-4 py-4 text-[10px] text-rose-700">{detailError}</div> : null}
                        {!detailLoadingId && !detailError && selectedDepartmentDetail ? <div className="border-t border-zinc-200 px-4 py-3"><div className="flex flex-wrap gap-1.5">{ownedEntities.length ? ownedEntities.slice(0, 10).map((entity) => <span key={entity.id} className="rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-[9px] text-zinc-600"><span className="mr-1 text-zinc-400">{entity.type.replaceAll("_", " ")}</span>{entity.name}</span>) : <span className="text-[10px] text-zinc-500">No owned work or assets have been recorded yet.</span>}{ownedEntities.length > 10 ? <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[9px] text-zinc-500">+{ownedEntities.length - 10} more</span> : null}</div><p className="mt-2 text-[9px] text-zinc-400">{ownedEntities.length} owned items · {departmentDocuments.length} supporting documents · {departmentConnections} department connections</p></div> : null}

                        {addingContext ? <form onSubmit={addContext} className="border-t border-zinc-200 bg-white p-4">
                          <div className="grid gap-3 sm:grid-cols-2">
                            <label><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">What kind of context?</span><select className={`${fieldClass} w-full px-3 capitalize`} value={contextDraft.entity_type} onChange={(event) => setContextDraft({ ...emptyContextDraft, entity_type: event.target.value as DepartmentContextItemCreate["entity_type"] })}>{contextTypes.map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></label>
                            <label><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">Criticality</span><select className={`${fieldClass} w-full px-3 capitalize`} value={contextDraft.criticality ?? "medium"} onChange={(event) => setContextDraft((current) => ({ ...current, criticality: event.target.value as Criticality }))}>{(["low", "medium", "high", "critical"] as Criticality[]).map((value) => <option key={value}>{value}</option>)}</select></label>
                            <label className="sm:col-span-2"><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">Name</span><Input className={fieldClass} required minLength={2} maxLength={120} placeholder="For example: Monthly financial close" value={contextDraft.name} onChange={(event) => setContextDraft((current) => ({ ...current, name: event.target.value }))} /></label>
                            <ContextSpecificFields draft={contextDraft} onChange={setContextDraft} />
                            <label><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">Evidence source</span><select className={`${fieldClass} w-full px-3 capitalize`} value={contextDraft.evidence_source} onChange={(event) => setContextDraft((current) => ({ ...current, evidence_source: event.target.value as EvidenceSource }))}>{evidenceSources.map((source) => <option key={source} value={source}>{source.replaceAll("_", " ")}</option>)}</select></label>
                            <label><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">Evidence title</span><Input className={fieldClass} required minLength={2} maxLength={160} placeholder="Runbook, report, or record name" value={contextDraft.evidence_title} onChange={(event) => setContextDraft((current) => ({ ...current, evidence_title: event.target.value }))} /></label>
                            <label className="sm:col-span-2"><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">What does the evidence establish?</span><textarea className="min-h-24 w-full resize-y rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-xs leading-5 outline-none focus:border-zinc-400" required minLength={10} maxLength={300} placeholder="State the ownership, responsibility, or dependency supported by this source." value={contextDraft.evidence_snippet} onChange={(event) => setContextDraft((current) => ({ ...current, evidence_snippet: event.target.value }))} /><span className="mt-1 block text-right text-[8px] text-zinc-400">{contextDraft.evidence_snippet.length}/300</span></label>
                          </div>
                          {contextError ? <p className="mt-3 rounded-xl bg-rose-50 p-3 text-[10px] text-rose-700">{contextError}</p> : null}
                          <div className="mt-4 flex items-center justify-between gap-4"><p className="text-[9px] leading-4 text-zinc-400">Saving creates a new company-twin version and makes this evidence available to routed agents.</p><Button type="submit" disabled={contextSaving} className="shrink-0 bg-zinc-950 text-white hover:bg-zinc-800">{contextSaving ? <LoaderCircle className="animate-spin" /> : <Plus />}{contextSaving ? "Saving…" : "Add to department"}</Button></div>
                        </form> : null}
                      </div>

                      <div className="rounded-2xl border border-zinc-200 bg-zinc-50/60">
                        <div className="flex items-center justify-between gap-3 p-4"><div className="flex min-w-0 items-center gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-700"><BookOpenText className="size-4" /></span><div className="min-w-0"><h3 className="text-xs font-semibold">Department agent guidance</h3><p className="mt-1 truncate text-[9px] text-zinc-500">Uses this organization&apos;s saved profile, graph, documents, and evidence at runtime</p></div></div>{selectedDepartmentSkill ? <Badge className="shrink-0 border-0 bg-emerald-50 text-[9px] text-emerald-700">Ready</Badge> : <Badge className="shrink-0 border-0 bg-amber-50 text-[9px] text-amber-700">Unavailable</Badge>}</div>
                        {selectedDepartmentSkill ? <details className="group border-t border-zinc-200"><summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-[10px] font-semibold text-zinc-600 marker:hidden"><span>Review {selectedDepartmentSkill.display_name} guidance</span><ChevronDown className="size-4 text-zinc-400 transition-transform group-open:rotate-180" /></summary><div className="max-h-[340px] overflow-y-auto border-t border-zinc-200 bg-white px-5 py-5"><SkillContent content={selectedDepartmentSkill.content} /></div></details> : <div className="border-t border-zinc-200 px-4 py-4 text-[10px] leading-5 text-zinc-500">No department-specific agent file is mapped to this profile. The simulation will surface the missing perspective instead of inventing advice.</div>}
                      </div>
                    </div>
                  </div> : <div className="mt-5 rounded-3xl border border-dashed border-zinc-300 p-10 text-center"><Users className="mx-auto size-6 text-zinc-300" /><h2 className="mt-3 text-sm font-semibold">No departments configured</h2><p className="mx-auto mt-2 max-w-sm text-[11px] leading-5 text-zinc-500">Use Add department above to create your first department.</p></div>}

                  {organizationWideSkills.length ? <div className="mt-6 border-t border-zinc-100 pt-6"><div className="flex items-end justify-between gap-4"><div><h2 className="text-sm font-semibold">Organization-wide agents</h2><p className="mt-1 text-[10px] text-zinc-500">Cross-functional perspectives used when the decision requires them.</p></div><Badge variant="outline" className="border-zinc-200 bg-zinc-50 text-[9px] text-zinc-500">{organizationWideSkills.length}</Badge></div><div className="mt-3 grid gap-2 sm:grid-cols-2">{organizationWideSkills.map((skill) => <AgentSkillCard key={skill.agent_id} skill={skill} />)}</div></div> : null}
                </div>
              ) : null}

              {activeTab === "simulation" ? <div className="pt-8">
                <SettingsSection title="Show outcome" description="Choose which outcome appears in the simulator’s map and totals. This changes your view only; no organization save is needed.">
                  {outcome ? <div className="max-w-xl">
                    <p className="mb-4 text-xs font-medium text-zinc-700">{outcome.title}</p>
                    <label htmlFor="outcome-selector" className={labelClass}>Outcome to display</label>
                    <select id="outcome-selector" aria-describedby="outcome-description" className={`${fieldClass} w-full border px-3`} value={outcome.resultId} onChange={event => {
                      const resultId = event.target.value;
                      setOutcome(current => current ? { ...current, resultId } : null);
                    }}>
                      {outcome.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <p id="outcome-description" className="mt-3 text-xs leading-5 text-zinc-500">{outcome.options.find(option => option.value === outcome.resultId)?.description}</p>
                    <Button asChild variant="outline" className="mt-4"><Link href="/simulate">View in simulator <ChevronRight /></Link></Button>
                  </div> : <div className="rounded-2xl border border-dashed border-zinc-200 p-5">
                    <p className="text-sm font-medium">No simulation loaded</p>
                    <p className="mt-2 text-xs leading-5 text-zinc-500">Open the simulator to load your latest run or preview a decision, then return here to choose its outcome.</p>
                    <Button asChild variant="outline" className="mt-4"><Link href="/simulate">Open simulator <ChevronRight /></Link></Button>
                  </div>}
                </SettingsSection>
                <SettingsSection title="Scenario defaults" description="Pre-filled on every new decision brief and editable per simulation."><div className="grid gap-5 sm:grid-cols-2"><label><span className={labelClass}>Default horizon</span><select className={`${fieldClass} w-full px-3`} value={settings.default_horizon_days} onChange={(event) => setSettings({ ...settings, default_horizon_days: Number(event.target.value) })}><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>365 days</option></select></label><label><span className={labelClass}>Default delay</span><select className={`${fieldClass} w-full px-3`} value={settings.default_delay_days} onChange={(event) => setSettings({ ...settings, default_delay_days: Number(event.target.value) })}><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option></select></label><label><span className={labelClass}>Propagation depth</span><Input className={fieldClass} type="number" min={1} max={6} value={settings.propagation_max_hops} onChange={(event) => setSettings({ ...settings, propagation_max_hops: Number(event.target.value) })} /></label><label><span className={labelClass}>Minimum impact threshold</span><Input className={fieldClass} type="number" min={0} max={1} step={0.01} value={settings.min_impact_threshold} onChange={(event) => setSettings({ ...settings, min_impact_threshold: Number(event.target.value) })} /></label></div></SettingsSection><SettingsSection title="Department analysis" description="Suggestions always come from the currently configured live agent models."><div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><strong className="text-sm text-emerald-950">Live agents</strong><p className="mt-1 text-[10px] leading-4 text-emerald-800">Recorded and offline agent responses are disabled. Failed calls are surfaced as unavailable perspectives.</p></div></SettingsSection></div> : null}

              {activeTab === "risk" ? <div className="pt-8"><SettingsSection title="Risk appetite" description="Adjusts thresholds and tie-breaking; it never bypasses hard constraints."><div className="grid gap-3 sm:grid-cols-3">{(["conservative", "balanced", "aggressive"] as const).map((appetite) => <button key={appetite} type="button" onClick={() => setSettings({ ...settings, risk_appetite: appetite })} className={`rounded-2xl border p-4 text-left transition-all ${settings.risk_appetite === appetite ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-200"}`}><strong className="text-sm capitalize">{appetite}</strong><p className={`mt-1 text-[10px] ${settings.risk_appetite === appetite ? "text-zinc-400" : "text-zinc-500"}`}>{appetite === "conservative" ? "Flag exposure earlier" : appetite === "balanced" ? "Balance value and risk" : "Favor upside potential"}</p></button>)}</div></SettingsSection><SettingsSection title="Risk weights" description="Weights must total 100%. Deterministic scoring uses these values."><div className="space-y-4">{Object.entries(settings.risk_weights).map(([key, value]) => <label key={key} className="grid grid-cols-[1fr_70px] items-center gap-4"><span className="text-xs capitalize text-zinc-600">{key.replaceAll("_", " ")}</span><Input className="h-9 border-zinc-200 text-right" type="number" min={0} max={100} value={value} onChange={(event) => setSettings({ ...settings, risk_weights: { ...settings.risk_weights, [key]: Number(event.target.value) } })} /></label>)}<div className={`flex items-center justify-between rounded-xl p-3 text-xs font-semibold ${riskTotal === 100 ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}><span>Total</span><span>{riskTotal}%</span></div></div></SettingsSection><SettingsSection title="Protected controls" description="These safeguards are locked in the current environment."><div className="space-y-3"><LockedControl icon={ShieldCheck} title="Human approval required" detail="Every real organizational decision ends at a human approval gate." /><LockedControl icon={Users} title="People remain anonymized" detail="The twin uses role and person tokens, never employee rankings." /><LockedControl icon={FileText} title="Evidence remains traceable" detail="Reported impacts retain evidence, confidence, and dependency paths." /></div></SettingsSection></div> : null}
            </div>
          </section>
        </div>
      </div>
      {addingDepartment ? <DepartmentChange baselineOnly profile={{...profile, twin_version:twinVersion, organization, departments, settings}} user={user} onClose={() => setAddingDepartment(false)} onSaved={(updated) => {
        const added = updated.departments.filter(department => !departments.some(existing => existing.department_id === department.department_id));
        setTwinVersion(updated.twin_version);
        setDepartments(current => [...current, ...added]);
        setOrganization(current => ({...current, total_headcount_fte:updated.organization.total_headcount_fte, total_annual_budget_usd:updated.organization.total_annual_budget_usd}));
        if (added[0]) { setSelectedDepartmentId(added[0].department_id); setDepartmentAdded(added[0].name); }
        setSaved(false);
      }} /> : null}
    </main>
  );
}

function SettingsSection({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="grid gap-6 border-b border-zinc-100 py-8 last:border-b-0 lg:grid-cols-[240px_1fr]"><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-2 text-[11px] leading-5 text-zinc-500">{description}</p></div><div>{children}</div></section>;
}

function DepartmentSummaryCard({ label, value, detail, alert = false }: { label: string; value: string; detail: string; alert?: boolean }) {
  return <div className="min-w-0 rounded-2xl border border-zinc-200 bg-zinc-50/60 p-3 sm:p-4"><span className="block truncate text-[8px] font-semibold uppercase tracking-[.1em] text-zinc-400 sm:text-[9px] sm:tracking-[.12em]">{label}</span><div className="mt-2 flex items-baseline gap-2"><strong className={`text-xl tracking-[-.04em] sm:text-2xl ${alert ? "text-rose-700" : "text-zinc-950"}`}>{value}</strong><span className="hidden truncate text-[9px] text-zinc-500 sm:inline">{detail}</span></div></div>;
}

type ContextNumberField = "annual_cost_usd" | "capacity_fte" | "min_qualified_owners" | "documented_pct" | "failure_cost_per_day_usd" | "completion_pct" | "remaining_cost_usd" | "expected_completion_day" | "time_to_train_days" | "kpi_baseline";

function ContextSpecificFields({ draft, onChange }: { draft: DepartmentContextItemCreate; onChange: (value: DepartmentContextItemCreate) => void }) {
  const numberField = (field: ContextNumberField, label: string, options: { min?: number; max?: number; step?: number } = {}) => <label key={field}><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">{label}</span><Input className={fieldClass} required type="number" min={options.min ?? 0} max={options.max} step={options.step ?? 1} value={draft[field] ?? ""} onChange={(event) => onChange({ ...draft, [field]: event.target.value === "" ? undefined : Number(event.target.value) })} /></label>;

  if (draft.entity_type === "workflow") return <>{numberField("min_qualified_owners", "Minimum qualified owners")}{numberField("documented_pct", "Documentation coverage (0–1)", { max: 1, step: 0.05 })}{numberField("failure_cost_per_day_usd", "Failure cost per day (USD)")}</>;
  if (draft.entity_type === "system") return <>{numberField("annual_cost_usd", "Annual cost (USD)")}{numberField("failure_cost_per_day_usd", "Failure cost per day (USD)")}</>;
  if (draft.entity_type === "project") return <>{numberField("annual_cost_usd", "Annual cost (USD)")}{numberField("completion_pct", "Completion (0–1)", { max: 1, step: 0.05 })}{numberField("remaining_cost_usd", "Remaining cost (USD)")}{numberField("expected_completion_day", "Expected completion in days")}</>;
  if (draft.entity_type === "role") return <>{numberField("annual_cost_usd", "Annual role cost (USD)")}{numberField("capacity_fte", "Capacity (FTE)", { step: 0.1 })}{numberField("time_to_train_days", "Time to train (days)")}</>;
  if (draft.entity_type === "knowledge_asset") return <>{numberField("documented_pct", "Documentation coverage (0–1)", { max: 1, step: 0.05 })}</>;
  return <>{numberField("kpi_baseline", "Current baseline", { min: -1000000000, step: 0.01 })}<label><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">Unit</span><Input className={fieldClass} required maxLength={40} placeholder="%, days, USD, count…" value={draft.kpi_unit ?? ""} onChange={(event) => onChange({ ...draft, kpi_unit: event.target.value })} /></label><label><span className="mb-1.5 block text-[9px] font-semibold text-zinc-500">Desired direction</span><select required className={`${fieldClass} w-full px-3`} value={draft.higher_is_better === undefined ? "" : String(draft.higher_is_better)} onChange={(event) => onChange({ ...draft, higher_is_better: event.target.value === "true" })}><option value="" disabled>Select direction</option><option value="true">Higher is better</option><option value="false">Lower is better</option></select></label></>;
}

function LockedControl({ icon: Icon, title, detail }: { icon: typeof CircleGauge; title: string; detail: string }) {
  return <div className="flex items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-4"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-600 shadow-sm"><Icon className="size-4" /></span><div className="min-w-0 flex-1"><strong className="text-xs">{title}</strong><p className="mt-0.5 text-[10px] leading-4 text-zinc-500">{detail}</p></div><Badge variant="outline" className="border-zinc-200 bg-white text-[9px] text-zinc-500">Locked on</Badge></div>;
}

function InlineMarkdown({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/).map((part, index) => part.startsWith("**") && part.endsWith("**") ? <strong key={`${index}-${part}`}>{part.slice(2, -2)}</strong> : part)}</>;
}

function SkillContent({ content }: { content: string }) {
  return <div className="space-y-4">{content.split(/\n\s*\n/).filter(Boolean).map((block, index) => {
    if (block.startsWith("## ")) return <h4 key={block} className="pt-1 text-[10px] font-semibold uppercase tracking-[.12em] text-zinc-400">{block.slice(3)}</h4>;
    const lines = block.split("\n");
    if (lines.every((line) => line.startsWith("- "))) return <ul key={`${index}-${block}`} className="space-y-2">{lines.map((line) => <li key={line} className="flex gap-2 text-[11px] leading-5 text-zinc-600"><span className="mt-2 size-1 shrink-0 rounded-full bg-zinc-400" /><span><InlineMarkdown text={line.slice(2)} /></span></li>)}</ul>;
    return <p key={`${index}-${block}`} className="text-[11px] leading-5 text-zinc-600"><InlineMarkdown text={lines.join(" ")} /></p>;
  })}</div>;
}

function AgentSkillCard({ skill }: { skill: AgentSkillFile }) {
  return <details className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white">
    <summary className="flex cursor-pointer list-none items-center gap-3 p-4 marker:hidden">
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-700"><BookOpenText className="size-4" /></span>
      <div className="min-w-0 flex-1"><strong className="block text-xs">{skill.display_name}</strong><span className="mt-1 block truncate text-[9px] text-zinc-400">{skill.file_path}</span></div>
      <Badge className={`border-0 text-[9px] ${skill.source === "skill" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{skill.source === "skill" ? "Skill file" : "Fallback"}</Badge>
      <ChevronDown className="size-4 text-zinc-400 transition-transform group-open:rotate-180" />
    </summary>
    <div className="border-t border-zinc-100 bg-zinc-50/60 px-5 py-5"><SkillContent content={skill.content} /></div>
  </details>;
}
