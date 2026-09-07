import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto w-full max-w-3xl px-4 py-16">
      <h1 className="font-display text-2xl font-semibold tracking-tight text-balance text-ink">That meeting doesn’t exist</h1>
      <p className="mt-2 text-sm text-ink-muted">It may have been removed, or the link is wrong.</p>
      <Link href="/" className="mt-6 inline-block font-mono text-xs uppercase tracking-[0.08em] text-ink underline underline-offset-4 hover:text-marker-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
        Back to meetings
      </Link>
    </main>
  );
}
