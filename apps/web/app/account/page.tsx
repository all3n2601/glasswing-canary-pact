import type { Metadata } from "next";

import { AccountPage } from "@/components/account-page";
import { BackendUnavailable } from "@/components/backend-unavailable";
import { requireUser } from "@/lib/auth-server";

export const metadata: Metadata = { title: "Account · Canary Pact", description: "Review your Canary Pact identity and access level." };

export default async function AccountRoute() {
  if (!await requireUser("/account")) return <BackendUnavailable resource="account verification" />;
  return <AccountPage />;
}
