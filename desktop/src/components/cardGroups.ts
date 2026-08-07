import type { DeckRow } from "../api/types";

/** Group-by modes for the sealed pool / deck tables — a port of the legacy
 *  sealed_studio.py "Sort:" combobox (["Color", "CMC", "Rarity", "Type"]). */
export type GroupBy = "color" | "cmc" | "rarity" | "type";

export const GROUP_OPTIONS: { id: GroupBy; label: string }[] = [
  { id: "color", label: "Color" },
  { id: "cmc", label: "CMC" },
  { id: "rarity", label: "Rarity" },
  { id: "type", label: "Type" },
];

const COLOR_LABELS: Record<string, string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  multi: "Multicolor",
  colorless: "Colorless",
  lands: "Lands",
};
const COLOR_ORDER = ["W", "U", "B", "R", "G", "multi", "colorless", "lands"];

const CMC_LABELS: Record<string, string> = {
  "0": "0 CMC",
  "1": "1 CMC",
  "2": "2 CMC",
  "3": "3 CMC",
  "4": "4 CMC",
  "5": "5 CMC",
  "6": "6+ CMC",
  lands: "Lands",
};
const CMC_ORDER = ["0", "1", "2", "3", "4", "5", "6", "lands"];

const RARITY_LABELS: Record<string, string> = {
  common: "Common",
  uncommon: "Uncommon",
  rare_mythic: "Rare/Mythic",
  basics: "Basic Lands",
};
const RARITY_ORDER = ["common", "uncommon", "rare_mythic", "basics"];

const TYPE_LABELS: Record<string, string> = {
  creatures: "Creatures",
  instants_sorceries: "Instants/Sorceries",
  artifacts_enchantments: "Artifacts/Enchantments",
  planeswalkers_battles: "Planeswalkers/Battles",
  lands: "Lands",
  other: "Other",
};
const TYPE_ORDER = [
  "creatures",
  "instants_sorceries",
  "artifacts_enchantments",
  "planeswalkers_battles",
  "lands",
  "other",
];

/** Bucket a deck row per the legacy sealed_studio._populate_canvas rules
 *  (sealed_studio.py:913-1124) — same buckets, same fallbacks. */
export function groupKey(row: DeckRow, by: GroupBy): string {
  const types = row.types;
  if (by === "color") {
    // _get_color_group: Land first, then colorless, then multicolor, then mono.
    if (types.includes("Land")) return "lands";
    const colors = row.colors;
    if (colors.length === 0) return "colorless";
    if (colors.length > 1) return "multi";
    const single = colors[0].toUpperCase();
    return "WUBRG".includes(single) ? single : "colorless";
  }
  if (by === "cmc") {
    // Lands separate; non-lands clamp at 6+.
    if (types.includes("Land")) return "lands";
    return String(Math.min(6, Math.max(0, Math.floor(row.cmc))));
  }
  if (by === "rarity") {
    // Basic lands get their own bucket; rare/mythic share one; unknown falls
    // back to common, exactly like the legacy loop.
    if (types.includes("Land") && types.includes("Basic")) return "basics";
    const r = row.rarity.toLowerCase();
    if (r === "rare" || r === "mythic") return "rare_mythic";
    return r === "uncommon" ? "uncommon" : "common";
  }
  // Type: first-match-wins chain over the types list.
  if (types.includes("Creature")) return "creatures";
  if (types.includes("Instant") || types.includes("Sorcery"))
    return "instants_sorceries";
  if (types.includes("Artifact") || types.includes("Enchantment"))
    return "artifacts_enchantments";
  if (types.includes("Planeswalker") || types.includes("Battle"))
    return "planeswalkers_battles";
  if (types.includes("Land")) return "lands";
  return "other";
}

/** Canonical left-to-right bucket order for a group-by mode. */
export function groupOrder(by: GroupBy): string[] {
  if (by === "color") return COLOR_ORDER;
  if (by === "cmc") return CMC_ORDER;
  if (by === "rarity") return RARITY_ORDER;
  return TYPE_ORDER;
}

function groupBaseLabel(by: GroupBy, key: string): string {
  const labels =
    by === "color"
      ? COLOR_LABELS
      : by === "cmc"
        ? CMC_LABELS
        : by === "rarity"
          ? RARITY_LABELS
          : TYPE_LABELS;
  return labels[key] ?? key;
}

/** "Label (N)" header text, N = total copies in the group (legacy summed each
 *  card's count field, not the number of distinct names). */
export function groupLabel(by: GroupBy, key: string, rows: DeckRow[]): string {
  const n = rows.reduce((total, r) => total + r.count, 0);
  return `${groupBaseLabel(by, key)} (${n})`;
}
