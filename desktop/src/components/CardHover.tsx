import type { Card, DeckColor, DeckRow } from "../api/types";
import { useLanguage } from "../i18n/useLanguage";
import type { Translate } from "./cardColumns";
import {
  artUrl,
  cardNameColor,
  RARITY_COLOR,
  TAG_ICONS,
} from "./cardColumns";

/** Port of src/constants.py::COLOR_NAMES_DICT — WUBRG keys to the guild/shard
 *  names the legacy tooltip renders in ARCHETYPE PLAY SHARE. */
const COLOR_NAMES: Record<string, string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
  WU: "Azorius",
  UB: "Dimir",
  BR: "Rakdos",
  RG: "Gruul",
  WG: "Selesnya",
  WB: "Orzhov",
  BG: "Golgari",
  UG: "Simic",
  UR: "Izzet",
  WR: "Boros",
  WUR: "Jeskai",
  UBG: "Sultai",
  WBR: "Mardu",
  URG: "Temur",
  WBG: "Abzan",
  WUB: "Esper",
  UBR: "Grixis",
  BRG: "Jund",
  WRG: "Naya",
  WUG: "Bant",
  WUBR: "Not-Green",
  UBRG: "Not-White",
  WBRG: "Not-Blue",
  WURG: "Not-Black",
  WUBG: "Not-Red",
  WUBRG: "Five-Color",
};

/** Data the hover tooltip renders for a row — a TS port of the legacy
 *  CardToolTip (src/ui/components.py): name + colored rarity header, the card
 *  art, a GLOBAL PERFORMANCE stat block, an ARCHETYPE PLAY SHARE list, and CARD
 *  ROLES from the advisor tags. */
export interface CardHoverData {
  name: string;
  rarity: string;
  colors: string[];
  image: string[];
  /** GLOBAL PERFORMANCE block. Deck rows ship the All Decks entry for
   *  IWD/ALSA/ATA/Games (the legacy tooltip reads `deck_colors["All Decks"]`);
   *  GIH WR keeps the active-filter value the table column shows. */
  stats: {
    gihwr: number | null;
    iwd: number | null;
    alsa: number | null;
    ata: number | null;
    games: number | null;
  };
  /** Per-color play shares (legacy: colors with GIH WR > 0, sorted by samples,
   *  top 10) for the ARCHETYPE PLAY SHARE section. */
  deckColors: DeckColor[];
  /** Advisor card roles (legacy TAG_VISUALS). */
  tags: string[];
}

export function hoverDataFromCard(card: Card): CardHoverData {
  return {
    name: card.name,
    rarity: card.rarity,
    colors: card.colors,
    image: card.image,
    stats: {
      gihwr: card.stats.gihwr,
      iwd: card.stats.iwd,
      alsa: card.stats.alsa,
      ata: card.stats.ata,
      games: card.stats.ngp,
    },
    deckColors: card.deckColors,
    tags: card.recommendation?.tags ?? [],
  };
}

export function hoverDataFromDeckRow(row: DeckRow): CardHoverData {
  return {
    name: row.name,
    rarity: row.rarity,
    colors: row.colors,
    image: row.image,
    stats: {
      gihwr: row.gihwr,
      iwd: row.iwd,
      alsa: row.alsa,
      ata: row.ata,
      games: row.samples,
    },
    deckColors: row.deckColors,
    tags: row.tags,
  };
}

const fmtPct = (v: number) => `${v.toFixed(1)}%`;
const fmtSigned = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
const fmtGames = (v: number) => v.toLocaleString();

interface StatRow {
  label: string;
  value: string;
  cls?: string;
}

function statRows(
  stats: CardHoverData["stats"],
  t: Translate,
): StatRow[] {
  const rows: StatRow[] = [];
  if (stats.gihwr != null) {
    rows.push({
      label: t("col.gihwr"),
      value: fmtPct(stats.gihwr),
      cls: stats.gihwr >= 55 ? "up" : undefined,
    });
  }
  if (stats.iwd != null) {
    rows.push({
      label: t("col.iwd"),
      value: fmtSigned(stats.iwd),
      cls: stats.iwd >= 3 ? "accent" : undefined,
    });
  }
  if (stats.alsa != null)
    rows.push({ label: t("col.alsa"), value: stats.alsa.toFixed(1) });
  if (stats.ata != null)
    rows.push({ label: t("col.ata"), value: stats.ata.toFixed(1) });
  if (stats.games != null)
    rows.push({ label: t("hover.games"), value: fmtGames(stats.games) });
  return rows;
}

/** Cursor-following hover card: art + the legacy CardToolTip stat panel.
 *  Rendered by DataTable when `hoverContent` is wired (pack / taken / deck). */
export function CardHoverTip({ data }: { data: CardHoverData }) {
  const { t } = useLanguage();
  const image = artUrl(data.image);
  const stats = statRows(data.stats, t);
  return (
    <div className="card-hover-panel">
      <div className="ch-header">
        {data.rarity && (
          <span
            className="ch-rarity"
            style={{ color: RARITY_COLOR[data.rarity] ?? "#8a8a8a" }}
          >
            {data.rarity.toUpperCase()}
          </span>
        )}
        <span
          className="card-name"
          style={{ color: cardNameColor(data.colors) }}
        >
          {data.name}
        </span>
      </div>
      <div className="ch-body">
        {image && <img className="ch-image" src={image} alt={data.name} />}
        {(stats.length > 0 ||
          data.deckColors.length > 0 ||
          data.tags.length > 0) && (
          <div className="ch-info">
            {stats.length > 0 && (
              <>
                <div className="ch-section">{t("hover.globalPerformance")}</div>
                <dl className="ch-grid">
                  {stats.flatMap((s) => [
                    <dt key={`${s.label}-t`} className={s.cls}>
                      {s.label}
                    </dt>,
                    <dd key={`${s.label}-v`} className={s.cls}>
                      {s.value}
                    </dd>,
                  ])}
                </dl>
              </>
            )}
            {data.deckColors.length > 0 && (
              <>
                <div className="ch-section">{t("hover.archetypeShare")}</div>
                <div className="ch-archetype">
                  {data.deckColors.map((d) => (
                    <div
                      key={d.color}
                      className={d.gihwr != null && d.gihwr >= 55 ? "up" : ""}
                    >
                      • {COLOR_NAMES[d.color] ?? d.color} ({d.color}):{" "}
                      {d.gihwr?.toFixed(1) ?? "—"}% WR
                    </div>
                  ))}
                </div>
              </>
            )}
            {data.tags.length > 0 && (
              <>
                <div className="ch-section">{t("hover.cardRoles")}</div>
                <div className="ch-tags">
                  {data.tags.map((t) => (
                    <span key={t}>{TAG_ICONS[t] ?? t}</span>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
