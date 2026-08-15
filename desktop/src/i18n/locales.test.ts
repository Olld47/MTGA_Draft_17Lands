import { describe, expect, it } from "vitest";

import { messages } from "./locales";

// Every locale must carry the exact same key set — a zh key missing its en
// counterpart (or vice versa) would silently fall back through t()'s chain and
// hide a translation gap. Mutation check: delete any zh key and this fails.
describe("locales", () => {
  it("zh mirrors every en key", () => {
    const enKeys = Object.keys(messages.en).sort();
    const zhKeys = Object.keys(messages.zh).sort();
    expect(zhKeys).toEqual(enKeys);
  });

  it("en values are non-empty", () => {
    for (const [key, value] of Object.entries(messages.en)) {
      expect(value.length, key).toBeGreaterThan(0);
    }
  });
});
