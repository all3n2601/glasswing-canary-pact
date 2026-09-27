"use client";

import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";

export function BackendUnavailable({ resource = "company data" }: { resource?: string }) {
  const router = useRouter();
  const [retrying, startTransition] = useTransition();
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <SiteHeader />
      <section className="mx-auto grid min-h-[calc(100vh-80px)] max-w-2xl place-items-center px-5 py-16 text-center">
        <div>
          <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-amber-50 text-amber-700"><AlertTriangle className="size-5" /></span>
          <h1 className="mt-6 text-4xl font-semibold tracking-[-.045em]">We couldn’t load this page.</h1>
          <p className="mx-auto mt-4 max-w-lg text-sm leading-6 text-zinc-500">We couldn’t retrieve {resource}. The service may be busy or temporarily unreachable. Try again in a moment.</p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button disabled={retrying} onClick={() => startTransition(() => router.refresh())}><RefreshCw className={retrying ? "animate-spin" : undefined} />{retrying ? "Trying again…" : "Try again"}</Button>
            <Button asChild variant="outline"><Link href="/"><ArrowLeft />Return home</Link></Button>
          </div>
          <p role="status" aria-live="polite" className="mt-3 text-sm text-zinc-500">{retrying ? "Reconnecting to your workspace…" : ""}</p>
        </div>
      </section>
    </main>
  );
}
