import type { Metadata } from "next";

import { DecisionDashboard } from "@/components/decision-dashboard";

export const metadata: Metadata = {
  title: "Simulator · Canary Pact",
  description: "Explore a decision across the organizational twin.",
};

export default function SimulatorPage() {
  return <DecisionDashboard />;
}
