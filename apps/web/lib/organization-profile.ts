import type { OrganizationProfile } from "@canary-pact/contracts";
import type { OrganizationProfileView } from "@canary-pact/contracts/generated";

export function normalizeProfile(profile: OrganizationProfileView): OrganizationProfile {
  const required = <T,>(value: T | null | undefined, field: string): T => {
    if (value === null || value === undefined) throw new Error(`Organization profile is missing ${field}`);
    return value;
  };
  const normalizeSector = (sector: string): OrganizationProfile["organization"]["sector"] => {
    if (sector === "retail_ecommerce") return "retail_consumer";
    if (["technology_saas", "financial_services", "healthcare", "professional_services", "manufacturing", "public_sector", "other"].includes(sector)) {
      return sector as OrganizationProfile["organization"]["sector"];
    }
    return "other";
  };
  const defaultFutures = required(profile.settings.default_futures, "settings.default_futures")
    .filter((future): future is "act_now" | "inaction" | "delay" => future !== "alternative");
  return {
    schema_version: "2.0.0",
    twin_version: profile.twin_version ?? undefined,
    organization: {
      ...profile.organization,
      sector: normalizeSector(profile.organization.sector),
      sub_sector: profile.organization.sub_sector ?? undefined,
      secondary_sectors: (profile.organization.secondary_sectors ?? []).map(normalizeSector),
      operating_regions: profile.organization.operating_regions ?? [],
      regulatory_frameworks: profile.organization.regulatory_frameworks ?? [],
      strategic_priorities: (profile.organization.strategic_priorities ?? []).map((priority) => ({
        ...priority,
        kpi_ids: priority.kpi_ids ?? [],
      })),
      evidence_refs: profile.organization.evidence_refs ?? [],
    },
    departments: profile.departments,
    settings: {
      settings_id: required(profile.settings.settings_id, "settings.settings_id"),
      organization_id: required(profile.settings.organization_id, "settings.organization_id"),
      settings_version: required(profile.settings.settings_version, "settings.settings_version"),
      updated_by: required(profile.settings.updated_by, "settings.updated_by"),
      updated_at: required(profile.settings.updated_at, "settings.updated_at"),
      display_currency: required(profile.settings.display_currency, "settings.display_currency"),
      money_display_scale: required(profile.settings.money_display_scale, "settings.money_display_scale"),
      timezone: required(profile.settings.timezone, "settings.timezone"),
      locale: required(profile.settings.locale, "settings.locale"),
      default_horizon_days: required(profile.settings.default_horizon_days, "settings.default_horizon_days"),
      default_futures: defaultFutures,
      default_delay_days: required(profile.settings.default_delay_days, "settings.default_delay_days"),
      propagation_max_hops: required(profile.settings.propagation_max_hops, "settings.propagation_max_hops"),
      min_impact_threshold: required(profile.settings.min_impact_threshold, "settings.min_impact_threshold"),
      risk_appetite: required(profile.settings.risk_appetite, "settings.risk_appetite"),
      risk_weights: {
        financial: required(profile.settings.risk_weights?.financial, "settings.risk_weights.financial"),
        capability_workflow: required(profile.settings.risk_weights?.capability_workflow, "settings.risk_weights.capability_workflow"),
        customer_revenue: required(profile.settings.risk_weights?.customer_revenue, "settings.risk_weights.customer_revenue"),
        compliance_control: required(profile.settings.risk_weights?.compliance_control, "settings.risk_weights.compliance_control"),
        execution_uncertainty: required(profile.settings.risk_weights?.execution_uncertainty, "settings.risk_weights.execution_uncertainty"),
      },
      optimizer_objective: required(profile.settings.optimizer_objective, "settings.optimizer_objective"),
      always_protected_entity_ids: profile.settings.always_protected_entity_ids ?? [],
      require_human_approval: required(profile.settings.require_human_approval, "settings.require_human_approval"),
      anonymize_people: required(profile.settings.anonymize_people, "settings.anonymize_people"),
      llm_mode: required(profile.settings.llm_mode, "settings.llm_mode"),
      doc_staleness_days: required(profile.settings.doc_staleness_days, "settings.doc_staleness_days"),
    },
  };
}


export async function saveOrganizationProfile(profile: OrganizationProfile): Promise<OrganizationProfile> {
  const {canaryApi} = await import("./canary-api-client");
  const original = await canaryApi.organizationProfile();
  if (!profile.twin_version || original.twin_version !== profile.twin_version) throw new Error("Company changed. Reload before saving.");
  const departments = profile.departments.filter(d => {
    const before = original.departments.find(p=>p.department_id===d.department_id);
    return !before || d.name!==before.name || d.mission!==before.mission || d.actual_fte!==before.actual_fte || d.annual_budget_usd!==before.annual_budget_usd || d.utilisation!==before.utilisation;
  }).map(d=>({department_id:d.department_id,name:d.name,mission:d.mission,actual_fte:d.actual_fte,annual_budget_usd:d.annual_budget_usd,utilisation:d.utilisation,active:d.active ?? true,agent_id:d.agent_id,assumption:"User supplied department staffing and budget; workflow capability requires supporting evidence."}));
  const enabled = new Set(original.settings.enabled_agent_ids ?? []);
  for (const d of profile.departments) if(d.agent_id) {if(d.enabled) enabled.add(d.agent_id);else enabled.delete(d.agent_id);}
  const sector = (value: OrganizationProfile["organization"]["sector"]) => value === "retail_consumer" ? "retail_ecommerce" as const : value;
  return normalizeProfile(await canaryApi.saveOrganization({expected_twin_version:profile.twin_version,
    organization:{...original.organization,...profile.organization,sector:sector(profile.organization.sector),secondary_sectors:profile.organization.secondary_sectors.map(sector)},
    departments,settings:{...original.settings,...profile.settings,enabled_agent_ids:[...enabled]}}));
}
