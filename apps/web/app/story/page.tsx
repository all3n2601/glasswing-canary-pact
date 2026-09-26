import type { Metadata } from "next";

import { SimulationStory } from "@/components/simulation-story";

export const metadata: Metadata = {
  title: "Simulation storyboard · Canary Pact",
  description: "Follow the evidence-backed consequences of an organizational decision.",
};

export default function StoryPage() {
  return <SimulationStory />;
}
