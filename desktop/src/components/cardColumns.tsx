import type { Card, SetMetrics } from "../api/types";
import { ManaCost } from "./ManaCost";
import type { Column } from "./DataTable";

export const fmtPct = (v: number | null) => (v == null ? "—" : v.toFixed(1));
export const fmtNum = (v: number | null) => (v == null ? "—" : v.toFixed(1));

/** Win-rate fields that Grade/Rating applies to — the subset of the backend
 *  WIN_RATE_OPTIONS the desktop can render (GN SWR / GD WR have no CardStats
 *  plumbing and stay unwired). */
export const WIN_RATE_FIELDS = new Set(["gihwr", "ohwr", "gpwr"]);

/** Optional card-table columns — the fields the legacy COLUMN_FIELD_LABELS
 *  exposes to its "Add Column" menus (plus TIER, which the desktop collapses
 *  into the single per-card `tier` field). Card tables identify themselves with
 *  a viewId and persist their visible set through Settings.columnConfigs. */
export const CARD_COLUMN_LABELS: Record<string, string> = {
  value: "Value",
  gihwr: "GIH WR",
  ohwr: "OH WR",
  gpwr: "GP WR",
  alsa: "ALSA",
  ata: "ATA",
  iwd: "IWD",
  wheel: "Wheel",
  colors: "Colors",
  count: "Count",
  tags: "Tags",
  tier: "Tier",
};

export const CARD_COLUMN_FIELDS = Object.keys(CARD_COLUMN_LABELS);

/** Emoji per card role — the icon portion of legacy TAG_VISUALS. Shared by the
 *  tags column and the AdvisorPanel tags line. */
export const TAG_ICONS: Record<string, string> = {
  removal: "🎯",
  evasion: "🦅",
  card_advantage: "📚",
  fixing_ramp: "🌈",
  fixing: "🌈",
  combat_trick: "⚔️",
  enhancement: "🛡️",
  token_maker: "👯",
  lifegain: "💖",
  mana_sink: "⚙️",
  protection: "🛡️",
  hate: "🚫",
};

/** (grade, z-score threshold) pairs in descending order — a TS port of
 *  src/constants GRADE_DEVIATION_DICT. */
const GRADE_DEVIATION_DICT: [string, number][] = [
  ["A+", 2.0],
  ["A", 1.67],
  ["A-", 1.33],
  ["B+", 1.0],
  ["B", 0.67],
  ["B-", 0.33],
  ["C+", 0.0],
  ["C", -0.33],
  ["C-", -0.67],
  ["D+", -1.0],
  ["D", -1.33],
  ["D-", -1.67],
];

export const RESULT_FORMAT_PERCENTAGE = "Percentage";
export const RESULT_FORMAT_RATING = "Rating";
export const RESULT_FORMAT_GRADE = "Grade";
const ALL_DECKS = "All Decks";

/** Frontend port of src.card_logic.format_win_rate: converts a raw win-rate
 *  value to its display string per the result_format setting, using the active
 *  dataset's per-color mean/std. Non-win-rate fields, missing metrics, and a
 *  zero std all fall through to the raw percentage. */
export function formatWinRate(
  val: number | null,
  colors: string[],
  field: string,
  resultFormat: string,
  metrics: SetMetrics,
): string {
  if (val == null) return "—";
  if (val === 0) return "-";
  if (resultFormat === RESULT_FORMAT_PERCENTAGE || !metrics.hasData) {
    return val.toFixed(1);
  }
  if (!WIN_RATE_FIELDS.has(field)) return val.toFixed(1);
  const color = colors[0] ?? ALL_DECKS;
  const m = metrics.metrics[field]?.[color];
  if (!m || m.std === 0) return val.toFixed(1);
  const z = (val - m.mean) / m.std;

  if (resultFormat === RESULT_FORMAT_GRADE) {
    for (const [grade, limit] of GRADE_DEVIATION_DICT) {
      if (z >= limit) return grade;
    }
    return "F";
  }
  if (resultFormat === RESULT_FORMAT_RATING) {
    const upper = m.mean + 2.0 * m.std;
    const lower = m.mean - 1.67 * m.std;
    if (upper === lower) return "2.5";
    const score = ((val - lower) / (upper - lower)) * 5.0;
    return Math.max(0, Math.min(5, score)).toFixed(1);
  }
  return val.toFixed(1);
}

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
          style={
            opts?.colorName && !c.recommendation?.isElite
              ? { color: cardNameColor(c.colors) }
              : undefined
          }
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

/** result_format + win-rate metrics, produced by useStatFormat(). */
export interface StatFormat {
  resultFormat: string;
  metrics: SetMetrics;
}

function winRateColumn(
  field: "gihwr" | "ohwr" | "gpwr",
  format?: StatFormat,
): Column<Card> {
  const wr = (c: Card) =>
    format
      ? formatWinRate(c.stats[field], c.colors, field, format.resultFormat, format.metrics)
      : fmtPct(c.stats[field]);
  return {
    id: field,
    header: CARD_COLUMN_LABELS[field],
    numeric: true,
    cell: (c) => wr(c),
    sortValue: (c) => c.stats[field] ?? -1,
  };
}

function statNumColumn(field: "alsa" | "ata" | "iwd"): Column<Card> {
  return {
    id: field,
    header: CARD_COLUMN_LABELS[field],
    numeric: true,
    cell: (c) => fmtNum(c.stats[field]),
    sortValue: (c) => c.stats[field] ?? (field === "iwd" ? -99 : 99),
  };
}

export function statColumns(format?: StatFormat): Column<Card>[] {
  return [
    winRateColumn("gihwr", format),
    winRateColumn("ohwr", format),
    statNumColumn("alsa"),
    statNumColumn("ata"),
    statNumColumn("iwd"),
  ];
}

/** Build one card column by field id — the registry behind the per-table
 *  column config (useColumnConfig). The win-rate columns take the live
 *  result_format + metrics so a later table refresh re-renders them. */
export function cardColumn(field: string, format?: StatFormat): Column<Card> {
  switch (field) {
    case "value":
      return {
        id: "value",
        header: "Value",
        numeric: true,
        cell: (c) =>
          c.recommendation ? c.recommendation.contextualScore.toFixed(0) : "—",
        sortValue: (c) => c.recommendation?.contextualScore ?? -1,
      };
    case "gihwr":
    case "ohwr":
    case "gpwr":
      return winRateColumn(field, format);
    case "alsa":
    case "ata":
    case "iwd":
      return statNumColumn(field);
    case "wheel":
      return {
        id: "wheel",
        header: "Wheel",
        numeric: true,
        cell: (c) =>
          c.recommendation && c.recommendation.wheelChance > 0
            ? `${c.recommendation.wheelChance.toFixed(0)}%`
            : "—",
        sortValue: (c) => c.recommendation?.wheelChance ?? 0,
      };
    case "colors":
      return {
        id: "colors",
        header: "Colors",
        cell: (c) => (c.colors.length > 0 ? c.colors.join("") : "—"),
        sortValue: (c) => c.colors.join(""),
      };
    case "count":
      return {
        id: "count",
        header: "Count",
        numeric: true,
        cell: (c) => c.count,
        sortValue: (c) => c.count,
      };
    case "tags": {
      const tags = (c: Card) => c.recommendation?.tags ?? [];
      return {
        id: "tags",
        header: "Tags",
        cell: (c) =>
          tags(c).length > 0 ? tags(c).map((t) => TAG_ICONS[t] ?? t).join(" ") : "—",
        sortValue: (c) => tags(c).join(" "),
      };
    }
    case "tier":
      return {
        id: "tier",
        header: "Tier",
        cell: (c) => c.tier ?? "—",
        sortValue: (c) => c.tier ?? "",
      };
    default:
      return { id: field, header: field, cell: () => "—" };
  }
}
