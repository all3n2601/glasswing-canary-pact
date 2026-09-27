import type { Metadata } from "next";

import { BackendUnavailable } from "@/components/backend-unavailable";
import { SimulationStory } from "@/components/simulation-story";
import { requireUser } from "@/lib/auth-server";

export const metadata: Metadata = {
  title: "Simulation storyboard · Canary Pact",
  description: "Follow the evidence-backed consequences of an organizational decision.",
};

export default async function StoryPage() {
  if (!await requireUser("/story")) return <BackendUnavailable resource="account verification" />;

  return <SimulationStory />;
}
