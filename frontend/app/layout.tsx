import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
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
const archivo = localFont({ src: "./fonts/archivo.woff2", weight: "100 900", variable: "--f-archivo", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL("https://whats-cooking-jade.vercel.app"),
  title: "What's Cooking?",
  description: "Turn one dish photo, or your sales data, into a narrated 8-second YouTube Short in a couple of minutes. No editing.",
  openGraph: {
    title: "What's Cooking?",
    description: "One dish photo in, a narrated 8-second YouTube Short out. No editing, no login.",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "What's Cooking? turns a dish photo into a YouTube Short" }],
  },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#0B0708",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fonts = [bebas, courier, archivo].map((f) => f.variable).join(" ");
  return (
    <html lang="en" data-theme="studio" className={fonts}>
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
