import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Create account · Canary Pact", description: "Create a Canary Pact viewer account." };

export default function SignupPage() { return <AuthForm mode="signup" />; }
