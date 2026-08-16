import type { Card, SetMetrics } from "../api/types";
import { ManaCost } from "./ManaCost";
import type { Column } from "./DataTable";
import type { Lang } from "../i18n/locales";

/** Translate callback — mirrors useLanguage().t. Builders take it as a param so
 *  the caller's render (which subscribes to the language store) re-invokes them
 *  with fresh translations on switch. The identity fallback keeps standalone
 *  builder tests (which only exercise .cell) compiling without wiring a store. */
export type Translate = (
  key: string,
  vars?: Record<string, string | number>,
) => string;
const identityT: Translate = (key) => key;

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
  value: "col.value",
  gihwr: "col.gihwr",
  ohwr: "col.ohwr",
  gpwr: "col.gpwr",
  alsa: "col.alsa",
  ata: "col.ata",
  iwd: "col.iwd",
  wheel: "col.wheel",
  colors: "col.colors",
  count: "col.count",
  tags: "col.tags",
  tier: "col.tier",
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

/** Localized card-role tag chip. zh renders the emoji plus the translated
 *  role (the recap chips' "🎯 Removal" shape); en keeps the legacy emoji-only
 *  chips so the English UI is unchanged. Unknown tags pass through as the raw
 *  key, or as `fallback` (e.g. the backend label) when one is supplied. */
export function tagChip(
  tag: string,
  lang: Lang,
  t: Translate,
  fallback?: string,
): string {
  if (lang === "zh") {
    const label = t(`tag.${tag}`);
    if (label !== `tag.${tag}`) {
      const icon = TAG_ICONS[tag] ?? "";
      return icon ? `${icon} ${label}` : label;
    }
  }
  return fallback ?? TAG_ICONS[tag] ?? tag;
}

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
export const RARITY_COLOR: Record<string, string> = {
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

export function nameColumn(
  opts?: { colorName?: boolean },
  t: Translate = identityT,
): Column<Card> {
  return {
    id: "name",
    header: t("col.card"),
    cell: (c) => (
      <span>
        {c.rarity && (
          <span
            className="card-rarity"
            title={c.rarity}
            style={{ color: RARITY_COLOR[c.rarity] ?? "#8a8a8a" }}
          >
            {c.rarity[0].toUpperCase()}
          </span>
        )}
        <span
          className="card-name"
          style={
            opts?.colorName ? { color: cardNameColor(c.colors) } : undefined
          }
        >
          {c.name}
        </span>
        {c.returnableAt.length > 0 && (
          <span title={t("table.wheelTitle", { picks: c.returnableAt.join(", ") })}>
            {" "}
            ⟳{c.returnableAt.join(",")}
          </span>
        )}
      </span>
    ),
    sortValue: (c) => c.name,
  };
}

export function manaColumn(t: Translate = identityT): Column<Card> {
  return {
    id: "cost",
    header: t("col.cost"),
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
  t: Translate = identityT,
): Column<Card> {
  const wr = (c: Card) =>
    format
      ? formatWinRate(c.stats[field], c.colors, field, format.resultFormat, format.metrics)
      : fmtPct(c.stats[field]);
  return {
    id: field,
    header: t(CARD_COLUMN_LABELS[field]),
    numeric: true,
    cell: (c) => wr(c),
    sortValue: (c) => c.stats[field] ?? -1,
  };
}

function statNumColumn(
  field: "alsa" | "ata" | "iwd",
  t: Translate = identityT,
): Column<Card> {
  return {
    id: field,
    header: t(CARD_COLUMN_LABELS[field]),
    numeric: true,
    cell: (c) => fmtNum(c.stats[field]),
    sortValue: (c) => c.stats[field] ?? (field === "iwd" ? -99 : 99),
  };
}

export function statColumns(format?: StatFormat, t: Translate = identityT): Column<Card>[] {
  return [
    winRateColumn("gihwr", format, t),
    winRateColumn("ohwr", format, t),
    statNumColumn("alsa", t),
    statNumColumn("ata", t),
    statNumColumn("iwd", t),
  ];
}

/** Build one card column by field id — the registry behind the per-table
 *  column config (useColumnConfig). The win-rate columns take the live
 *  result_format + metrics so a later table refresh re-renders them. `lang`
 *  drives the tags column's chip localization. */
export function cardColumn(
  field: string,
  format?: StatFormat,
  t: Translate = identityT,
  lang: Lang = "en",
): Column<Card> {
  switch (field) {
    case "value":
      return {
        id: "value",
        header: t("col.value"),
        numeric: true,
        cell: (c) =>
          c.recommendation ? c.recommendation.contextualScore.toFixed(0) : "—",
        sortValue: (c) => c.recommendation?.contextualScore ?? -1,
      };
    case "gihwr":
    case "ohwr":
    case "gpwr":
      return winRateColumn(field, format, t);
    case "alsa":
    case "ata":
    case "iwd":
      return statNumColumn(field, t);
    case "wheel":
      return {
        id: "wheel",
        header: t("col.wheel"),
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
        header: t("col.colors"),
        cell: (c) => (c.colors.length > 0 ? c.colors.join("") : "—"),
        sortValue: (c) => c.colors.join(""),
      };
    case "count":
      return {
        id: "count",
        header: t("col.count"),
        numeric: true,
        cell: (c) => c.count,
        sortValue: (c) => c.count,
      };
    case "tags": {
      const tags = (c: Card) => c.recommendation?.tags ?? [];
      return {
        id: "tags",
        header: t("col.tags"),
        cell: (c) =>
          tags(c).length > 0
            ? tags(c).map((tag) => tagChip(tag, lang, t)).join(" ")
            : "—",
        sortValue: (c) => tags(c).join(" "),
      };
    }
    case "tier":
      return {
        id: "tier",
        header: t("col.tier"),
        cell: (c) => c.tier ?? "—",
        sortValue: (c) => c.tier ?? "",
      };
    default:
      return { id: field, header: field, cell: () => "—" };
  }
}
