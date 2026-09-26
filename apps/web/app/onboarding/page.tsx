import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { OrganizationOnboarding } from "@/components/organization-onboarding";
import { getOrganizationProfile } from "@/lib/canary-api-server";

export const metadata: Metadata = {
  title: "Organization setup · Canary Pact",
  description: "Create the baseline context for your organizational twin.",
};

export default async function OnboardingPage() {
  try {
    return <OrganizationOnboarding profile={await getOrganizationProfile()} />;
  } catch {
    return <BackendUnavailable resource="organization profile data" />;
  }
}
