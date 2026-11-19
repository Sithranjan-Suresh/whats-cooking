"use client";
// App-wide copy for the Hollywood look ("Every dish is a star") + the sound-effects on/off setting.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

const COPY = {
  studio: {
    generate: "Action!",
    generating: "Rolling…",
    working: "Rolling",
    ready: "That's a wrap",
    placeholder: "Your Short premieres here",
  },
  library: { live: "Now showing on YouTube" },
};

type Ctx = { t: typeof COPY; sound: boolean; setSound: (v: boolean) => void };
const ThemeCtx = createContext<Ctx>({ t: COPY, sound: true, setSound: () => {} });
export const useTheme = () => useContext(ThemeCtx);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [sound, setSoundState] = useState(true);
  useEffect(() => {
    try {
      setSoundState(localStorage.getItem("wc_sound") !== "off");
    } catch {
      /* storage blocked: keep the default */
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
  return <ThemeCtx.Provider value={{ t: COPY, sound, setSound }}>{children}</ThemeCtx.Provider>;
}
