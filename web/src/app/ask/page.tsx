import type { Metadata } from "next";

import { AskPanel } from "@/components/ask-panel";

export const metadata: Metadata = { title: "Ask" };

/** `?mode=agentic` opens the page on that mode, so a mode can be linked to. */
export default async function AskPage(props: PageProps<"/ask">) {
  const { mode } = await props.searchParams;
  const initialMode = mode === "agentic" ? "agentic" : "classic";
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-12">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-balance text-ink">Ask the meetings</h1>
        <p className="mt-1 text-sm text-ink-muted">Every claim in the answer points at the turn it comes from.</p>
      </header>
      <AskPanel initialMode={initialMode} />
    </main>
  );
}
