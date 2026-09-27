import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { BackendUnavailable } from "@/components/backend-unavailable";
import { getSession } from "@/lib/auth-server";
import { safeReturnTo } from "@/lib/auth";

export const metadata: Metadata = { title: "Create account · Canary Pact", description: "Create a Canary Pact viewer account." };

export default async function SignupPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const session = await getSession();
  if (session.unavailable) return <BackendUnavailable resource="account verification" />;
  if (session.user) redirect(safeReturnTo(next));
  return <AuthForm mode="signup" returnTo={next} />;
}
