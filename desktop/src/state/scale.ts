// UI scale application. Everything here is module-level on purpose: `useSettings`
// is instantiated independently by App and SettingsPage, so the side effects
// live at module scope and are called from receive()/patch() — never from a
// hook body that StrictMode could double-invoke.
import { clampUiScale } from "./uiScaleClamp";

const STORAGE_KEY = "mtga.uiScale";

/** Sets the global CSS zoom factor and mirrors it for index.html's pre-paint
 *  script. `percent` is the legacy uiSize string ("100%", "150%", ...); bare
 *  numbers and junk both degrade to a factor of 1. The clamp bounds live in
 *  state/uiScaleClamp.ts — the same module index.html's pre-paint script gets
 *  its numbers from at build time. */
export function applyUiScale(percent: string): void {
  const raw = parseFloat(percent); // "100%" -> 100, "100" -> 100, junk -> NaN
  const factor = clampUiScale(Number.isFinite(raw) ? raw / 100 : 1);
  document.documentElement.style.setProperty("--ui-scale", String(factor));
  try {
    localStorage.setItem(STORAGE_KEY, String(factor));
  } catch {
    // Private mode / disabled storage — only costs a flash on the next launch.
  }
}
