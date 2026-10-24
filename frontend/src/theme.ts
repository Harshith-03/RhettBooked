// Theme controller: default to the OS preference, remember the session choice.

export type Theme = "light" | "dark";

const KEY = "eventtwin-theme";

export function getInitialTheme(): Theme {
  const stored = sessionStorage.getItem(KEY);
  if (stored === "light" || stored === "dark") return stored;
  const prefersDark =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export function setTheme(theme: Theme): void {
  sessionStorage.setItem(KEY, theme);
  applyTheme(theme);
}

export function usePrefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
