import { afterEach, describe, expect, it } from "vitest";

import { applyUiScale } from "./scale";

function uiScale(): string {
  return document.documentElement.style.getPropertyValue("--ui-scale");
}

afterEach(() => {
  // The store module keeps no state, but the CSS var and its localStorage
  // mirror persist on the DOM across tests — reset both so "never called"
  // below can't be polluted by an earlier assertion.
  document.documentElement.style.removeProperty("--ui-scale");
  localStorage.removeItem("mtga.uiScale");
});

describe("applyUiScale", () => {
  it("maps a legacy percent string to the CSS zoom factor", () => {
    applyUiScale("150%");
    expect(uiScale()).toBe("1.5");
  });

  it("accepts a bare number (the legacy test-fixture form)", () => {
    applyUiScale("100");
    expect(uiScale()).toBe("1");
  });

  it("degrades junk and empty strings to factor 1", () => {
    applyUiScale("banana");
    expect(uiScale()).toBe("1");
    applyUiScale("");
    expect(uiScale()).toBe("1");
  });

  it("accepts the legacy scale bounds and clamps beyond them", () => {
    applyUiScale("40%"); // floor of the legacy UI_SIZE_DICT scale
    expect(uiScale()).toBe("0.4");
    applyUiScale("250%"); // ceiling
    expect(uiScale()).toBe("2.5");
    applyUiScale("30%"); // below the floor
    expect(uiScale()).toBe("1");
    applyUiScale("400%"); // above the ceiling
    expect(uiScale()).toBe("1");
  });

  it("leaves the var untouched when never called", () => {
    expect(uiScale()).toBe("");
  });

  it("mirrors the factor to localStorage for index.html's pre-paint script", () => {
    applyUiScale("200%");
    expect(localStorage.getItem("mtga.uiScale")).toBe("2");
  });
});
