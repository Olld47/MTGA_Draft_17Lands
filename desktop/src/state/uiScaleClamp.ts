// Single source of truth for the uiScale zoom clamp. The settings layer
// (state/scale.ts) imports it directly; index.html's pre-paint script can't —
// it runs synchronously before the bundle loads — so vite.config.ts rewrites
// its bound literals from this module at every dev/build, and
// tests/test_desktop_bundle_config.py pins the source to these values.

export const UI_SCALE_MIN = 0.4;
export const UI_SCALE_MAX = 2.5;

/** Clamp a zoom factor to [UI_SCALE_MIN, UI_SCALE_MAX]; non-finite input
 *  degrades to 1 (the "restore default zoom" fallback). */
export function clampUiScale(factor: number): number {
  if (!Number.isFinite(factor)) {
    return 1;
  }
  return Math.min(Math.max(factor, UI_SCALE_MIN), UI_SCALE_MAX);
}

/** Rewrites the pre-paint script's bound literals in `index.html` to this
 *  module's values. Kept pure (no Vite import, no DOM) so the build wiring and
 *  the unit test share one code path. */
export function rewriteUiScaleBounds(html: string): string {
  return html
    .replace(/const UI_SCALE_MIN = [0-9.]+/, `const UI_SCALE_MIN = ${UI_SCALE_MIN}`)
    .replace(/const UI_SCALE_MAX = [0-9.]+/, `const UI_SCALE_MAX = ${UI_SCALE_MAX}`);
}
