import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./hooks/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0F1A14",
        panel: "#18261D",
        panel2: "#1E2F24",
        line: "#2A3A2F",
        gold: "#C49A4A",
        gold2: "#D9B26A",
        cream: "#F3EBDD",
        muted: "#9DAA9F",
        ok: "#5BD07F",
        bad: "#E0604F",
      },
      fontFamily: {
        display: ["var(--font-oswald)", "Oswald", "sans-serif"],
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
      },
      borderRadius: { xl: "16px" },
      boxShadow: { glow: "0 0 40px rgba(196,154,74,.25)" },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        pop: { "0%": { transform: "scale(.6)", opacity: "0" }, "70%": { transform: "scale(1.1)" }, "100%": { transform: "scale(1)", opacity: "1" } },
        fadeup: { "0%": { transform: "translateY(6px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        pulsegold: { "0%,100%": { boxShadow: "0 0 0 0 rgba(196,154,74,.0)" }, "50%": { boxShadow: "0 0 0 6px rgba(196,154,74,.25)" } },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
        pop: "pop .35s ease-out both",
        fadeup: "fadeup .35s ease-out both",
        pulsegold: "pulsegold 2.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
