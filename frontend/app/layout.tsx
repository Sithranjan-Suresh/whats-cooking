import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { defaultTheme, themeBootScript } from "@/lib/theme-boot";
import "./globals.css";

// Bundled (SIL OFL) so builds never depend on fetching Google Fonts.
const bebas = localFont({ src: "./fonts/bebas-neue.woff2", weight: "400", variable: "--f-bebas", display: "swap" });
const courier = localFont({
  src: [
    { path: "./fonts/courier-prime-400.woff2", weight: "400" },
    { path: "./fonts/courier-prime-700.woff2", weight: "700" },
  ],
  variable: "--f-courier",
  display: "swap",
});
const alfa = localFont({ src: "./fonts/alfa-slab-one.woff2", weight: "400", variable: "--f-alfa", display: "swap" });
const caveat = localFont({ src: "./fonts/caveat.woff2", weight: "400 700", variable: "--f-caveat", display: "swap" });
const plex = localFont({
  src: [
    { path: "./fonts/plex-mono-400.woff2", weight: "400" },
    { path: "./fonts/plex-mono-600.woff2", weight: "600" },
  ],
  variable: "--f-plex",
  display: "swap",
});
const archivo = localFont({ src: "./fonts/archivo.woff2", weight: "100 900", variable: "--f-archivo", display: "swap" });

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
  themeColor: "#0B0708",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fonts = [bebas, courier, alfa, caveat, plex, archivo].map((f) => f.variable).join(" ");
  return (
    <html lang="en" data-theme={defaultTheme()} className={fonts} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript(defaultTheme()) }} />
      </head>
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
