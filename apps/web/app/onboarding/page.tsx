import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { OrganizationOnboarding } from "@/components/organization-onboarding";
import { getOrganizationProfile } from "@/lib/canary-api-server";
import { requireUser } from "@/lib/auth-server";

export const metadata: Metadata = {
  title: "Organization setup · Canary Pact",
  description: "Create the baseline context for your organizational twin.",
};

export default async function OnboardingPage() {
  if (!await requireUser("/onboarding")) return <BackendUnavailable resource="account verification" />;

  try {
    return <OrganizationOnboarding profile={await getOrganizationProfile()} />;
  } catch {
    return <BackendUnavailable resource="organization profile data" />;
  }
}
