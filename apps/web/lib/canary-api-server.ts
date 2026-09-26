import "server-only";

import type { OrganizationProfileView } from "@canary-pact/contracts/generated";

import type { OrganizationProfile } from "@canary-pact/contracts";

const API_URL = process.env.CANARY_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function normalizeProfile(profile: OrganizationProfileView): OrganizationProfile {
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

export async function getOrganizationProfile(): Promise<OrganizationProfile> {
  const response = await fetch(`${API_URL}/organization/profile`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(3_000),
  });
  if (!response.ok) throw new Error(`Canary API returned ${response.status}`);
  return normalizeProfile((await response.json()) as OrganizationProfileView);
}
