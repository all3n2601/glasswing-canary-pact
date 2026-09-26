import "server-only";

import type { OrganizationProfileView } from "@canary-pact/contracts/generated";

import type { OrganizationProfile } from "@canary-pact/contracts";

import fallbackProfile from "../../../data/organization_profile.json";

const API_URL = process.env.CANARY_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiConnection = "live" | "offline_fallback";

export interface OrganizationProfileResult {
  profile: OrganizationProfile;
  connection: ApiConnection;
}

function normalizeProfile(profile: OrganizationProfileView): OrganizationProfile {
  const normalizeSector = (sector: string): OrganizationProfile["organization"]["sector"] => {
    if (sector === "retail_ecommerce") return "retail_consumer";
    if (["technology_saas", "financial_services", "healthcare", "professional_services", "manufacturing", "public_sector", "other"].includes(sector)) {
      return sector as OrganizationProfile["organization"]["sector"];
    }
    return "other";
  };
  const defaultFutures = (profile.settings.default_futures ?? ["act_now", "inaction", "delay"])
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
      settings_id: profile.settings.settings_id ?? "settings_default",
      organization_id: profile.settings.organization_id ?? profile.organization.id,
      settings_version: profile.settings.settings_version ?? 1,
      updated_by: profile.settings.updated_by ?? "system",
      updated_at: profile.settings.updated_at ?? new Date(0).toISOString(),
      display_currency: profile.settings.display_currency ?? "USD",
      money_display_scale: profile.settings.money_display_scale ?? "auto",
      timezone: profile.settings.timezone ?? "UTC",
      locale: profile.settings.locale ?? "en-US",
      default_horizon_days: profile.settings.default_horizon_days ?? 365,
      default_futures: defaultFutures,
      default_delay_days: profile.settings.default_delay_days ?? 90,
      propagation_max_hops: profile.settings.propagation_max_hops ?? 4,
      min_impact_threshold: profile.settings.min_impact_threshold ?? 0.02,
      risk_appetite: profile.settings.risk_appetite ?? "balanced",
      risk_weights: {
        financial: profile.settings.risk_weights?.financial ?? 25,
        capability_workflow: profile.settings.risk_weights?.capability_workflow ?? 25,
        customer_revenue: profile.settings.risk_weights?.customer_revenue ?? 20,
        compliance_control: profile.settings.risk_weights?.compliance_control ?? 20,
        execution_uncertainty: profile.settings.risk_weights?.execution_uncertainty ?? 10,
      },
      optimizer_objective: profile.settings.optimizer_objective ?? "balanced",
      always_protected_entity_ids: profile.settings.always_protected_entity_ids ?? [],
      require_human_approval: true,
      anonymize_people: true,
      llm_mode: profile.settings.llm_mode ?? "replay",
      doc_staleness_days: profile.settings.doc_staleness_days ?? 365,
    },
  };
}

export async function getOrganizationProfile(): Promise<OrganizationProfileResult> {
  try {
    const response = await fetch(`${API_URL}/organization/profile`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) throw new Error(`Canary API returned ${response.status}`);
    return {
      profile: normalizeProfile((await response.json()) as OrganizationProfileView),
      connection: "live",
    };
  } catch {
    return {
      profile: fallbackProfile as OrganizationProfile,
      connection: "offline_fallback",
    };
  }
}
