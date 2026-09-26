import Image from "next/image";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function Brand() {
  return (
    <Link className="flex items-center" href="/" aria-label="Canary Pact home">
      <Image
        alt=""
        aria-hidden="true"
        className="h-8 w-auto sm:h-9"
        height={420}
        priority
        src="/canary-pact-logo-v3.png"
        width={1900}
      />
    </Link>
  );
}

export function SiteHeader() {
  return (
    <header className="relative z-50 mx-auto flex h-20 max-w-[1420px] items-center justify-between border-b border-zinc-100 px-5 md:px-7">
      <Brand />
      <nav className="flex items-center gap-2 md:gap-6" aria-label="Primary navigation">
        <Link className="hidden text-[11px] font-medium text-zinc-500 transition-colors hover:text-zinc-950 md:block" href="/#how-it-works">How it works</Link>
        <Link className="hidden text-[11px] font-medium text-zinc-500 transition-colors hover:text-zinc-950 md:block" href="/simulate">Simulation</Link>
        <Link className="hidden text-[11px] font-medium text-zinc-500 transition-colors hover:text-zinc-950 md:block" href="/story">Storyboard</Link>
        <Link className="hidden text-[11px] font-medium text-zinc-500 transition-colors hover:text-zinc-950 md:block" href="/evidence">Evidence</Link>
        <Link className="hidden text-[11px] font-medium text-zinc-500 transition-colors hover:text-zinc-950 lg:block" href="/settings/organization">Organization</Link>
        <Button asChild size="sm" className="rounded-xl bg-zinc-950 text-white hover:bg-zinc-800"><Link href="/simulate">Open simulator</Link></Button>
      </nav>
    </header>
  );
}
