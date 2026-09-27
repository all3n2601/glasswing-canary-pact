"use client";

import type { DecisionPackage } from "@canary-pact/contracts/generated";
import { useEffect, useState } from "react";

import { canaryApi } from "@/lib/canary-api-client";

export function useLastDecisionPackage() {
  const [decisionPackage, setDecisionPackage] = useState<DecisionPackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const runId = window.localStorage.getItem("canary:last-run-id");
    if (!runId) {
      setLoading(false);
      return;
    }
    let active = true;
    canaryApi.package(runId)
      .then((value) => { if (active) setDecisionPackage(value); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Could not load the decision package."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return { decisionPackage, loading, error };
}
