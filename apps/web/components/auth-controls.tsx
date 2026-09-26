"use client";

import { ChevronDown, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

export function AuthControls({ compact = false }: { compact?: boolean }) {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const router = useRouter();

  if (loading) return <div className="h-9 w-24 animate-pulse rounded-xl bg-zinc-100" aria-label="Loading account" />;
  if (!user) {
    return <div className="flex items-center gap-1.5">
      {!compact ? <Button asChild variant="ghost" size="sm"><Link href="/login">Log in</Link></Button> : null}
      <Button asChild size="sm" className="rounded-xl bg-zinc-950 text-white hover:bg-zinc-800"><Link href={compact ? "/login" : "/signup"}>{compact ? "Sign in" : "Get started"}</Link></Button>
    </div>;
  }

  const initials = user.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  const signOut = async () => {
    setSigningOut(true);
    try {
      await logout();
      setOpen(false);
      router.push("/");
      router.refresh();
    } finally { setSigningOut(false); }
  };

  return <div className="relative">
    <button type="button" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((value) => !value)} className="flex h-10 items-center gap-2 rounded-xl border border-zinc-200 bg-white px-2 pr-3 text-left shadow-sm transition-colors hover:bg-zinc-50">
      <span className="grid size-7 place-items-center rounded-lg bg-zinc-950 text-[10px] font-bold text-white">{initials}</span>
      {!compact ? <span className="hidden max-w-28 truncate text-xs font-semibold lg:block">{user.display_name}</span> : null}
      <ChevronDown className="size-3 text-zinc-400" />
    </button>
    {open ? <div role="menu" className="absolute right-0 top-12 z-[80] w-60 rounded-2xl border border-zinc-200 bg-white p-2 shadow-[0_18px_55px_rgb(0_0_0/.14)]">
      <div className="border-b border-zinc-100 px-3 py-2.5"><strong className="block truncate text-xs">{user.display_name}</strong><span className="mt-0.5 block truncate text-[10px] text-zinc-500">{user.email}</span></div>
      <Link role="menuitem" href="/account" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950"><UserRound className="size-3.5" /> Account</Link>
      <button role="menuitem" type="button" disabled={signingOut} onClick={() => void signOut()} className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950 disabled:opacity-50"><LogOut className="size-3.5" /> {signingOut ? "Signing out…" : "Sign out"}</button>
    </div> : null}
  </div>;
}
