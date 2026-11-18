// Server-safe theme helpers (no "use client"): used by the root layout before first paint.
export type ThemeName = "studio" | "kitchen";
export const THEME_KEY = "wc_theme";

export function defaultTheme(): ThemeName {
  return process.env.NEXT_PUBLIC_THEME === "kitchen" ? "kitchen" : "studio";
}

/** Sets data-theme from ?theme=, then localStorage, then the default (no flash of the wrong theme). */
export function themeBootScript(def: ThemeName): string {
  return `(function(){try{var q=new URLSearchParams(location.search).get('theme');var s=q||localStorage.getItem('${THEME_KEY}')||'${def}';if(s!=='studio'&&s!=='kitchen')s='${def}';if(q==='studio'||q==='kitchen')localStorage.setItem('${THEME_KEY}',q);document.documentElement.dataset.theme=s;}catch(e){document.documentElement.dataset.theme='${def}';}})();`;
}
