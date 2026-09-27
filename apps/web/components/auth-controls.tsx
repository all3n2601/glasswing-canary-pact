"use client";

import { ChevronDown, LogOut, Settings2, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

export function AuthControls({ compact = false }: { compact?: boolean }) {
  const { user, loading, unavailable, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (event.target instanceof Node && !containerRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);

  if (loading) return <div className="h-9 w-24 animate-pulse rounded-xl bg-zinc-100" aria-label="Loading account" />;
  if (unavailable) return <Button variant="outline" size="sm" onClick={() => router.refresh()}>Retry account check</Button>;
  if (!user) {
    return <div className="flex items-center gap-1.5">
      {!compact ? <Button asChild variant="ghost" size="sm"><Link href="/login">Log in</Link></Button> : null}
      <Button asChild size="sm" className="rounded-xl bg-zinc-950 text-white hover:bg-zinc-800"><Link href={compact ? "/login" : "/signup"}>{compact ? "Sign in" : "Get started"}</Link></Button>
    </div>;
  }

  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  const signOut = async () => {
    setSigningOut(true);
    setSignOutError(false);
    try {
      await logout();
      setOpen(false);
      router.replace("/");
      router.refresh();
    } catch {
      setSignOutError(true);
    } finally { setSigningOut(false); }
  };

  return <div ref={containerRef} className="relative" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }} onKeyDown={(event) => {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    }
  }}>
    <button ref={triggerRef} type="button" aria-label="Profile and settings" title="Profile and settings" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((value) => !value)} className="flex h-10 shrink-0 items-center gap-2 rounded-xl border border-zinc-200 bg-white px-2 pr-3 text-left shadow-sm transition-colors hover:bg-zinc-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-950">
      <span className="grid size-7 place-items-center rounded-lg bg-zinc-950 text-[10px] font-bold text-white">{initials || <UserRound className="size-3.5" />}</span>
      {!compact ? <span className="hidden max-w-28 truncate text-xs font-semibold lg:block">{user.display_name}</span> : null}
      <ChevronDown className={`size-3 text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
    {open ? <nav id={panelId} aria-label="Profile and settings" className="absolute right-0 top-12 z-[80] w-60 max-w-[calc(100vw-2rem)] rounded-2xl border border-zinc-200 bg-white p-2 shadow-[0_18px_55px_rgb(0_0_0/.14)]">
      <div className="border-b border-zinc-100 px-3 py-2.5"><strong className="block truncate text-xs">{user.display_name}</strong><span className="mt-0.5 block truncate text-[10px] text-zinc-500">{user.email}</span></div>
      <Link href="/account" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950 focus-visible:bg-zinc-100"><UserRound className="size-3.5" /> My profile</Link>
      <Link href="/settings/organization" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950 focus-visible:bg-zinc-100"><Settings2 className="size-3.5" /> Organization settings</Link>
      <div className="mt-1 border-t border-zinc-100 pt-1">
        <button type="button" disabled={signingOut} onClick={() => void signOut()} className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950 focus-visible:bg-zinc-100 disabled:opacity-50"><LogOut className="size-3.5" /> {signingOut ? "Signing out…" : "Sign out"}</button>
        {signOutError ? <p role="alert" className="px-3 py-2 text-xs text-red-600">Could not sign out. Please try again.</p> : null}
      </div>
    </nav> : null}
  </div>;
}
