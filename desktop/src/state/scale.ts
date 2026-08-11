// UI scale application. Everything here is module-level on purpose: `useSettings`
// is instantiated independently by App and SettingsPage, so the side effects
// live at module scope and are called from receive()/patch() — never from a
// hook body that StrictMode could double-invoke.

const STORAGE_KEY = "mtga.uiScale";

/** Sets the global CSS zoom factor and mirrors it for index.html's pre-paint
 *  script. `percent` is the legacy uiSize string ("100%", "150%", ...); bare
 *  numbers and junk both degrade to a factor of 1. */
export function applyUiScale(percent: string): void {
  const raw = parseFloat(percent); // "100%" -> 100, "100" -> 100, junk -> NaN
  let factor = Number.isFinite(raw) ? raw / 100 : 1;
  if (!(factor >= 0.4 && factor <= 2.5)) factor = 1;
  document.documentElement.style.setProperty("--ui-scale", String(factor));
  try {
    localStorage.setItem(STORAGE_KEY, String(factor));
  } catch {
    // Private mode / disabled storage — only costs a flash on the next launch.
  }
}
