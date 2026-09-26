import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  output: "standalone",
  transpilePackages: ["@canary-pact/contracts"],
};

export default nextConfig;
