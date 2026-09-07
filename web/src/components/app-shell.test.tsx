import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const route = vi.hoisted(() => ({ pathname: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => route.pathname }));

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
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
    route.pathname = "/";
    render(<AppShell><p>content</p></AppShell>);

    expect(screen.getAllByRole("link", { name: "Meeting Intelligence" }).length).toBeGreaterThan(0);
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("opens the menu on small screens, keeps the page inert behind it, and closes on Escape", () => {
    route.pathname = "/";
    render(<AppShell><p>content</p></AppShell>);

    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("content").parentElement).not.toHaveAttribute("inert");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Close menu" })).toBe(toggle);
    expect(screen.getByText("content").parentElement).toHaveAttribute("inert");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Meetings" })).toHaveFocus();

    fireEvent.keyDown(nav, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
    expect(screen.getByText("content").parentElement).not.toHaveAttribute("inert");
  });
});
