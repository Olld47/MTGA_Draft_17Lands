import type { Card } from "../api/types";
import { ManaCost } from "./ManaCost";
import type { Column } from "./DataTable";

export const fmtPct = (v: number | null) => (v == null ? "—" : v.toFixed(1));
export const fmtNum = (v: number | null) => (v == null ? "—" : v.toFixed(1));

/** 17Lands datasets store relative art paths; Scryfall URLs come through
 *  absolute. Prefer the large printing when Scryfall offers a size variant. */
export function artUrl(image: string[]): string | null {
  const raw = image[0];
  if (!raw) return null;
  if (raw.startsWith("/static")) return `https://www.17lands.com${raw}`;
  if (raw.includes("scryfall") && !raw.includes("format=image")) {
    return raw.replace("/small/", "/large/").replace("/normal/", "/large/");
  }
  return raw;
}

/** Rarity ink, lifted from the legacy CardToolTip header coloring. */
const RARITY_COLOR: Record<string, string> = {
  mythic: "#d4712a",
  rare: "#c9a227",
  uncommon: "#3a7bd5",
  common: "#8a8a8a",
};

/** Mana flair for card names: mono-color cards render in their color,
 *  multi-color in gold, colorless in grey — the legacy CardToolTip look. */
const CARD_NAME_COLOR: Record<string, string> = {
  w: "var(--mana-w)",
  u: "var(--mana-u)",
  b: "var(--mana-b)",
  r: "var(--mana-r)",
  g: "var(--mana-g)",
};

export function cardNameColor(colors: string[]): string {
  if (colors.length === 1) {
    return CARD_NAME_COLOR[colors[0].toLowerCase()] ?? "var(--gruff)";
  }
  return colors.length > 1 ? "var(--gold-foil)" : "var(--gruff)";
}

/** Shared row class: picked/elite state + optional color tint. */
export function cardRowClass(card: Card, colorTint: boolean): string {
  const classes: string[] = [];
  if (card.isPicked) classes.push("picked");
  if (card.recommendation?.isElite) classes.push("elite");
  if (colorTint) {
    if (card.colors.length === 1) {
      classes.push(`tint-${card.colors[0].toLowerCase()}`);
    } else if (card.colors.length > 1) {
      classes.push("tint-multi");
    }
  }
  return classes.join(" ");
}

export function nameColumn(opts?: { colorName?: boolean }): Column<Card> {
  return {
    id: "name",
    header: "Card",
    cell: (c) => (
      <span>
        {c.rarity && (
          <span
            className="card-rarity"
            title={c.rarity}
            style={{ color: RARITY_COLOR[c.rarity] ?? "#8a8a8a" }}
          >
            {c.rarity[0]}
          </span>
        )}
        <span
          className="card-name"
          style={opts?.colorName ? { color: cardNameColor(c.colors) } : undefined}
        >
          {c.name}
        </span>
        {c.returnableAt.length > 0 && (
          <span title={`May wheel at pick ${c.returnableAt.join(", ")}`}>
            {" "}
            ⟳{c.returnableAt.join(",")}
          </span>
        )}
      </span>
    ),
    sortValue: (c) => c.name,
  };
}

export function manaColumn(): Column<Card> {
  return {
    id: "cost",
    header: "Cost",
    cell: (c) => <ManaCost cost={c.manaCost} />,
    sortValue: (c) => c.cmc,
  };
}

export function statColumns(): Column<Card>[] {
  return [
    {
      id: "gihwr",
      header: "GIHWR",
      numeric: true,
      cell: (c) => fmtPct(c.stats.gihwr),
      sortValue: (c) => c.stats.gihwr ?? -1,
    },
    {
      id: "ohwr",
      header: "OHWR",
      numeric: true,
      cell: (c) => fmtPct(c.stats.ohwr),
      sortValue: (c) => c.stats.ohwr ?? -1,
    },
    {
      id: "alsa",
      header: "ALSA",
      numeric: true,
      cell: (c) => fmtNum(c.stats.alsa),
      sortValue: (c) => c.stats.alsa ?? 99,
    },
    {
      id: "ata",
      header: "ATA",
      numeric: true,
      cell: (c) => fmtNum(c.stats.ata),
      sortValue: (c) => c.stats.ata ?? 99,
    },
    {
      id: "iwd",
      header: "IWD",
      numeric: true,
      cell: (c) => fmtNum(c.stats.iwd),
      sortValue: (c) => c.stats.iwd ?? -99,
    },
  ];
}
