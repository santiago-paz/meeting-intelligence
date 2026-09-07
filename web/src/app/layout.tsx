import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Schibsted_Grotesk, Source_Serif_4 } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const schibsted = Schibsted_Grotesk({ subsets: ["latin"], variable: "--font-schibsted" });
const sourceSerif = Source_Serif_4({ subsets: ["latin"], variable: "--font-source-serif" });
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono" });

export const metadata: Metadata = {
  title: { default: "Meeting Intelligence", template: "%s · Meeting Intelligence" },
  description: "Upload meeting transcripts and read them as a timeline.",
};

export const viewport: Viewport = { themeColor: "#edeff2" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${schibsted.variable} ${sourceSerif.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-20 focus:rounded-sm focus:bg-ink focus:px-3 focus:py-1.5 focus:font-mono focus:text-xs focus:uppercase focus:tracking-[0.08em] focus:text-sheet"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-10 border-b border-rule bg-surface/90 backdrop-blur">
          <nav className="mx-auto flex w-full max-w-6xl items-center px-4 py-3">
            <Link href="/" className="font-display text-sm font-semibold tracking-tight text-ink">
              Meeting Intelligence
            </Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
