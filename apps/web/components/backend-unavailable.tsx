import { AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";

export function BackendUnavailable({ resource = "company data" }: { resource?: string }) {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <SiteHeader />
      <section className="mx-auto grid min-h-[calc(100vh-80px)] max-w-2xl place-items-center px-5 py-16 text-center">
        <div>
          <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-amber-50 text-amber-700"><AlertTriangle className="size-5" /></span>
          <h1 className="mt-6 text-4xl font-semibold tracking-[-.045em]">The Canary API is unavailable.</h1>
          <p className="mx-auto mt-4 max-w-lg text-sm leading-6 text-zinc-500">This screen requires live {resource}. No local fixture or mock result was substituted.</p>
          <Button asChild variant="outline" className="mt-7"><Link href="/"><ArrowLeft />Return home</Link></Button>
        </div>
      </section>
    </main>
  );
}
