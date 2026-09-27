import type { AgentAssessment, Event } from "@canary-pact/contracts/generated";

export function mergeRunEvents(runId: string, previous: Event[], incoming: Event[]): Event[] {
  const bySequence = new Map<number, Event>();
  for (const event of [...previous, ...incoming]) {
    if (event.run_id === runId && !bySequence.has(event.sequence)) bySequence.set(event.sequence, event);
  }
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}

export interface BoardParticipant {
  key: string;
  agentId: string;
  planId: string | null;
  status: "analyzing" | "available" | "unavailable";
  assessment?: AgentAssessment;
  challenge: boolean;
  reason?: string;
  passType?: string;
}

export function boardParticipants(events: Event[]): BoardParticipant[] {
  const participants = new Map<string, BoardParticipant>();
  for (const event of events) {
    const payload = event.payload;
    if (event.type === "run_failed") {
      for (const [key, participant] of participants) {
        if (participant.status === "analyzing") participants.set(key, {...participant,
          status: "unavailable", reason: "The run ended before this assessment was received."});
      }
      continue;
    }
    if (!("agent_id" in payload)) continue;
    const planId = "plan_id" in payload ? payload.plan_id ?? null : null;
    const key = `${payload.agent_id}:${planId ?? "all"}`;
    if (event.type === "agent_started") {
      const passType = "pass_type" in payload ? String(payload.pass_type) : "first_pass";
      const startedKey = `${key}:${passType}`;
      participants.set(startedKey, {key: startedKey, agentId: payload.agent_id, planId, passType,
        status: "analyzing", challenge: passType === "challenge"});
    } else if (event.type === "agent_completed" || event.type === "challenge_raised") {
      if (!("assessment_id" in payload)) continue;
      const assessment = payload as AgentAssessment;
      const assessmentKey = `${key}:${assessment.pass_type ?? "first_pass"}`;
      participants.delete(key);
      // Older event logs do not identify the challenger pass on their start event.
      for (const [pendingKey, pending] of participants) {
        if (pending.agentId === assessment.agent_id && pending.planId === planId && !pending.assessment)
          participants.delete(pendingKey);
      }
      participants.set(assessmentKey, {key: assessmentKey, agentId: assessment.agent_id, planId,
        passType: assessment.pass_type,
        status: assessment.status === "ok" ? "available" : "unavailable", assessment,
        challenge: event.type === "challenge_raised" || Boolean(assessment.challenge),
        reason: assessment.validation?.errors?.join("; ")});
    } else if (event.type === "agent_failed") {
      // Failure envelopes currently omit plan_id; attach to this agent's active call.
      const active = [...participants.values()].reverse().find(p => p.agentId === payload.agent_id && p.status === "analyzing");
      const failedKey = active?.key ?? key;
      participants.set(failedKey, {...(active ?? {key: failedKey, agentId: payload.agent_id, planId, challenge: false}),
        status: "unavailable", reason: "reason" in payload ? String(payload.reason) : "Assessment unavailable"});
    }
  }
  return [...participants.values()];
}
