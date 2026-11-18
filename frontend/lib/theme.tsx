"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Angle, StageName } from "./types";

import { defaultTheme, THEME_KEY as KEY, type ThemeName } from "./theme-boot";
export type { ThemeName };
export const THEMES: ThemeName[] = ["studio", "kitchen"];

// ---------------------------------------------------------------- copy

type Copy = {
  brandTag: string;
  nav: { insights: string; studio: string; library: string; settings: string; settingsShort: string };
  insights: { title: string; eyebrow: string; sub: (rows: string, range: string) => string; empty: string; cta: string; refresh: string };
  angle: Record<Angle, { label: string; cta: string; badge: string }>;
  studio: {
    title: string; eyebrow: string; sub: string; generate: string; generating: string; again: string;
    tabs: { photo: string; insight: string; menu: string }; veo: string; veoOn: string; scriptTitle: string;
    voiceover: string; working: string; ready: string; placeholder: string;
  };
  stages: Record<StageName, { title: string; sub: string }>;
  library: { title: string; eyebrow: string; sub: (n: number) => string; empty: string; emptyBody: string; publish: string; published: string; publishing: string; live: string };
  settings: { title: string; eyebrow: string; sub: string; budget: string; freeMode: string; freeModeSub: string; brand: string; youtube: string; perVideo: (c: string) => string };
  toast: { done: string; failed: string; publishing: string };
};

export const COPY: Record<ThemeName, Copy> = {
  studio: {
    brandTag: "Every dish is a star",
    nav: { insights: "Casting", studio: "On Set", library: "Screening Room", settings: "Production Office", settingsShort: "Office" },
    insights: {
      title: "Casting",
      eyebrow: "Auditions · this week",
      sub: (rows, range) => `${rows} orders auditioned your menu · ${range}`,
      empty: "No auditions yet",
      cta: "Cast as lead",
      refresh: "Re-run auditions",
    },
    angle: {
      rising: { label: "Rising star", cta: "Cast as lead", badge: "Breakout" },
      top_seller: { label: "Box-office hit", cta: "Cast as lead", badge: "Headliner" },
      slow_mover: { label: "Hidden talent", cta: "Give it a shot", badge: "Undiscovered" },
    },
    studio: {
      title: "On Set",
      eyebrow: "One dish · one Short",
      sub: "Pick your star, set the scene, call action.",
      generate: "Action!",
      generating: "Rolling…",
      again: "New take",
      tabs: { photo: "Headshot", insight: "From casting", menu: "From the menu" },
      veo: "Real motion (Veo)",
      veoOn: "Turns the still into 8 seconds of real motion. Falls back to free camera work automatically.",
      scriptTitle: "Screenplay",
      voiceover: "Narrator (V.O.)",
      working: "Rolling",
      ready: "That's a wrap",
      placeholder: "Your Short premieres here",
    },
    stages: {
      analyze: { title: "Read-through", sub: "Reads the dish against your menu" },
      script: { title: "Script", sub: "Hook, captions and lines from the menu" },
      visuals: { title: "Lights · Camera", sub: "AI motion or Ken Burns camera" },
      voice: { title: "Voice", sub: "The narrator records" },
      assemble: { title: "Final Cut", sub: "Titles, score and end card" },
    },
    library: {
      title: "Screening Room",
      eyebrow: "Now showing",
      sub: (n) => `${n} feature${n === 1 ? "" : "s"} in the vault`,
      empty: "The screen is dark",
      emptyBody: "Shoot your first Short on set. It premieres here.",
      publish: "Premiere on YouTube",
      published: "Now showing",
      publishing: "Rolling out the carpet",
      live: "Now showing on YouTube",
    },
    settings: {
      title: "Production Office",
      eyebrow: "Budget · brand · distribution",
      sub: "Every film on-brand, every dollar accounted for.",
      budget: "Production budget",
      freeMode: "Indie mode",
      freeModeSub: "No Veo. Every film is shot on the free camera rig for $0.",
      brand: "Studio logo & titles",
      youtube: "Distribution",
      perVideo: (c) => `This film cost ${c} to make`,
    },
    toast: { done: "That's a wrap. Your Short is ready.", failed: "Cut! The take failed.", publishing: "Premiere started" },
  },
  kitchen: {
    brandTag: "Order up!",
    nav: { insights: "Specials", studio: "The Line", library: "The Pass", settings: "Back Office", settingsShort: "Office" },
    insights: {
      title: "What to push tonight",
      eyebrow: "Chalked from your sales",
      sub: (rows, range) => `${rows} tickets read · ${range}`,
      empty: "Board's blank",
      cta: "Fire it",
      refresh: "Re-chalk the board",
    },
    angle: {
      rising: { label: "On fire", cta: "Fire it", badge: "Hot" },
      top_seller: { label: "House favorite", cta: "Fire it", badge: "#1" },
      slow_mover: { label: "Chef's pick", cta: "Push it", badge: "Sleeper" },
    },
    studio: {
      title: "The Line",
      eyebrow: "One ticket · one Short",
      sub: "Put the ticket in. Fire. Plate it.",
      generate: "Fire!",
      generating: "On the line…",
      again: "New ticket",
      tabs: { photo: "Snap a plate", insight: "From specials", menu: "From the menu" },
      veo: "Live motion (Veo)",
      veoOn: "Turns the plate photo into 8 seconds of real motion. If Veo can't, the line keeps cooking for free.",
      scriptTitle: "The ticket",
      voiceover: "Expo call-out",
      working: "Cooking",
      ready: "Order up!",
      placeholder: "Plates up here",
    },
    stages: {
      analyze: { title: "Prep", sub: "Reads the plate against your menu" },
      script: { title: "Cook", sub: "Hook, captions and call-out from the menu" },
      visuals: { title: "Plate", sub: "AI motion or slow pan" },
      voice: { title: "Garnish", sub: "Voiceover on top" },
      assemble: { title: "Serve", sub: "Captions, music, end card" },
    },
    library: {
      title: "The Pass",
      eyebrow: "Under the heat lamps",
      sub: (n) => `${n} plate${n === 1 ? "" : "s"} up`,
      empty: "Nothing on the pass",
      emptyBody: "Fire your first ticket on the line. It lands here, ready to run.",
      publish: "Run it to YouTube",
      published: "Served",
      publishing: "Running it out",
      live: "Served on YouTube",
    },
    settings: {
      title: "Back Office",
      eyebrow: "The bill · the house style · delivery",
      sub: "Every plate on-brand, every dollar on the receipt.",
      budget: "The bill",
      freeMode: "Staff meal mode",
      freeModeSub: "No Veo. Every plate uses the free camera, $0 on the bill.",
      brand: "House style",
      youtube: "Delivery",
      perVideo: (c) => `This plate cost ${c}`,
    },
    toast: { done: "Order up! Your Short is ready.", failed: "86'd. That ticket failed.", publishing: "Running it to YouTube" },
  },
};

// ---------------------------------------------------------------- context

type Ctx = { theme: ThemeName; setTheme: (t: ThemeName) => void; t: Copy; sound: boolean; setSound: (v: boolean) => void };
const ThemeCtx = createContext<Ctx>({ theme: "studio", setTheme: () => {}, t: COPY.studio, sound: true, setSound: () => {} });
export const useTheme = () => useContext(ThemeCtx);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(defaultTheme());
  const [sound, setSoundState] = useState(true);
  useEffect(() => {
    const cur = document.documentElement.dataset.theme;
    if (cur === "studio" || cur === "kitchen") setThemeState(cur);
    try {
      setSoundState(localStorage.getItem("wc_sound") !== "off");
    } catch {
      /* ignore */
    }
  }, []);
  const setTheme = useCallback((t: ThemeName) => {
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* ignore */
    }
    setThemeState(t);
  }, []);
  const setSound = useCallback((v: boolean) => {
    setSoundState(v);
    try {
      localStorage.setItem("wc_sound", v ? "on" : "off");
    } catch {
      /* ignore */
    }
  }, []);
  return <ThemeCtx.Provider value={{ theme, setTheme, t: COPY[theme], sound, setSound }}>{children}</ThemeCtx.Provider>;
}
