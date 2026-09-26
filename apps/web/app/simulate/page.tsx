import type { Metadata } from "next";

import { DecisionDashboard } from "@/components/decision-dashboard";
import { getOrganizationProfile } from "@/lib/canary-api-server";

export const metadata: Metadata = {
  title: "Simulator · Canary Pact",
  description: "Explore a decision across the organizational twin.",
};

export default async function SimulatorPage() {
  const { profile, connection } = await getOrganizationProfile();
  return <DecisionDashboard profile={profile} connection={connection} />;
}
