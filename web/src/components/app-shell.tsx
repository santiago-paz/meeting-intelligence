"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { Logo } from "@/components/logo";

type Item = {
  href: string;
  label: string;
  icon: ReactNode;
  /** Whether a pathname belongs to this section, so a transcript still lights up Meetings. */
  matches: (pathname: string) => boolean;
};

const ITEMS: Item[] = [
  { href: "/", label: "Meetings", icon: <MeetingsIcon />, matches: (p) => p === "/" || p.startsWith("/meetings") },
  { href: "/ask", label: "Ask", icon: <AskIcon />, matches: (p) => p.startsWith("/ask") },
  { href: "/traces", label: "Traces", icon: <TracesIcon />, matches: (p) => p.startsWith("/traces") },
];

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sheet";

const LINK = `flex items-center gap-3 rounded-md px-3 py-2 text-[0.9375rem] font-medium text-sheet/70 transition-colors hover:bg-sheet/10 hover:text-sheet aria-[current=page]:bg-sheet/15 aria-[current=page]:text-sheet ${FOCUS}`;

/**
 * The rail: the mark, the three places to go, and nothing else. On wide screens
 * it stands beside the content; on small ones it folds into a bar and slides
 * out under it on demand, with the page inert behind it.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // The drawer remembers where it was opened, so a navigation closes it on its own.
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const open = openedAt === pathname;
  const drawerId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;
    const link = firstLinkRef.current;
    link?.focus();
    if (document.activeElement === link) return;
    // The drawer is still hidden while its slide-in starts, so focus once the slide ends.
    const drawer = drawerRef.current;
    const onEnd = () => link?.focus();
    drawer?.addEventListener("transitionend", onEnd);
    return () => drawer?.removeEventListener("transitionend", onEnd);
  }, [open]);

  function close() {
    setOpenedAt(null);
    toggleRef.current?.focus();
  }

  return (
    <div className="lg:flex lg:min-h-dvh">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between bg-ink px-4 lg:hidden">
        <Brand />
        <button
          ref={toggleRef}
          type="button"
          aria-controls={drawerId}
          aria-expanded={open}
          onClick={() => setOpenedAt(open ? null : pathname)}
          className={`-mr-2 rounded-md p-2 text-sheet/80 hover:bg-sheet/10 hover:text-sheet ${FOCUS}`}
        >
          <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
          {open ? <CloseIcon /> : <MenuIcon />}
        </button>
      </header>
      {open && (
        // Pointer users tap the dimmed page to close; keyboard users have Escape and the toggle.
        <button type="button" tabIndex={-1} aria-hidden="true" onClick={close} className="fixed inset-x-0 top-14 bottom-0 z-20 bg-ink/50 lg:hidden" />
      )}
      <aside
        ref={drawerRef}
        id={drawerId}
        data-open={open || undefined}
        onKeyDown={(event) => {
          if (event.key === "Escape") close();
        }}
        className="invisible fixed top-14 bottom-0 left-0 z-30 flex w-72 -translate-x-full flex-col overflow-y-auto overscroll-contain bg-ink px-4 py-4 text-sheet transition-[transform,visibility] duration-200 ease-out motion-reduce:transition-none data-open:visible data-open:translate-x-0 lg:visible lg:sticky lg:top-0 lg:bottom-auto lg:h-dvh lg:w-60 lg:shrink-0 lg:translate-x-0 lg:py-5"
      >
        <div className="hidden px-3 lg:block">
          <Brand />
        </div>
        <nav aria-label="Main" className="lg:mt-9">
          <ul className="flex flex-col gap-0.5">
            {ITEMS.map((item, i) => {
              const current = item.matches(pathname);
              return (
                <li key={item.href}>
                  <Link ref={i === 0 ? firstLinkRef : undefined} href={item.href} aria-current={current ? "page" : undefined} className={LINK}>
                    <span aria-hidden className="shrink-0">
                      {item.icon}
                    </span>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>
      <div className="min-w-0 flex-1" inert={open || undefined}>
        {children}
      </div>
    </div>
  );
}

function Brand() {
  return (
    <Link href="/" className={`flex items-center gap-2.5 rounded-md ${FOCUS}`}>
      <Logo className="size-7 shrink-0" />
      <span className="font-display text-[0.95rem] font-bold leading-none tracking-tight text-sheet font-stretch-semi-condensed">
        Meeting Intelligence
      </span>
    </Link>
  );
}

const ICON = "size-[18px]";
const STROKE = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function MeetingsIcon() {
  return (
    <svg viewBox="0 0 20 20" className={ICON} {...STROKE}>
      <circle cx="4" cy="5" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="4" cy="10" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="4" cy="15" r="1.4" fill="currentColor" stroke="none" />
      <path d="M8 5h9M8 10h6M8 15h8" />
    </svg>
  );
}

function AskIcon() {
  return (
    <svg viewBox="0 0 20 20" className={ICON} {...STROKE}>
      <path d="M4 3.5h12A2.5 2.5 0 0 1 18.5 6v6a2.5 2.5 0 0 1-2.5 2.5H9.5L5 17.5v-3H4A2.5 2.5 0 0 1 1.5 12V6A2.5 2.5 0 0 1 4 3.5z" />
    </svg>
  );
}

function TracesIcon() {
  return (
    <svg viewBox="0 0 20 20" className={ICON} {...STROKE}>
      <path d="M1.5 10.5h3.5l2.5-6 4 11 2.5-5h4.5" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 20 20" className="size-5" aria-hidden="true" {...STROKE}>
      <path d="M3 5.5h14M3 10h14M3 14.5h14" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" className="size-5" aria-hidden="true" {...STROKE}>
      <path d="M5 5l10 10M15 5L5 15" />
    </svg>
  );
}
