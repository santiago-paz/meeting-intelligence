import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

/** The top of a page: an optional breadcrumb line, the title with an optional tag beside it, then a lede or a line of figures. */
export function PageHeader({
  crumb,
  title,
  badge,
  lede,
  meta,
}: {
  crumb?: ReactNode;
  title: ReactNode;
  badge?: ReactNode;
  lede?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="mb-6 sm:mb-8">
      {crumb && <p className="eyebrow mb-3 text-muted-foreground">{crumb}</p>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-[1.625rem] leading-tight font-semibold tracking-tight text-balance break-words sm:text-[1.875rem]">{title}</h1>
        {badge && (
          <Badge variant="secondary" className="h-6 rounded-md px-2 text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-muted-foreground">
            {badge}
          </Badge>
        )}
      </div>
      {lede && <p className="mt-2 max-w-[60ch] text-sm leading-relaxed text-muted-foreground">{lede}</p>}
      {meta && <p className="mt-1.5 text-xs tabular-nums text-muted-foreground">{meta}</p>}
    </header>
  );
}
