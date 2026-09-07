import type { ReactNode } from "react";

/** The top of a page: an optional breadcrumb line, the title, then a lede or a line of figures. */
export function PageHeader({ crumb, title, lede, meta }: { crumb?: ReactNode; title: ReactNode; lede?: ReactNode; meta?: ReactNode }) {
  return (
    <header className="mb-8">
      {crumb && <p className="eyebrow mb-2 text-ink-muted">{crumb}</p>}
      <h1 className="font-display text-[1.75rem] leading-[1.1] font-bold tracking-tight text-balance break-words text-ink sm:text-[2.125rem]">
        {title}
      </h1>
      {lede && <p className="mt-2.5 max-w-[60ch] text-[0.95rem] leading-relaxed text-ink-muted">{lede}</p>}
      {meta && <p className="mt-2 text-xs tabular-nums text-ink-muted">{meta}</p>}
    </header>
  );
}
