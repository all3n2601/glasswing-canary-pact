import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { OrganizationSettings } from "@/components/organization-settings";
import { getAgentSkillFiles, getOrganizationProfile } from "@/lib/canary-api-server";
import { requireUser } from "@/lib/auth-server";

export const metadata: Metadata = {
  title: "Organization settings · Canary Pact",
  description: "Manage organization context and simulation defaults.",
};

export default async function OrganizationSettingsPage() {
  if (!await requireUser("/settings/organization")) return <BackendUnavailable resource="account verification" />;

  try {
    const [profile, agentSkills] = await Promise.all([getOrganizationProfile(), getAgentSkillFiles()]);
    return <OrganizationSettings profile={profile} agentSkills={agentSkills} />;
  } catch {
    return <BackendUnavailable resource="organization settings" />;
  }
}
