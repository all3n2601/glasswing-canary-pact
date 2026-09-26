import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@canary-pact/contracts"],
};

export default nextConfig;

