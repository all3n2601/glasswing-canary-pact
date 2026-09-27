import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { BackendUnavailable } from "@/components/backend-unavailable";
import { getSession } from "@/lib/auth-server";
import { safeReturnTo } from "@/lib/auth";

export const metadata: Metadata = { title: "Sign in · Canary Pact", description: "Sign in to your Canary Pact decision workspace." };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const session = await getSession();
  if (session.unavailable) return <BackendUnavailable resource="account verification" />;
  if (session.user) redirect(safeReturnTo(next));
  return <AuthForm mode="login" returnTo={next} />;
}
