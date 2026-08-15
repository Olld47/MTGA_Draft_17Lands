// Theme application. Everything here is module-level on purpose: `useSettings`
// is instantiated independently by App and SettingsPage, and React 18
// StrictMode double-invokes effects — a matchMedia listener registered from
// inside the hook would be subscribed several times over.

export type ThemePreference = "System" | "Dark" | "Light";

const STORAGE_KEY = "mtga.theme";

let preference: ThemePreference = "System";

function resolve(pref: ThemePreference): "dark" | "light" {
  if (pref === "Dark") return "dark";
  if (pref === "Light") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/** Sets the palette and mirrors it for index.html's pre-paint script. */
export function applyTheme(pref: ThemePreference): void {
  preference = pref;
  const resolved = resolve(pref);
  document.documentElement.dataset.theme = resolved;
  try {
    localStorage.setItem(STORAGE_KEY, resolved);
  } catch {
    // Private mode / disabled storage — only costs a flash on the next launch.
  }
}

window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => {
    if (preference === "System") applyTheme("System");
  });
