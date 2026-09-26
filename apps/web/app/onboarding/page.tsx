import type { Metadata } from "next";

import { OrganizationOnboarding } from "@/components/organization-onboarding";
import { organizationProfile } from "@/lib/organization-data";

export const metadata: Metadata = {
  title: "Organization setup · Canary Pact",
  description: "Create the baseline context for your organizational twin.",
};

export default function OnboardingPage() {
  return <OrganizationOnboarding profile={organizationProfile} />;
}
