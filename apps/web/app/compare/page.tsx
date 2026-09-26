import type { Metadata } from "next";
import { FuturesComparison } from "@/components/futures-comparison";

export const metadata: Metadata = { title: "Compare scenarios · Canary Pact", description: "Compare possible organizational futures and their tradeoffs." };

export default function ComparePage() {
  return <FuturesComparison />;
}
