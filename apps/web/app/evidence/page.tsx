import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { EvidenceReview } from "@/components/evidence-review";
import { requireUser } from "@/lib/auth-server";

export const metadata: Metadata = { title: "Evidence and assumptions · Canary Pact", description: "Inspect the evidence, confidence, and assumptions behind a simulation." };

export default async function EvidencePage() {
  if (!await requireUser("/evidence")) return <BackendUnavailable resource="account verification" />;

  return <EvidenceReview />;
}
