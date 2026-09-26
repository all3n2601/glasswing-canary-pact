import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { OrganizationSettings } from "@/components/organization-settings";
import { getOrganizationProfile } from "@/lib/canary-api-server";

export const metadata: Metadata = {
  title: "Organization settings · Canary Pact",
  description: "Manage organization context and simulation defaults.",
};

export default async function OrganizationSettingsPage() {
  try {
    return <OrganizationSettings profile={await getOrganizationProfile()} />;
  } catch {
    return <BackendUnavailable resource="organization settings" />;
  }
}
