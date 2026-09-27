import type { Metadata } from "next";

import { AuthProvider } from "@/components/auth-provider";
import { getSession } from "@/lib/auth-server";

import "./globals.css";

export const metadata: Metadata = {
  title: "Canary Pact · Organizational simulation",
  description: "Explore the organizational blast radius of a decision before committing.",
  icons: { icon: "/canary-pact-logo-v3.png" },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const session = await getSession();
  return (
    <html lang="en">
      <body><AuthProvider initialUser={session.user} unavailable={session.unavailable}>{children}</AuthProvider></body>
    </html>
  );
}
