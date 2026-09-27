import "server-only";

import type { AgentSkillFile, OrganizationProfileView } from "@canary-pact/contracts/generated";

import type { OrganizationProfile } from "@canary-pact/contracts";

const API_URL = process.env.CANARY_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

import { normalizeProfile } from "./organization-profile";
import { authToken } from "./auth-server";

async function sessionHeaders(): Promise<Record<string, string>> {
  const token = await authToken();
  return { Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export async function getOrganizationProfile(): Promise<OrganizationProfile> {
  const response = await fetch(`${API_URL}/organization/profile`, {
    cache: "no-store",
    headers: await sessionHeaders(),
    signal: AbortSignal.timeout(3_000),
  });
  if (!response.ok) throw new Error(`Canary API returned ${response.status}`);
  return normalizeProfile((await response.json()) as OrganizationProfileView);
}

export async function getAgentSkillFiles(): Promise<AgentSkillFile[]> {
  const response = await fetch(`${API_URL}/organization/agent-skills`, {
    cache: "no-store",
    headers: await sessionHeaders(),
    signal: AbortSignal.timeout(3_000),
  });
  if (!response.ok) throw new Error(`Canary API returned ${response.status}`);
  return response.json() as Promise<AgentSkillFile[]>;
}
