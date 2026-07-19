import type { Card } from "../api/types";
import { ManaCost } from "./ManaCost";
import type { Column } from "./DataTable";

export const fmtPct = (v: number | null) => (v == null ? "—" : v.toFixed(1));
export const fmtNum = (v: number | null) => (v == null ? "—" : v.toFixed(1));

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

export function nameColumn(): Column<Card> {
  return {
    id: "name",
    header: "Card",
    cell: (c) => (
      <span>
        <span className="card-name">{c.name}</span>
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
      id: "iwd",
      header: "IWD",
      numeric: true,
      cell: (c) => fmtNum(c.stats.iwd),
      sortValue: (c) => c.stats.iwd ?? -99,
    },
  ];
}
