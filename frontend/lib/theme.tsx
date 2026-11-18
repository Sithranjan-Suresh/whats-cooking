"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Angle, StageName } from "./types";


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

export const COPY: { studio: Copy } = {
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
};

// ---------------------------------------------------------------- context

type Ctx = { t: Copy; sound: boolean; setSound: (v: boolean) => void };
const ThemeCtx = createContext<Ctx>({ t: COPY.studio, sound: true, setSound: () => {} });
export const useTheme = () => useContext(ThemeCtx);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [sound, setSoundState] = useState(true);
  useEffect(() => {
    try {
      setSoundState(localStorage.getItem("wc_sound") !== "off");
    } catch {
      /* ignore */
    }
  }, []);
  const setSound = useCallback((v: boolean) => {
    setSoundState(v);
    try {
      localStorage.setItem("wc_sound", v ? "on" : "off");
    } catch {
      /* ignore */
    }
  }, []);
  return <ThemeCtx.Provider value={{ t: COPY.studio, sound, setSound }}>{children}</ThemeCtx.Provider>;
}
