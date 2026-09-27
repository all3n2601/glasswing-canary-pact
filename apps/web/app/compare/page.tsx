import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { FuturesComparison } from "@/components/futures-comparison";
import { requireUser } from "@/lib/auth-server";

export const metadata: Metadata = { title: "Compare scenarios · Canary Pact", description: "Compare possible organizational futures and their tradeoffs." };

export default async function ComparePage() {
  if (!await requireUser("/compare")) return <BackendUnavailable resource="account verification" />;

  return <FuturesComparison />;
}
