import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { DecisionDashboard } from "@/components/decision-dashboard";
import { getOrganizationProfile } from "@/lib/canary-api-server";

export const metadata: Metadata = {
  title: "Simulator · Canary Pact",
  description: "Explore a decision across the organizational twin.",
};

export default async function SimulatorPage() {
  try {
    return <DecisionDashboard profile={await getOrganizationProfile()} />;
  } catch {
    return <BackendUnavailable resource="organization and simulation data" />;
  }
}
