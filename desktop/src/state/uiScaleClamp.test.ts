import { describe, expect, it } from "vitest";

import {
  clampUiScale,
  rewriteUiScaleBounds,
  UI_SCALE_MAX,
  UI_SCALE_MIN,
} from "./uiScaleClamp";

describe("uiScaleClamp (the shared clamp definition)", () => {
  it("declares the legacy 40%..250% zoom bounds", () => {
    expect(UI_SCALE_MIN).toBe(0.4);
    expect(UI_SCALE_MAX).toBe(2.5);
  });

  it("passes in-range factors through unchanged", () => {
    expect(clampUiScale(0.4)).toBe(0.4);
    expect(clampUiScale(1)).toBe(1);
    expect(clampUiScale(2.5)).toBe(2.5);
  });

  it("clamps out-of-range factors to the bounds; junk degrades to 1", () => {
    expect(clampUiScale(3.0)).toBe(2.5); // ticket: stored scale above the ceiling
    expect(clampUiScale(0.1)).toBe(0.4); // ticket: stored scale below the floor
    expect(clampUiScale(0.39)).toBe(0.4);
    expect(clampUiScale(2.6)).toBe(2.5);
    expect(clampUiScale(Number.NaN)).toBe(1);
    expect(clampUiScale(Number.POSITIVE_INFINITY)).toBe(1);
    expect(clampUiScale(Number.NEGATIVE_INFINITY)).toBe(1);
  });

  it("rewrites the pre-paint script's bound literals to its own values", () => {
    const html = ["const UI_SCALE_MIN = 0.4;", "const UI_SCALE_MAX = 2.5;"].join(
      "\n",
    );
    const rewritten = rewriteUiScaleBounds(html);
    expect(rewritten).toContain(`const UI_SCALE_MIN = ${UI_SCALE_MIN};`);
    expect(rewritten).toContain(`const UI_SCALE_MAX = ${UI_SCALE_MAX};`);
  });

  it("rewrites stale literals instead of leaving them in the built html", () => {
    const stale = "const UI_SCALE_MIN = 9.9;\nconst UI_SCALE_MAX = 9.9;";
    const rewritten = rewriteUiScaleBounds(stale);
    expect(rewritten).not.toContain("9.9");
    expect(rewritten).toContain(String(UI_SCALE_MIN));
    expect(rewritten).toContain(String(UI_SCALE_MAX));
  });
});
