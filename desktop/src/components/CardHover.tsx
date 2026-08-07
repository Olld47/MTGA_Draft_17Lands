import type { Card, DeckRow } from "../api/types";
import {
  artUrl,
  cardNameColor,
  RARITY_COLOR,
  TAG_ICONS,
} from "./cardColumns";

/** Data the hover tooltip renders for a row — a TS port of the legacy
 *  CardToolTip (src/ui/components.py): name + colored rarity header, the card
 *  art, a GLOBAL PERFORMANCE stat block, and CARD ROLES from the advisor tags.
 *  The legacy ARCHETYPE PLAY SHARE section is intentionally absent: per-color
 *  stats never crossed the IPC boundary, so there is no data to render. */
export interface CardHoverData {
  name: string;
  rarity: string;
  colors: string[];
  image: string[];
  /** "All Decks" performance. Deck rows ship only a single GIH WR, so the
   *  stats are mostly null there — the panel renders just the available rows. */
  stats: {
    gihwr: number | null;
    iwd: number | null;
    alsa: number | null;
    ata: number | null;
    games: number | null;
  };
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
    tags: card.recommendation?.tags ?? [],
  };
}

export function hoverDataFromDeckRow(row: DeckRow): CardHoverData {
  return {
    name: row.name,
    rarity: row.rarity,
    colors: row.colors,
    image: row.image,
    stats: { gihwr: row.gihwr, iwd: null, alsa: null, ata: null, games: null },
    tags: [],
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

function statRows(stats: CardHoverData["stats"]): StatRow[] {
  const rows: StatRow[] = [];
  if (stats.gihwr != null) {
    rows.push({
      label: "GIH WR",
      value: fmtPct(stats.gihwr),
      cls: stats.gihwr >= 55 ? "up" : undefined,
    });
  }
  if (stats.iwd != null) {
    rows.push({
      label: "IWD",
      value: fmtSigned(stats.iwd),
      cls: stats.iwd >= 3 ? "accent" : undefined,
    });
  }
  if (stats.alsa != null) rows.push({ label: "ALSA", value: stats.alsa.toFixed(1) });
  if (stats.ata != null) rows.push({ label: "ATA", value: stats.ata.toFixed(1) });
  if (stats.games != null) rows.push({ label: "Games", value: fmtGames(stats.games) });
  return rows;
}

/** Cursor-following hover card: art + the legacy CardToolTip stat panel.
 *  Rendered by DataTable when `hoverContent` is wired (pack / taken / deck). */
export function CardHoverTip({ data }: { data: CardHoverData }) {
  const image = artUrl(data.image);
  const stats = statRows(data.stats);
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
        {(stats.length > 0 || data.tags.length > 0) && (
          <div className="ch-info">
            {stats.length > 0 && (
              <>
                <div className="ch-section">GLOBAL PERFORMANCE</div>
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
            {data.tags.length > 0 && (
              <>
                <div className="ch-section">CARD ROLES</div>
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
