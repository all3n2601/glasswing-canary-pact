import "server-only";

import type { AgentSkillFile, OrganizationProfileView } from "@canary-pact/contracts/generated";

import type { OrganizationProfile } from "@canary-pact/contracts";

import { normalizeProfile } from "./organization-profile";
import { authToken } from "./auth-server";
import { readBackend } from "./canary-api-transport";

async function sessionHeaders(): Promise<Record<string, string>> {
  const token = await authToken();
  return { Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export async function getOrganizationProfile(): Promise<OrganizationProfile> {
  const response = await readBackend("/organization/profile", await sessionHeaders());
  if (!response.ok) throw new Error(`Canary API returned ${response.status}`);
  return normalizeProfile((await response.json()) as OrganizationProfileView);
}

export async function getAgentSkillFiles(): Promise<AgentSkillFile[]> {
  const response = await readBackend("/organization/agent-skills", await sessionHeaders());
  if (!response.ok) throw new Error(`Canary API returned ${response.status}`);
  return response.json() as Promise<AgentSkillFile[]>;
}
