"use client";

import { CalendarDays, Check, LogOut, Mail, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthControls } from "@/components/auth-controls";
import { useAuth } from "@/components/auth-provider";
import { Brand } from "@/components/site-header";
import { Button } from "@/components/ui/button";

export function AccountPage() {
  const { user, loading, logout } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace("/login?next=/account"); }, [loading, router, user]);
  if (loading || !user) return <main className="grid min-h-dvh place-items-center bg-white"><div className="size-8 animate-pulse rounded-xl bg-zinc-200" /></main>;

  const createdAt = new Intl.DateTimeFormat("en", { dateStyle: "long" }).format(new Date(user.created_at));
  const signOut = async () => {
    setSigningOut(true);
    try { await logout(); router.push("/"); router.refresh(); } finally { setSigningOut(false); }
  };

  return <main className="min-h-dvh bg-zinc-50/70 text-zinc-950">
    <header className="border-b border-zinc-200 bg-white"><div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-5 sm:px-8"><Brand /><AuthControls /></div></header>
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-400">Account</p><h1 className="mt-3 text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">Your workspace identity.</h1><p className="mt-4 max-w-xl text-sm leading-6 text-zinc-500">Your role controls which actions you can take. Company evidence remains shared and read-only access stays available.</p>
      <div className="mt-10 grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
        <section className="rounded-[24px] border border-zinc-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="flex items-center gap-4 border-b border-zinc-100 pb-7"><span className="grid size-14 place-items-center rounded-2xl bg-zinc-950 text-lg font-bold text-white"><UserRound className="size-6" /></span><div><h2 className="text-xl font-semibold">{user.display_name}</h2><p className="mt-1 text-xs capitalize text-zinc-500">{user.role} account</p></div></div>
          <dl className="mt-7 grid gap-6 sm:grid-cols-2">
            <div><dt className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-400"><Mail className="size-3" /> Email</dt><dd className="mt-2 text-sm font-medium">{user.email}</dd></div>
            <div><dt className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-400"><CalendarDays className="size-3" /> Member since</dt><dd className="mt-2 text-sm font-medium">{createdAt}</dd></div>
            <div><dt className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-400"><ShieldCheck className="size-3" /> Role</dt><dd className="mt-2 text-sm font-medium capitalize">{user.role}</dd></div>
            <div><dt className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">User ID</dt><dd className="mt-2 font-mono text-xs text-zinc-600">{user.user_id}</dd></div>
          </dl>
        </section>
        <section className="rounded-[24px] bg-zinc-950 p-6 text-white shadow-sm sm:p-8"><span className="grid size-10 place-items-center rounded-xl bg-white/10"><ShieldCheck className="size-4 text-emerald-400" /></span><h2 className="mt-6 text-xl font-semibold">Access level</h2><p className="mt-2 text-xs leading-5 text-zinc-400">{user.role === "approver" ? "You can inspect simulations and record final human decisions." : "You can create and inspect simulations. Final decisions require an approver."}</p><ul className="mt-6 space-y-3 text-xs text-zinc-300">{["View the company twin", "Create decision scenarios", ...(user.role === "approver" ? ["Approve or reject packages"] : [])].map((permission) => <li key={permission} className="flex items-center gap-2"><span className="grid size-5 place-items-center rounded-full bg-emerald-400/10 text-emerald-400"><Check className="size-3" /></span>{permission}</li>)}</ul></section>
      </div>
      <div className="mt-6 flex flex-col gap-3 rounded-[24px] border border-zinc-200 bg-white p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"><div><strong className="text-sm">Session controls</strong><p className="mt-1 text-xs text-zinc-500">Signing out revokes this session on the Canary Pact API.</p></div><div className="flex gap-2"><Button asChild variant="outline"><Link href="/simulate">Return to simulator</Link></Button><Button variant="destructive" disabled={signingOut} onClick={() => void signOut()}><LogOut />{signingOut ? "Signing out…" : "Sign out"}</Button></div></div>
    </div>
  </main>;
}
