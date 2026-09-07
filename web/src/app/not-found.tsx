import Link from "next/link";

import { PageHeader } from "@/components/page-header";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6">
      <PageHeader title="That page doesn’t exist" lede="It may have been removed, or the link is wrong." />
      <Link
        href="/"
        className="inline-block rounded-md bg-ink px-4 py-2 text-sm font-semibold text-sheet hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        Back to meetings
      </Link>
    </main>
  );
}
