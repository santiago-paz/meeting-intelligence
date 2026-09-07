import type { Metadata } from "next";

import { AskPanel } from "@/components/ask-panel";
import { PageHeader } from "@/components/page-header";
import { getTestModeStatus } from "@/lib/api";

export const metadata: Metadata = { title: "Ask" };

// Whether test mode is on by default depends on the API's key, read per request.
export const dynamic = "force-dynamic";

/** `?mode=agentic` opens the page on that mode, so a mode can be linked to. */
export default async function AskPage(props: PageProps<"/ask">) {
  const [{ mode }, testMode] = await Promise.all([
    props.searchParams,
    // Without the API there is nothing to replay; the form says so if the switch is turned on.
    getTestModeStatus().catch(() => null),
  ]);
  const initialMode = mode === "agentic" ? "agentic" : "classic";
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader title="Ask the meetings" lede="Every claim in the answer points at the turn it comes from." />
      <AskPanel initialMode={initialMode} testMode={testMode} />
    </main>
  );
}
