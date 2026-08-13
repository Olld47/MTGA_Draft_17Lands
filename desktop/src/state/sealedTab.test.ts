import { describe, expect, it } from "vitest";

import { isSealedEvent } from "./sealedTab";

describe("isSealedEvent", () => {
  it("accepts both Sealed variants", () => {
    expect(isSealedEvent("Sealed")).toBe(true);
    expect(isSealedEvent("TradSealed")).toBe(true);
  });

  it("rejects draft event types", () => {
    expect(isSealedEvent("PremierDraft")).toBe(false);
    expect(isSealedEvent("QuickDraft")).toBe(false);
    expect(isSealedEvent("TradDraft")).toBe(false);
    expect(isSealedEvent("PickTwoDraft")).toBe(false);
    expect(isSealedEvent("ContenderDraft")).toBe(false);
  });

  it("is false with no active draft", () => {
    expect(isSealedEvent("")).toBe(false);
    expect(isSealedEvent(null)).toBe(false);
    expect(isSealedEvent(undefined)).toBe(false);
  });
});
