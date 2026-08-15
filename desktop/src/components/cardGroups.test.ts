import { describe, expect, it } from "vitest";

import type { DeckRow } from "../api/types";
import {
  GROUP_OPTIONS,
  groupKey,
  groupLabel,
  groupOrder,
  type GroupBy,
} from "./cardGroups";

const row = (over: Partial<DeckRow> = {}): DeckRow => ({
  name: "X",
  count: 1,
  cmc: 0,
  types: [],
  colors: [],
  rarity: "",
  manaCost: "",
  gihwr: null,
  iwd: null,
  alsa: null,
  ata: null,
  samples: null,
  deckColors: [],
  tags: [],
  rowTag: "",
  image: [],
  ...over,
});

describe("groupKey — color", () => {
  it("sends lands to the Lands bucket first", () => {
    expect(groupKey(row({ types: ["Land"], colors: ["W"] }), "color")).toBe(
      "lands",
    );
  });
  it("buckets a colorless card by empty colors", () => {
    expect(groupKey(row({ colors: [] }), "color")).toBe("colorless");
  });
  it("buckets a gold card as Multicolor", () => {
    expect(groupKey(row({ colors: ["W", "U"] }), "color")).toBe("multi");
  });
  it("buckets a mono card by its color and unknown mono as Colorless", () => {
    expect(groupKey(row({ colors: ["B"] }), "color")).toBe("B");
    expect(groupKey(row({ colors: ["Z"] }), "color")).toBe("colorless");
  });
});

describe("groupKey — cmc", () => {
  it("separates lands and clamps non-lands at 6+", () => {
    expect(groupKey(row({ types: ["Land"] }), "cmc")).toBe("lands");
    expect(groupKey(row({ cmc: 0 }), "cmc")).toBe("0");
    expect(groupKey(row({ cmc: 5 }), "cmc")).toBe("5");
    expect(groupKey(row({ cmc: 7 }), "cmc")).toBe("6");
  });
  it("floors fractional cmc", () => {
    expect(groupKey(row({ cmc: 3.5 }), "cmc")).toBe("3");
  });
});

describe("groupKey — rarity", () => {
  it("separates basic lands from every other bucket", () => {
    expect(
      groupKey(row({ types: ["Basic", "Land"], rarity: "common" }), "rarity"),
    ).toBe("basics");
  });
  it("shares the Rare/Mythic bucket and maps unknown to Common", () => {
    expect(groupKey(row({ rarity: "rare" }), "rarity")).toBe("rare_mythic");
    expect(groupKey(row({ rarity: "mythic" }), "rarity")).toBe("rare_mythic");
    expect(groupKey(row({ rarity: "" }), "rarity")).toBe("common");
  });
  it("keeps uncommon distinct", () => {
    expect(groupKey(row({ rarity: "uncommon" }), "rarity")).toBe("uncommon");
    expect(groupKey(row({ rarity: "common" }), "rarity")).toBe("common");
  });
});

describe("groupKey — type", () => {
  it("follows the first-match-wins chain", () => {
    expect(groupKey(row({ types: ["Creature"] }), "type")).toBe("creatures");
    expect(groupKey(row({ types: ["Instant"] }), "type")).toBe(
      "instants_sorceries",
    );
    expect(groupKey(row({ types: ["Sorcery"] }), "type")).toBe(
      "instants_sorceries",
    );
    expect(groupKey(row({ types: ["Artifact"] }), "type")).toBe(
      "artifacts_enchantments",
    );
    expect(groupKey(row({ types: ["Enchantment"] }), "type")).toBe(
      "artifacts_enchantments",
    );
    expect(groupKey(row({ types: ["Planeswalker"] }), "type")).toBe(
      "planeswalkers_battles",
    );
    expect(groupKey(row({ types: ["Battle"] }), "type")).toBe(
      "planeswalkers_battles",
    );
    expect(groupKey(row({ types: ["Land"] }), "type")).toBe("lands");
    expect(groupKey(row({ types: [] }), "type")).toBe("other");
  });
  it("a Creature that is also an Artifact lands in Creatures", () => {
    expect(
      groupKey(row({ types: ["Artifact", "Creature"] }), "type"),
    ).toBe("creatures");
  });
});

describe("groupOrder", () => {
  it("exposes a canonical bucket order per mode", () => {
    expect(groupOrder("color")).toEqual([
      "W",
      "U",
      "B",
      "R",
      "G",
      "multi",
      "colorless",
      "lands",
    ]);
    expect(groupOrder("cmc")).toEqual([
      "0",
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "lands",
    ]);
    expect(groupOrder("rarity")).toEqual([
      "common",
      "uncommon",
      "rare_mythic",
      "basics",
    ]);
    expect(groupOrder("type")).toContain("other");
  });
});

describe("groupLabel", () => {
  it("sums the count field, not the number of names", () => {
    const rows = [row({ colors: ["W"], count: 2 }), row({ colors: ["W"], count: 1 })];
    expect(groupLabel("color", "W", rows)).toBe("White (3)");
  });
  it("falls back to the raw key for an unknown bucket", () => {
    expect(groupLabel("cmc", "9", [row({ count: 4 })])).toBe("9 (4)");
  });
});

describe("GROUP_OPTIONS", () => {
  it("mirrors the legacy Sort combobox choices", () => {
    expect(GROUP_OPTIONS.map((o) => o.label)).toEqual([
      "Color",
      "CMC",
      "Rarity",
      "Type",
    ]);
    expect(GROUP_OPTIONS.map((o) => o.id)).toEqual([
      "color",
      "cmc",
      "rarity",
      "type",
    ]);
    // every mode has a canonical order + labeler
    (GROUP_OPTIONS.map((o) => o.id) as GroupBy[]).forEach((g) => {
      expect(groupOrder(g).length).toBeGreaterThan(0);
      expect(groupLabel(g, groupOrder(g)[0], [row()])).toMatch(/\(1\)$/);
    });
  });
});
