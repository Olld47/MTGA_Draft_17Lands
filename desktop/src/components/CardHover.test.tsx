import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import type { Card, DeckRow, Recommendation } from "../api/types";
import { CardHoverTip, hoverDataFromCard, hoverDataFromDeckRow } from "./CardHover";

const rec = (over: Partial<Recommendation> = {}): Recommendation => ({
  cardName: "X",
  baseWinRate: 55,
  contextualScore: 70,
  zScore: 1,
  castProbability: 0.9,
  wheelChance: 0.2,
  functionalCmc: 2,
  reasoning: [],
  isElite: false,
  archetypeFit: "",
  tags: [],
  ...over,
});

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

const deckRow = (over: Partial<DeckRow> = {}): DeckRow => ({
  name: "Grizzly Bears",
  count: 2,
  cmc: 2,
  types: ["Creature"],
  colors: ["G"],
  rarity: "uncommon",
  manaCost: "{1}{G}",
  gihwr: 55.1,
  iwd: null,
  alsa: null,
  ata: null,
  samples: null,
  deckColors: [],
  tags: [],
  rowTag: "",
  image: ["/static/img/cards/grizzly-bears.jpg"],
  ...over,
});

describe("hoverDataFromCard", () => {
  it("maps stats and advisor tags through to the tooltip data", () => {
    const c = card({
      rarity: "rare",
      stats: {
        gihwr: 58.5,
        ohwr: 54,
        gpwr: 56,
        alsa: 4.2,
        ata: 5.1,
        iwd: 1.5,
        gih: 3,
        ngp: 1234,
      },
      recommendation: rec({ tags: ["removal", "evasion"] }),
      deckColors: [
        { color: "W", gihwr: 57.2, samples: 99 },
        { color: "WU", gihwr: 55.5, samples: 80 },
      ],
    });
    const d = hoverDataFromCard(c);
    expect(d.name).toBe("Grizzly Bears");
    expect(d.rarity).toBe("rare");
    expect(d.stats.gihwr).toBe(58.5);
    expect(d.stats.iwd).toBe(1.5);
    expect(d.stats.alsa).toBe(4.2);
    expect(d.stats.ata).toBe(5.1);
    // Games = the legacy ngp (games/samples) field.
    expect(d.stats.games).toBe(1234);
    expect(d.tags).toEqual(["removal", "evasion"]);
    // Per-color play shares pass straight through for ARCHETYPE PLAY SHARE.
    expect(d.deckColors).toEqual([
      { color: "W", gihwr: 57.2, samples: 99 },
      { color: "WU", gihwr: 55.5, samples: 80 },
    ]);
  });
  it("defaults to no tags when the card has no recommendation", () => {
    expect(hoverDataFromCard(card()).tags).toEqual([]);
  });
});

describe("hoverDataFromDeckRow", () => {
  it("maps the All Decks hover stats, play shares, and roles through", () => {
    const d = hoverDataFromDeckRow(
      deckRow({
        gihwr: 55.1,
        iwd: 2.6,
        alsa: 3.8,
        ata: 4.2,
        samples: 12345,
        deckColors: [
          { color: "BR", gihwr: 62.3, samples: 400 },
          { color: "WU", gihwr: 55.5, samples: 300 },
        ],
        tags: ["removal"],
      }),
    );
    expect(d.name).toBe("Grizzly Bears");
    expect(d.rarity).toBe("uncommon");
    expect(d.stats).toEqual({
      gihwr: 55.1,
      iwd: 2.6,
      alsa: 3.8,
      ata: 4.2,
      games: 12345,
    });
    expect(d.deckColors).toEqual([
      { color: "BR", gihwr: 62.3, samples: 400 },
      { color: "WU", gihwr: 55.5, samples: 300 },
    ]);
    expect(d.tags).toEqual(["removal"]);
  });
});

describe("CardHoverTip", () => {
  it("renders the uppercase rarity, art, GLOBAL PERFORMANCE, ARCHETYPE PLAY SHARE, and CARD ROLES", () => {
    const { container } = render(
      <CardHoverTip
        data={hoverDataFromCard(
          card({
            rarity: "mythic",
            stats: {
              gihwr: 58.5,
              ohwr: null,
              gpwr: null,
              alsa: 4.2,
              ata: 5.1,
              iwd: 3.2,
              gih: null,
              ngp: 1234,
            },
            recommendation: rec({ tags: ["removal"] }),
            deckColors: [
              { color: "W", gihwr: 57.2, samples: 99 },
              { color: "WU", gihwr: 55.5, samples: 80 },
            ],
          }),
        )}
      />,
    );
    // Header: colored rarity word (uppercased) + card name.
    expect(screen.getByText("MYTHIC")).toBeInTheDocument();
    expect(screen.getByText("Grizzly Bears")).toBeInTheDocument();
    // Art.
    const img = container.querySelector(".ch-image");
    expect(img).toBeInTheDocument();
    expect(img?.getAttribute("src")).toBe(
      "https://www.17lands.com/static/img/cards/grizzly-bears.jpg",
    );
    // Stat rows.
    expect(screen.getByText("GLOBAL PERFORMANCE")).toBeInTheDocument();
    expect(screen.getByText("GIH WR")).toBeInTheDocument();
    expect(screen.getByText("58.5%")).toBeInTheDocument();
    expect(screen.getByText("+3.2%")).toBeInTheDocument();
    expect(screen.getByText("ALSA")).toBeInTheDocument();
    expect(screen.getByText("4.2")).toBeInTheDocument();
    expect(screen.getByText("ATA")).toBeInTheDocument();
    expect(screen.getByText("5.1")).toBeInTheDocument();
    expect(screen.getByText("Games")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    // The GIH WR row is flagged "up" (>= 55) and IWD "accent" (>= 3).
    expect(container.querySelector(".ch-grid dt.up")?.textContent).toBe("GIH WR");
    expect(container.querySelector(".ch-grid dd.accent")?.textContent).toBe("+3.2%");
    // Archetype play share: "• Name (key): WR%" per color, up-flagged >= 55.
    expect(screen.getByText("ARCHETYPE PLAY SHARE")).toBeInTheDocument();
    expect(screen.getByText(/Azorius \(WU\): 55\.5% WR/)).toBeInTheDocument();
    expect(
      container.querySelector(".ch-archetype div.up")?.textContent,
    ).toContain("White (W): 57.2% WR");
    // Roles.
    expect(screen.getByText("CARD ROLES")).toBeInTheDocument();
    expect(screen.getByText("🎯")).toBeInTheDocument();
  });
  it("renders a bare header when a deck row carries no stats or tags", () => {
    const { container } = render(
      <CardHoverTip
        data={hoverDataFromDeckRow(
          deckRow({ rarity: "common", gihwr: null, image: [] }),
        )}
      />,
    );
    expect(screen.getByText("COMMON")).toBeInTheDocument();
    expect(container.querySelector(".ch-image")).toBeNull();
    expect(container.querySelector(".ch-info")).toBeNull();
    expect(screen.queryByText("GIH WR")).not.toBeInTheDocument();
  });
});
