"use client";

import type { BlastRadius, DecisionBrief, SimulationResult } from "@canary-pact/contracts/generated";
import { createContext, useContext, useMemo, useState } from "react";
import { useAuth } from "./auth-provider";

export type SimulationOutcomeView = {
  organizationId: string;
  twinVersion?: string;
  runId: string | null;
  resultId: string;
  day: number;
  title: string;
  options: Array<{ value: string; label: string; description: string }>;
  preview: { brief: DecisionBrief; result: SimulationResult; blast: BlastRadius } | null;
};

const OutcomeContext = createContext<{
  outcome: SimulationOutcomeView | null;
  setOutcome: React.Dispatch<React.SetStateAction<SimulationOutcomeView | null>>;
} | null>(null);

function OutcomeState({ children }: { children: React.ReactNode }) {
  const [outcome, setOutcome] = useState<SimulationOutcomeView | null>(null);
  const value = useMemo(() => ({ outcome, setOutcome }), [outcome]);
  return <OutcomeContext.Provider value={value}>{children}</OutcomeContext.Provider>;
}

// Keep the current view across client-side navigation, scoped to the signed-in user.
export function SimulationOutcomeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  return <OutcomeState key={user?.user_id ?? "signed-out"}>{children}</OutcomeState>;
}

export function useSimulationOutcome() {
  const context = useContext(OutcomeContext);
  if (!context) throw new Error("SimulationOutcomeProvider is required");
  return context;
}
