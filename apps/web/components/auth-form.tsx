"use client";

import { ArrowRight, Eye, EyeOff, LoaderCircle, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Brand } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login, signup } from "@/lib/auth";

type AuthFormProps = { mode: "login" | "signup"; returnTo?: string };

function safeReturnTo(value?: string) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/simulate";
}

export function AuthForm({ mode, returnTo }: AuthFormProps) {
  const isSignup = mode === "signup";
  const router = useRouter();
  const { setUser } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    try {
      const response = isSignup
        ? await signup({ email, password, display_name: String(form.get("displayName") ?? "").trim() })
        : await login({ email, password });
      setUser(response.user);
      router.push(safeReturnTo(returnTo));
      router.refresh();
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Could not authenticate");
    } finally { setSubmitting(false); }
  };

  return <main className="grid min-h-dvh bg-white lg:grid-cols-[0.92fr_1.08fr]">
    <section className="flex min-h-dvh flex-col px-5 py-5 sm:px-10 sm:py-8 lg:px-16 xl:px-24">
      <Brand />
      <div className="mx-auto flex w-full max-w-[430px] flex-1 flex-col justify-center py-14">
        <span className="mb-7 grid size-11 place-items-center rounded-2xl bg-zinc-950 text-white shadow-lg shadow-zinc-200"><LockKeyhole className="size-5" /></span>
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-400">Secure workspace</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-[-0.05em] text-zinc-950 sm:text-5xl">{isSignup ? "Create your account." : "Welcome back."}</h1>
        <p className="mt-4 text-sm leading-6 text-zinc-500">{isSignup ? "Join the shared company twin and explore evidence-backed decisions." : "Sign in to create scenarios and return to your decision workspace."}</p>
        <form onSubmit={submit} className="mt-9 space-y-5">
          {isSignup ? <label className="block"><span className="mb-2 block text-xs font-semibold text-zinc-700">Display name</span><Input name="displayName" autoComplete="name" required minLength={1} maxLength={120} placeholder="Alex Morgan" className="h-12 border-zinc-200 bg-white" /></label> : null}
          <label className="block"><span className="mb-2 block text-xs font-semibold text-zinc-700">Work email</span><Input name="email" type="email" autoComplete="email" required maxLength={254} placeholder="alex@company.com" className="h-12 border-zinc-200 bg-white" /></label>
          <label className="block"><span className="mb-2 block text-xs font-semibold text-zinc-700">Password</span><span className="relative block">
            <Input name="password" type={showPassword ? "text" : "password"} autoComplete={isSignup ? "new-password" : "current-password"} required minLength={isSignup ? 8 : undefined} maxLength={256} placeholder={isSignup ? "At least 8 characters" : "Enter your password"} className="h-12 border-zinc-200 bg-white pr-12" />
            <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-zinc-400 hover:text-zinc-700">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button>
          </span></label>
          {error ? <p role="alert" className="rounded-xl border border-rose-100 bg-rose-50 px-3.5 py-3 text-xs text-rose-700">{error}</p> : null}
          <Button type="submit" disabled={submitting} className="h-12 w-full rounded-xl bg-zinc-950 text-white hover:bg-zinc-800">{submitting ? <LoaderCircle className="animate-spin" /> : null}{submitting ? (isSignup ? "Creating account…" : "Signing in…") : (isSignup ? "Create account" : "Sign in")}{!submitting ? <ArrowRight /> : null}</Button>
        </form>
        <p className="mt-7 text-center text-xs text-zinc-500">{isSignup ? "Already have an account?" : "New to Canary Pact?"} <Link className="font-semibold text-zinc-950 hover:underline" href={isSignup ? "/login" : "/signup"}>{isSignup ? "Sign in" : "Create an account"}</Link></p>
      </div>
      <p className="text-[10px] leading-5 text-zinc-400">Human approval remains required for organizational decisions.</p>
    </section>
    <aside className="relative hidden overflow-hidden bg-zinc-950 p-12 text-white lg:flex lg:flex-col lg:justify-between xl:p-16">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgb(59_130_246/.22),transparent_34%),radial-gradient(circle_at_20%_78%,rgb(16_185_129/.18),transparent_32%)]" />
      <div className="relative flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-400"><ShieldCheck className="size-4 text-emerald-400" /> Decision access, controlled</div>
      <div className="relative max-w-xl"><blockquote className="text-4xl font-medium leading-[1.12] tracking-[-0.045em] xl:text-5xl">“See who carries the risk before the organization carries the consequence.”</blockquote><div className="mt-10 grid gap-3 sm:grid-cols-3">{["Evidence linked", "Roles enforced", "Humans decide"].map((item, index) => <div key={item} className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur"><span className="text-[10px] text-zinc-500">0{index + 1}</span><strong className="mt-6 block text-xs">{item}</strong></div>)}</div></div>
      <p className="relative max-w-md text-xs leading-5 text-zinc-500">Viewer accounts can create and inspect simulations. Final approval remains restricted to configured approvers.</p>
    </aside>
  </main>;
}
