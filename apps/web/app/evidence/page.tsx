import type { Metadata } from "next";
import { EvidenceReview } from "@/components/evidence-review";

export const metadata: Metadata = { title: "Evidence and assumptions · Canary Pact", description: "Inspect the evidence, confidence, and assumptions behind a simulation." };

export default function EvidencePage() {
  return <EvidenceReview />;
}
