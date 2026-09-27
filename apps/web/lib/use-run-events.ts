"use client";
import { useEffect, useState } from "react";
import type { Event } from "@canary-pact/contracts/generated";
import { canaryApi } from "./canary-api-client";
import { mergeRunEvents } from "./run-events";

export function useRunEvents(runId: string | null) {
  const [state, setState] = useState<{runId: string | null; events: Event[]; error: string | null; complete: boolean}>({runId: null, events: [], error: null, complete: false});
  useEffect(() => {
    setState({runId, events: [], error: null, complete: false});
    if (!runId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let cursor = 0;
    let failures = 0;
    const poll = async () => {
      try {
        const page = await canaryApi.eventLog(runId, cursor, controller.signal);
        if (controller.signal.aborted) return;
        cursor = page.next_sequence;
        failures = 0;
        const complete = page.terminal && !page.has_more;
        setState(old => ({runId, events: mergeRunEvents(runId, old.events, page.events), error: null, complete}));
        if (!complete) timer = setTimeout(poll, page.has_more ? 0 : 1000);
      } catch (error) {
        if (controller.signal.aborted) return;
        setState(old => ({...old, error: error instanceof Error ? error.message : "Reconnecting to the run"}));
        timer = setTimeout(poll, Math.min(15000, 1000 * 2 ** Math.min(++failures, 4)));
      }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [runId]);
  return state.runId === runId ? state : {runId, events: [], error: null, complete: false};
}
