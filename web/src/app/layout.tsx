import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Source_Serif_4 } from "next/font/google";

import { AppShell } from "@/components/app-shell";

import "./globals.css";

// The optical size and width axes are what give the face its character at large
// sizes and its calm at small ones; both are opt-in because they cost bytes.
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], axes: ["opsz", "wdth"], variable: "--font-bricolage" });
const sourceSerif = Source_Serif_4({ subsets: ["latin"], variable: "--font-source-serif" });

export const metadata: Metadata = {
  title: { default: "Meeting Intelligence", template: "%s · Meeting Intelligence" },
  description: "Upload meeting transcripts and read them as a timeline.",
};

export const viewport: Viewport = { themeColor: "#14213d" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${bricolage.variable} ${sourceSerif.variable} h-full antialiased`}>
      <body className="min-h-full">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-4 focus:z-40 focus:rounded-md focus:bg-sheet focus:px-3 focus:py-1.5 focus:text-sm focus:font-semibold focus:text-ink focus:outline-2 focus:outline-ink"
        >
          Skip to content
        </a>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
