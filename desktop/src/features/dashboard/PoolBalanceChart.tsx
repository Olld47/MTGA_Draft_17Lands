// PoolBalanceChart — per-type pool breakdown as a donut pie + legend. Port of
// the legacy TypePieChart (src/ui/components.py). Types follow the legacy
// priority order (Creature → … → Land); basic lands are excluded upstream.

// One entry per non-zero type, in the order PoolSummaryVM.typeCounts ships.
interface Props {
  counts: Record<string, number>;
}

const TYPE_COLORS: Record<string, string> = {
  Creature: "var(--ok)",
  Instant: "var(--mana-u)",
  Sorcery: "var(--err)",
  Enchantment: "#a855f7",
  Artifact: "var(--gold-foil)",
  Planeswalker: "#14b8a6",
  Battle: "#ec4899",
  Land: "var(--gruff)",
};

export function PoolBalanceChart({ counts }: Props) {
  const entries = Object.entries(counts).filter(([, n]) => n > 0);
  const total = entries.reduce((sum, [, n]) => sum + n, 0);
  if (total === 0) return null;

  // conic-gradient needs cumulative percentages, e.g. "green 0 40%, blue 40 60%"
  let acc = 0;
  const stops = entries.map(([type, n]) => {
    const from = acc;
    acc += (n / total) * 100;
    const color = TYPE_COLORS[type] ?? "var(--gruff)";
    return `${color} ${from}% ${acc}%`;
  });

  return (
    <div className="pool-balance">
      <div
        className="pool-balance-pie"
        style={{ background: `conic-gradient(${stops.join(", ")})` }}
        role="img"
        aria-label="Pool type balance"
      />
      <ul className="pool-balance-legend">
        {entries.map(([type, n]) => (
          <li key={type}>
            <i style={{ background: TYPE_COLORS[type] ?? "var(--gruff)" }} />
            {type}: <b>{n}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
