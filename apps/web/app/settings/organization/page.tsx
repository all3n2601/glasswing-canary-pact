import type { Metadata } from "next";

import { OrganizationSettings } from "@/components/organization-settings";
import { getOrganizationProfile } from "@/lib/canary-api-server";

export const metadata: Metadata = {
  title: "Organization settings · Canary Pact",
  description: "Manage organization context and simulation defaults.",
};

export default async function OrganizationSettingsPage() {
  const { profile, connection } = await getOrganizationProfile();
  return <OrganizationSettings profile={profile} connection={connection} />;
}
