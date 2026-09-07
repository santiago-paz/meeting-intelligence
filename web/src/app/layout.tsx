import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppShell } from "@/components/app-shell";

import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: { default: "Meeting Intelligence", template: "%s · Meeting Intelligence" },
  description: "Upload meeting transcripts and read them as a timeline.",
};

export const viewport: Viewport = { themeColor: "#0e0f10" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The app is dark only; the class is what turns on the components' dark styles.
    <html lang="en" className={`dark h-full antialiased ${geist.variable} ${geistMono.variable}`}>
      <body className="min-h-full">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-1.5 focus:text-sm focus:font-semibold focus:text-foreground focus:outline-2 focus:outline-ring"
        >
          Skip to content
        </a>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
