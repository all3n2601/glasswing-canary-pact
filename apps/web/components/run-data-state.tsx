import { AlertTriangle, LoaderCircle, Play } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function RunDataState({ loading, error }: { loading: boolean; error?: string | null }) {
  return (
    <section className="mx-5 grid min-h-[360px] max-w-[1256px] place-items-center rounded-[24px] border border-zinc-200 bg-zinc-50 p-8 text-center lg:mx-auto">
      <div>
        {loading
          ? <LoaderCircle className="mx-auto size-7 animate-spin text-zinc-400" />
          : <AlertTriangle className="mx-auto size-7 text-amber-600" />}
        <h2 className="mt-5 text-2xl font-semibold">{loading ? "Loading the latest run…" : error ? "The decision package could not be loaded." : "No completed simulation is available."}</h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-zinc-500">{error ?? (loading ? "Results will appear as soon as the backend responds." : "Run a simulation first. This screen does not substitute local or fabricated results.")}</p>
        {!loading ? <Button asChild className="mt-6 bg-zinc-950 text-white hover:bg-zinc-800"><Link href="/simulate"><Play />Open simulator</Link></Button> : null}
      </div>
    </section>
  );
}
