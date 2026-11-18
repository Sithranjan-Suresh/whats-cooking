import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

// Every color is a CSS variable (space-separated RGB) defined per theme in app/globals.css,
// so the same class names re-skin between the "studio" and "kitchen" themes.
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./hooks/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        panel: v("panel"),
        panel2: v("panel2"),
        line: v("line"),
        gold: v("gold"),
        gold2: v("gold2"),
        cream: v("cream"),
        muted: v("muted"),
        ember: v("ember"),
        ok: v("ok"),
        bad: v("bad"),
        ongold: v("ongold"),
        paper: v("paper"),
        ink: v("ink"),
        chalk: v("chalk"),
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
        hand: ["var(--font-hand)", "cursive"],
      },
      borderRadius: { xl: "var(--radius)" },
      boxShadow: {
        glow: "0 0 60px rgb(var(--gold) / .28)",
        lift: "0 18px 50px -20px rgb(0 0 0 / .8)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        pop: { "0%": { transform: "scale(.6)", opacity: "0" }, "70%": { transform: "scale(1.12)" }, "100%": { transform: "scale(1)", opacity: "1" } },
        fadeup: { "0%": { transform: "translateY(8px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        flicker: { "0%,100%": { opacity: "1" }, "41%": { opacity: "1" }, "42%": { opacity: ".55" }, "43%": { opacity: "1" }, "78%": { opacity: ".9" } },
        grain: {
          "0%,100%": { transform: "translate(0,0)" },
          "20%": { transform: "translate(-3%,2%)" },
          "40%": { transform: "translate(2%,-3%)" },
          "60%": { transform: "translate(-2%,-1%)" },
          "80%": { transform: "translate(3%,3%)" },
        },
        flame: { "0%,100%": { transform: "scaleY(1) translateY(0)" }, "50%": { transform: "scaleY(1.18) translateY(-2px)" } },
        steam: { "0%": { transform: "translateY(6px) scaleX(1)", opacity: "0" }, "40%": { opacity: ".55" }, "100%": { transform: "translateY(-26px) scaleX(1.4)", opacity: "0" } },
        swing: { "0%,100%": { transform: "rotate(-1.2deg)" }, "50%": { transform: "rotate(1.2deg)" } },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
        pop: "pop .35s ease-out both",
        fadeup: "fadeup .45s cubic-bezier(.2,.7,.2,1) both",
        flicker: "flicker 4s infinite",
        grain: "grain .9s steps(4) infinite",
        flame: "flame .35s ease-in-out infinite",
        steam: "steam 2.6s ease-out infinite",
        swing: "swing 5s ease-in-out infinite",
      },
    },
  },
  plugins: [
    plugin(({ addVariant }) => {
      addVariant("studio", '[data-theme="studio"] &');
      addVariant("kitchen", '[data-theme="kitchen"] &');
    }),
  ],
};
export default config;
