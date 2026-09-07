"use client";

import { Activity, FileText, MessageSquare, PanelLeft, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { MeetingSummary } from "@/lib/api";

type Item = {
  href: string;
  label: string;
  icon: ReactNode;
  /** Whether a pathname belongs to this section, so a transcript still lights up Meetings. */
  matches: (pathname: string) => boolean;
};

/** The places to go: the work (transcripts and questions), then the ledger of what the model did. */
const WORK: Item[] = [
  { href: "/", label: "Meetings", icon: <FileText />, matches: (p) => p === "/" || p.startsWith("/meetings") },
  { href: "/ask", label: "Ask", icon: <MessageSquare />, matches: (p) => p.startsWith("/ask") },
];
const MONITOR: Item[] = [{ href: "/traces", label: "Traces", icon: <Activity />, matches: (p) => p.startsWith("/traces") }];
const ITEMS = [...WORK, ...MONITOR];

/**
 * The frame every page sits in: a header with the mark and the search, and a
 * sidebar with the places to go. On wide screens the sidebar stands beside
 * the content and folds down to its icons; on small ones it is a drawer
 * under the header's menu button.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider>
      <SidebarProvider className="flex-col [--header-height:3.5rem]">
        <SiteHeader />
        <div className="flex flex-1">
          <AppSidebar />
          <div className="relative flex w-full min-w-0 flex-1 flex-col">{children}</div>
        </div>
      </SidebarProvider>
    </TooltipProvider>
  );
}

function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 grid h-(--header-height) grid-cols-[1fr_auto_1fr] items-center gap-3 border-b bg-header px-3 sm:px-4">
      <div className="flex min-w-0 items-center gap-1.5">
        <MenuButton />
        <Brand />
      </div>
      <SearchMenu />
      <div aria-hidden="true" />
    </header>
  );
}

function Brand() {
  return (
    <Link
      href="/"
      className="flex min-w-0 items-center gap-2.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
    >
      <Logo className="size-7 shrink-0" />
      <span className="truncate text-[0.9375rem] font-semibold tracking-tight">Meeting Intelligence</span>
    </Link>
  );
}

/** Opens the drawer on small screens; on wide ones the sidebar is always there and this is hidden. */
function MenuButton() {
  const { openMobile, setOpenMobile } = useSidebar();
  return (
    <Button variant="ghost" size="icon-sm" aria-expanded={openMobile} onClick={() => setOpenMobile(true)} className="md:hidden">
      <PanelLeft />
      <span className="sr-only">Open menu</span>
    </Button>
  );
}

function AppSidebar() {
  const pathname = usePathname();
  const { isMobile, setOpenMobile, toggleSidebar, state } = useSidebar();
  const collapsed = state === "collapsed";

  return (
    <Sidebar collapsible="icon" className="top-(--header-height) h-[calc(100svh-var(--header-height))]!">
      {isMobile && (
        <SidebarHeader className="flex-row items-center justify-between px-3 py-2.5">
          <Brand />
          <Button variant="ghost" size="icon-sm" onClick={() => setOpenMobile(false)}>
            <X />
            <span className="sr-only">Close menu</span>
          </Button>
        </SidebarHeader>
      )}
      <SidebarContent>
        <nav aria-label="Main" className="flex flex-col">
          <SidebarGroup>
            <SidebarGroupContent>
              <NavMenu items={WORK} pathname={pathname} />
            </SidebarGroupContent>
          </SidebarGroup>
          <SidebarGroup>
            <SidebarGroupLabel className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-sidebar-foreground/60">
              Monitor
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <NavMenu items={MONITOR} pathname={pathname} />
            </SidebarGroupContent>
          </SidebarGroup>
        </nav>
      </SidebarContent>
      {!isMobile && (
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={toggleSidebar} tooltip="Expand sidebar" className="text-sidebar-foreground/70">
                <PanelLeft />
                <span>{collapsed ? "Expand sidebar" : "Collapse sidebar"}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      )}
      <SidebarRail />
    </Sidebar>
  );
}

function NavMenu({ items, pathname }: { items: Item[]; pathname: string }) {
  const { setOpenMobile } = useSidebar();
  return (
    <SidebarMenu>
      {items.map((item) => {
        const current = item.matches(pathname);
        return (
          <SidebarMenuItem key={item.href}>
            <SidebarMenuButton
              asChild
              isActive={current}
              tooltip={item.label}
              className="data-active:bg-sidebar-active data-active:text-sidebar-accent-foreground"
            >
              {/* The drawer closes on its own when a place is picked. */}
              <Link href={item.href} aria-current={current ? "page" : undefined} onClick={() => setOpenMobile(false)}>
                {item.icon}
                <span>{item.label}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        );
      })}
    </SidebarMenu>
  );
}

type Meetings = MeetingSummary[] | "loading" | "failed";

/** The search in the header: ⌘K opens it, and it jumps to a page or into a meeting's transcript. */
function SearchMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [meetings, setMeetings] = useState<Meetings>("loading");

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  // The meeting list is fetched when the search opens, so the header costs nothing on every page.
  useEffect(() => {
    if (!open) return;
    let stale = false;
    fetch("/api/meetings")
      .then((response) => (response.ok ? (response.json() as Promise<MeetingSummary[]>) : Promise.reject(new Error(String(response.status)))))
      .then((list) => {
        if (!stale) setMeetings(list);
      })
      .catch(() => {
        if (!stale) setMeetings("failed");
      });
    return () => {
      stale = true;
    };
  }, [open]);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <>
      <Button
        variant="outline"
        onClick={() => setOpen(true)}
        className="h-8 w-[clamp(2rem,40vw,28rem)] justify-start gap-2 px-2 font-normal text-muted-foreground max-sm:w-8 max-sm:justify-center max-sm:px-0"
      >
        <Search />
        <span className="flex-1 truncate text-left max-sm:sr-only">Search or jump to…</span>
        <KbdGroup className="max-sm:hidden">
          <Kbd>⌘</Kbd>
          <Kbd>K</Kbd>
        </KbdGroup>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Jump to a page or a meeting.">
        <Command>
          <CommandInput placeholder="Type a page or a meeting…" />
          <CommandList>
            <CommandEmpty>Nothing here by that name.</CommandEmpty>
            <CommandGroup heading="Pages">
              {ITEMS.map((item) => (
                <CommandItem key={item.href} value={item.label} onSelect={() => go(item.href)}>
                  {item.icon}
                  {item.label}
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandGroup heading="Meetings">
              {meetings === "loading" ? (
                <CommandItem disabled value="loading">
                  Loading the meetings…
                </CommandItem>
              ) : meetings === "failed" ? (
                <CommandItem disabled value="failed">
                  Couldn’t reach the server. Is it running?
                </CommandItem>
              ) : meetings.length === 0 ? (
                <CommandItem disabled value="none">
                  No meetings yet.
                </CommandItem>
              ) : (
                meetings.map((meeting) => (
                  <CommandItem key={meeting.id} value={`meeting ${meeting.title}`} onSelect={() => go(`/meetings/${meeting.id}`)}>
                    <FileText />
                    <span className="truncate">{meeting.title}</span>
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{meeting.turn_count} turns</span>
                  </CommandItem>
                ))
              )}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
