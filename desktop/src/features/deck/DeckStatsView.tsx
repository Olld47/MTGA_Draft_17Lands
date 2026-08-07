import type { DeckRow, DeckStats } from "../../api/types";
import { artUrl, cardNameColor, formatWinRate } from "../../components/cardColumns";
import { useCardMenu } from "../../components/CardContextMenu";
import { ManaCost } from "../../components/ManaCost";
import { DataTable, type Column } from "../../components/DataTable";
import { useStatFormat } from "../../state/useStatFormat";

const PIP_CLASS: Record<string, string> = {
  W: "w",
  U: "u",
  B: "b",
  R: "r",
  G: "g",
};

/** Curve histogram + pips + tribes/tags, shared by the custom-deck and sealed
 *  pages (both consume the identical DeckStats view-model). */
export function DeckStatsView({ stats }: { stats: DeckStats }) {
  const maxCurve = Math.max(1, ...Object.values(stats.curve));
  return (
    <div className="deck-stats">
      <div className="deck-stat-tiles">
        <span>
          <b>{stats.totalCards}</b> cards
        </span>
        <span>
          <b>{stats.creatures}</b> creatures
        </span>
        <span>
          <b>{stats.noncreatures}</b> spells
        </span>
        <span>
          <b>{stats.lands}</b> lands
        </span>
        <span>
          <b>{stats.avgCmc.toFixed(2)}</b> avg CMC
        </span>
      </div>

      <div className="deck-curve">
        {Object.entries(stats.curve).map(([cmc, n]) => (
          <div key={cmc} className="curve-col">
            <i style={{ height: `${(n / maxCurve) * 100}%` }} title={`${n} card(s)`} />
            <span className="curve-label">{cmc}</span>
          </div>
        ))}
      </div>

      {stats.pips.length > 0 && (
        <div className="deck-pips">
          {stats.pips.map((p) => (
            <span key={p.symbol} className={`pip-count ${PIP_CLASS[p.symbol] ?? "c"}`}>
              {p.symbol} {p.count}
            </span>
          ))}
        </div>
      )}

      {stats.tags.length > 0 && (
        <div className="recap-chips">
          {stats.tags.map((t) => (
            <span key={t.label}>
              {t.label} <b>{t.count}</b>
            </span>
          ))}
        </div>
      )}

      {stats.tribes.length > 0 && (
        <div className="deck-tribes">
          <span className="stat-label">Top Tribes:</span>
          <div className="recap-chips">
            {stats.tribes.map((t) => (
              <span key={t.label}>
                {t.label} <b>{t.count}</b>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface DeckTableProps {
  title: string;
  rows: DeckRow[];
  count: number;
  /** When set, annotate the header with the legacy smart-deck-size cue:
   *  "✔" at the target, "⚠️ ADD N" below, "⚠️ CUT N" above. The Custom Deck and
   *  Sealed main tables pass 40; sideboard/pool tables leave it unset. */
  targetCount?: number;
  /** Move a card to the other zone (deck⇄sideboard). Omit for a read-only
   *  table (the suggest page renders decks it doesn't let you edit). */
  onMove?: (name: string) => void;
  moveLabel?: string;
  emptyText: string;
  colorTint: boolean;
  /** Custom Deck interaction: double-click a row to move it. Hides the
   *  move-button column — the legacy panel moved one copy per
   *  <Double-Button-1>. */
  dblClickMove?: boolean;
}

export function DeckTable({
  title,
  rows,
  count,
  targetCount,
  onMove,
  moveLabel,
  emptyText,
  colorTint,
  dblClickMove,
}: DeckTableProps) {
  const { resultFormat, metrics } = useStatFormat();
  const menu = useCardMenu();
  const columns: Column<DeckRow>[] = [
    {
      id: "count",
      header: "#",
      numeric: true,
      cell: (r) => r.count,
      sortValue: (r) => r.count,
    },
    {
      id: "name",
      header: "Card",
      cell: (r) => (
        <span className="card-name" style={{ color: cardNameColor(r.colors) }}>
          {r.name}
        </span>
      ),
      sortValue: (r) => r.name,
    },
    {
      id: "cost",
      header: "Cost",
      cell: (r) => <ManaCost cost={r.manaCost} />,
      sortValue: (r) => r.cmc,
    },
    {
      id: "gihwr",
      header: "GIHWR",
      numeric: true,
      cell: (r) =>
        formatWinRate(r.gihwr, r.colors, "gihwr", resultFormat, metrics),
      sortValue: (r) => r.gihwr ?? -1,
    },
  ];

  if (onMove && !dblClickMove) {
    columns.push({
      id: "move",
      header: "",
      cell: (r) => (
        <button className="ghost-btn" onClick={() => onMove(r.name)}>
          {moveLabel}
        </button>
      ),
    });
  }

  const rowClass = (r: DeckRow) =>
    colorTint && r.colors.length === 1
      ? `tint-${r.colors[0].toLowerCase()}`
      : colorTint && r.colors.length > 1
        ? "tint-multi"
        : "";

  return (
    <section className="panel">
      <h2>
        {title} ({count})
        {targetCount != null &&
          (count === targetCount ? (
            <span className="deck-complete"> ✔</span>
          ) : count > targetCount ? (
            <span className="deck-incomplete">
              {" "}
              ⚠️ CUT {count - targetCount}
            </span>
          ) : (
            <span className="deck-incomplete">
              {" "}
              ⚠️ ADD {targetCount - count}
            </span>
          ))}
      </h2>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.name}
        rowClass={rowClass}
        defaultSort={{ id: "cost", desc: false }}
        emptyText={emptyText}
        hoverImage={(r) => artUrl(r.image)}
        onRowDoubleClick={
          dblClickMove && onMove ? (r) => onMove(r.name) : undefined
        }
        onContextMenu={(r, x, y) => menu.open(r.name, x, y)}
      />
      {menu.element}
    </section>
  );
}
