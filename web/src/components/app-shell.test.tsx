import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const route = vi.hoisted(() => ({ pathname: "/", push: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => route.pathname, useRouter: () => ({ push: route.push }) }));

import { AppShell } from "@/components/app-shell";

const fetchMock = vi.fn();

const meetings = [{ id: "abc", title: "2026-09-08-weekly-sync", created_at: "2026-09-08T10:00:00Z", turn_count: 12 }];

describe("AppShell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => meetings });
    route.pathname = "/";
    window.innerWidth = 1024;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    route.push.mockReset();
  });

  it("links to every section and marks the current one", () => {
    route.pathname = "/traces/abc";
    render(<AppShell><p>content</p></AppShell>);

    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["Meetings", "/"],
      ["Ask", "/ask"],
      ["Traces", "/traces"],
    ]);
    expect(within(nav).getByRole("link", { name: "Traces" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Meetings" })).not.toHaveAttribute("aria-current");
  });

  it("counts a transcript page as part of Meetings", () => {
    route.pathname = "/meetings/42";
    render(<AppShell><p>content</p></AppShell>);

    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Meetings" })).toHaveAttribute("aria-current", "page");
  });

  it("names the app next to the mark", () => {
    render(<AppShell><p>content</p></AppShell>);

    expect(screen.getAllByRole("link", { name: "Meeting Intelligence" }).length).toBeGreaterThan(0);
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("opens the menu on small screens as a dialog, and closes it on Escape", async () => {
    window.innerWidth = 375;
    render(<AppShell><p>content</p></AppShell>);

    const toggle = await screen.findByRole("button", { name: "Open menu" });
    await waitFor(() => expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull());

    toggle.focus();
    fireEvent.click(toggle);
    const dialog = await screen.findByRole("dialog", { name: "Sidebar" });
    const nav = within(dialog).getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Ask" })).toHaveAttribute("href", "/ask");

    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sidebar" })).toBeNull());
    expect(toggle).toHaveFocus();
  });

  it("opens the search with ⌘K and jumps to a page", async () => {
    render(<AppShell><p>content</p></AppShell>);

    fireEvent.keyDown(document, { key: "k", metaKey: true });

    const dialog = await screen.findByRole("dialog", { name: "Search" });
    fireEvent.click(within(dialog).getByRole("option", { name: "Traces" }));
    expect(route.push).toHaveBeenCalledWith("/traces");
  });

  it("lists the meetings in the search, each a jump into its transcript", async () => {
    render(<AppShell><p>content</p></AppShell>);

    fireEvent.click(screen.getByRole("button", { name: /Search/ }));

    const option = await screen.findByRole("option", { name: /weekly-sync/ });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/meetings");
    fireEvent.click(option);
    expect(route.push).toHaveBeenCalledWith("/meetings/abc");
  });

  it("says so when the meetings cannot be loaded", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    render(<AppShell><p>content</p></AppShell>);

    fireEvent.click(screen.getByRole("button", { name: /Search/ }));

    expect(await screen.findByText(/reach the server/)).toBeInTheDocument();
  });
});
