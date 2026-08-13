import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { applyUiScale } from "./scale";

// The pre-paint script lives inline in index.html's <head>, so the only way to
// test the first-paint path is to run the shipped source exactly as shipped.
// vitest runs with cwd = desktop/, so resolve() lands on the project index.html.
const INDEX_HTML = resolve("index.html");

function prePaintScript(): string {
  const html = readFileSync(INDEX_HTML, "utf8");
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!match) throw new Error("no inline pre-paint <script> in index.html");
  return match[1];
}

function uiScale(): string {
  return document.documentElement.style.getPropertyValue("--ui-scale");
}

/** Runs the pre-paint script against a live document with the given stored
 *  scale already in localStorage, and returns the zoom it painted. */
function firstPaint(stored: string): string {
  localStorage.setItem("mtga.uiScale", stored);
  new Function(prePaintScript())();
  return uiScale();
}

afterEach(() => {
  document.documentElement.style.removeProperty("--ui-scale");
  localStorage.removeItem("mtga.uiScale");
});

describe("index.html pre-paint script (first paint)", () => {
  it("clamps a stored scale exactly like the settings layer does", () => {
    // (stored factor, equivalent uiSize percent string) — every one of the
    // ticket's corrupted/legacy cases plus the clamp boundaries.
    const cases: Array<[stored: string, percent: string]> = [
      ["3", "300%"], // above the ceiling
      ["0.1", "10%"], // below the floor
      ["banana", "banana"], // junk
      ["0.39", "39%"], // just below the floor
      ["2.6", "260%"], // just above the ceiling
      ["0.4", "40%"], // floor
      ["2.5", "250%"], // ceiling
      ["1", "100%"],
    ];
    for (const [stored, percent] of cases) {
      const atFirstPaint = firstPaint(stored);
      applyUiScale(percent); // the settings-load path
      expect(atFirstPaint).toBe(uiScale());
    }
  });

  it("paints the clamped factor for out-of-range stored values, 1 for junk", () => {
    expect(firstPaint("3")).toBe("2.5");
    expect(firstPaint("0.1")).toBe("0.4");
    expect(firstPaint("banana")).toBe("1");
  });

  it("keeps in-range stored factors", () => {
    expect(firstPaint("0.4")).toBe("0.4");
    expect(firstPaint("2.5")).toBe("2.5");
    expect(firstPaint("1")).toBe("1");
  });
});
