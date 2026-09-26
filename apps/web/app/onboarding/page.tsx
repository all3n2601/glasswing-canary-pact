import type { Metadata } from "next";

import { OrganizationOnboarding } from "@/components/organization-onboarding";
import { getOrganizationProfile } from "@/lib/canary-api-server";

export const metadata: Metadata = {
  title: "Organization setup · Canary Pact",
  description: "Create the baseline context for your organizational twin.",
};

export default async function OnboardingPage() {
  const { profile, connection } = await getOrganizationProfile();
  return <OrganizationOnboarding profile={profile} connection={connection} />;
}
