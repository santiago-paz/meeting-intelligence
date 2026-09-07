import type { Metadata } from "next";

import { AskPanel } from "@/components/ask-panel";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Ask" };

/** `?mode=agentic` opens the page on that mode, so a mode can be linked to. */
export default async function AskPage(props: PageProps<"/ask">) {
  const { mode } = await props.searchParams;
  const initialMode = mode === "agentic" ? "agentic" : "classic";
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <PageHeader title="Ask the meetings" lede="Every claim in the answer points at the turn it comes from." />
      <AskPanel initialMode={initialMode} />
    </main>
  );
}
