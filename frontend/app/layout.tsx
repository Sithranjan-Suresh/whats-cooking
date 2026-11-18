import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Bundled (SIL OFL) so builds never depend on fetching Google Fonts.
const oswald = localFont({ src: "./fonts/oswald.woff2", weight: "200 700", variable: "--font-oswald", display: "swap" });
const inter = localFont({ src: "./fonts/inter.woff2", weight: "100 900", variable: "--font-inter", display: "swap" });
const mono = localFont({ src: "./fonts/jetbrains-mono.woff2", weight: "100 800", variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "What's Cooking?",
  description: "Turn a restaurant's dish photos and sales data into published YouTube Shorts in about a minute.",
  openGraph: {
    title: "What's Cooking?",
    description: "Dish photo or sales data in, published YouTube Short out. No editing, capped cost.",
    type: "website",
  },
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#0F1A14",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${oswald.variable} ${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-bg font-sans text-cream">{children}</body>
    </html>
  );
}
