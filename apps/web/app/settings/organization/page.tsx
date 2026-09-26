import type { Metadata } from "next";

import { OrganizationSettings } from "@/components/organization-settings";
import { organizationProfile } from "@/lib/organization-data";

export const metadata: Metadata = {
  title: "Organization settings · Canary Pact",
  description: "Manage organization context and simulation defaults.",
};

export default function OrganizationSettingsPage() {
  return <OrganizationSettings profile={organizationProfile} />;
}
