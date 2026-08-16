import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import type { Card, SetMetrics } from "../api/types";
import { messages, type Lang } from "../i18n/locales";
import {
  artUrl,
  cardColumn,
  cardNameColor,
  cardRowClass,
  formatWinRate,
  nameColumn,
  RESULT_FORMAT_GRADE,
  RESULT_FORMAT_RATING,
  tagChip,
} from "./cardColumns";

/** Language-bound translator mirroring useLanguage().t's fallback chain. */
const lookup = (lang: Lang) => (key: string) =>
  messages[lang][key] ?? messages.en[key] ?? key;

const card = (over: Partial<Card> = {}): Card => ({
  name: "Grizzly Bears",
  manaCost: "{1}{G}",
  cmc: 2,
  colors: ["G"],
  types: ["Creature"],
  rarity: "common",
  image: ["/static/img/cards/grizzly-bears.jpg"],
  count: 1,
  stats: {
    gihwr: null,
    ohwr: null,
    gpwr: null,
    alsa: null,
    ata: null,
    iwd: null,
    gih: null,
    ngp: null,
  },
  recommendation: null,
  isPicked: false,
  returnableAt: [],
  tier: null,
  deckColors: [],
  ...over,
});

const withMetrics = (
  std = 3,
  mean = 55,
): SetMetrics => ({
  hasData: true,
  metrics: {
    gihwr: { G: { mean, std }, W: { mean, std } },
    ohwr: {},
    gpwr: {},
  },
});

describe("formatWinRate", () => {
  it("dashes a missing value and renders zero as a bare dash", () => {
    expect(formatWinRate(null, ["W"], "gihwr", "Percentage", withMetrics())).toBe("—");
    expect(formatWinRate(0, ["W"], "gihwr", "Percentage", withMetrics())).toBe("-");
  });
  it("returns the raw percentage for Percentage format or missing metrics", () => {
    expect(formatWinRate(57.25, ["G"], "gihwr", "Percentage", withMetrics())).toBe(
      "57.3",
    );
    const noData: SetMetrics = { hasData: false, metrics: {} };
    expect(formatWinRate(57.25, ["G"], "gihwr", RESULT_FORMAT_GRADE, noData)).toBe(
      "57.3",
    );
  });
  it("ignores non-win-rate fields even in Grade/Rating format", () => {
    expect(
      formatWinRate(4.2, ["G"], "alsa", RESULT_FORMAT_GRADE, withMetrics()),
    ).toBe("4.2");
  });
  it("falls back to percentage when the color has no metrics or zero std", () => {
    const empty: SetMetrics = {
      hasData: true,
      metrics: { gihwr: {}, ohwr: {}, gpwr: {} },
    };
    expect(formatWinRate(57, ["G"], "gihwr", RESULT_FORMAT_GRADE, empty)).toBe(
      "57.0",
    );
    const zeroStd = withMetrics(0);
    expect(formatWinRate(57, ["G"], "gihwr", RESULT_FORMAT_GRADE, zeroStd)).toBe(
      "57.0",
    );
  });
  it("derives a grade from the z-score (61 → A+, 52 → D+)", () => {
    expect(formatWinRate(61, ["G"], "gihwr", RESULT_FORMAT_GRADE, withMetrics(3, 55))).toBe("A+");
    expect(formatWinRate(52, ["G"], "gihwr", RESULT_FORMAT_GRADE, withMetrics(3, 55))).toBe("D+");
  });
  it("maps the win rate onto a 0–5 rating scale", () => {
    expect(formatWinRate(61, ["G"], "gihwr", RESULT_FORMAT_RATING, withMetrics(3, 55))).toBe("5.0");
    expect(formatWinRate(55, ["G"], "gihwr", RESULT_FORMAT_RATING, withMetrics(3, 55))).toBe("2.3");
  });
});

describe("artUrl", () => {
  it("returns null without an image", () => {
    expect(artUrl([])).toBeNull();
  });
  it("prefixes relative 17Lands paths", () => {
    expect(artUrl(["/static/img/cards/x.jpg"])).toBe(
      "https://www.17lands.com/static/img/cards/x.jpg",
    );
  });
  it("upgrades Scryfall small/normal prints to large", () => {
    expect(artUrl(["https://cards.scryfall.io/small/front/x.jpg"])).toBe(
      "https://cards.scryfall.io/large/front/x.jpg",
    );
    expect(artUrl(["https://cards.scryfall.io/normal/front/x.jpg"])).toBe(
      "https://cards.scryfall.io/large/front/x.jpg",
    );
  });
  it("passes absolute non-Scryfall URLs through unchanged", () => {
    expect(artUrl(["https://example.com/x.png"])).toBe("https://example.com/x.png");
  });
});

describe("cardNameColor", () => {
  it("uses the mana color for mono cards, orange for multi, grey otherwise", () => {
    expect(cardNameColor(["W"])).toBe("var(--mana-w)");
    expect(cardNameColor(["W", "U"])).toBe("var(--mana-multi)");
    expect(cardNameColor([])).toBe("var(--gruff)");
    expect(cardNameColor(["Z"])).toBe("var(--gruff)");
  });
});

describe("cardRowClass", () => {
  it("flags picked + elite rows and applies the optional color tint", () => {
    expect(cardRowClass(card({ isPicked: true }), false)).toBe("picked");
    expect(
      cardRowClass(card({ recommendation: { ...card({}).recommendation!, isElite: true } }), false),
    ).toContain("elite");
    expect(cardRowClass(card({ colors: ["R"] }), true)).toContain("tint-r");
    expect(cardRowClass(card({ colors: ["W", "U"] }), true)).toContain("tint-multi");
    expect(cardRowClass(card({ colors: ["R"] }), false)).not.toContain("tint");
  });
});

describe("nameColumn", () => {
  it("renders the rarity initial uppercased and bold-coded, plus the card name", () => {
    const { container } = render(
      <>{nameColumn().cell(card({ rarity: "rare" }))}</>,
    );
    const badge = container.querySelector(".card-rarity");
    expect(badge?.textContent).toBe("R");
    expect(screen.getByText("Grizzly Bears")).toBeInTheDocument();
  });
  it("skips the rarity badge when rarity is unknown", () => {
    const { container } = render(<>{nameColumn().cell(card({ rarity: "" }))}</>);
    expect(container.querySelector(".card-rarity")).toBeNull();
  });
  it("colors elite (bomb) names with the mana color too", () => {
    const elite = card({
      colors: ["R"],
      recommendation: { ...card({}).recommendation!, isElite: true },
    });
    const { container } = render(
      <>{nameColumn({ colorName: true }).cell(elite)}</>,
    );
    expect(container.querySelector(".card-name")?.getAttribute("style")).toContain(
      "var(--mana-r)",
    );
  });
  it("leaves names uncolored without the colorName option", () => {
    const { container } = render(<>{nameColumn().cell(card({ colors: ["G"] }))}</>);
    expect(container.querySelector(".card-name")?.getAttribute("style")).toBeNull();
  });
});

describe("tagChip", () => {
  const rec = (tags: string[]) => ({
    cardName: "Grizzly Bears",
    baseWinRate: 0,
    contextualScore: 0,
    zScore: 0,
    castProbability: 0,
    wheelChance: 0,
    functionalCmc: 0,
    reasoning: [],
    isElite: false,
    archetypeFit: "",
    tags,
  });

  it("keeps the legacy emoji-only chip in English", () => {
    expect(tagChip("removal", "en", lookup("en"))).toBe("🎯");
  });
  it("renders emoji + translated role in Chinese", () => {
    expect(tagChip("removal", "zh", lookup("zh"))).toBe("🎯 解场");
    expect(tagChip("evasion", "zh", lookup("zh"))).toBe("🦅 穿透");
    expect(tagChip("fixing_ramp", "zh", lookup("zh"))).toBe("🌈 调色加速");
  });
  it("passes unknown tags through as the raw key, or the fallback label", () => {
    expect(tagChip("mystery", "en", lookup("en"))).toBe("mystery");
    expect(tagChip("mystery", "zh", lookup("zh"))).toBe("mystery");
    expect(tagChip("mystery", "zh", lookup("zh"), "Mystery")).toBe("Mystery");
  });

  it("localizes the DataTable tags column cell in Chinese only", () => {
    const en = cardColumn("tags", undefined, lookup("en"), "en");
    const zh = cardColumn("tags", undefined, lookup("zh"), "zh");
    const tagged = card({ recommendation: rec(["removal", "evasion"]) });
    expect(en.cell(tagged)).toBe("🎯 🦅");
    expect(zh.cell(tagged)).toBe("🎯 解场 🦅 穿透");
    expect(cardColumn("tags", undefined, lookup("zh"), "zh").cell(card())).toBe("—");
  });
});
