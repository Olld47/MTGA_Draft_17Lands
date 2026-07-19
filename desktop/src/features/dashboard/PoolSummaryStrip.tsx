import type { PoolSummary } from "../../api/types";

const PIP_ORDER = ["W", "U", "B", "R", "G"] as const;

export function PoolSummaryStrip({ summary }: { summary: PoolSummary | null }) {
  if (!summary || summary.cardCount === 0) {
    return null;
  }
  const maxBucket = Math.max(...summary.cmcDistribution, 1);
  return (
    <div className="pool-strip">
      <span>
        {summary.cardCount} cards · {summary.creatureCount} creatures ·{" "}
        {summary.noncreatureCount} spells
      </span>
      <span className="curve" aria-label="Mana curve">
        {summary.cmcDistribution.map((n, i) => (
          <i
            key={i}
            style={{ height: `${Math.max(9, (n / maxBucket) * 100)}%` }}
            title={`CMC ${i}${i === 7 ? "+" : ""}: ${n}`}
          />
        ))}
      </span>
      <span>avg {summary.cmcAverage.toFixed(1)}</span>
      <span className="pips">
        {PIP_ORDER.filter((c) => (summary.colorPips[c] ?? 0) > 0).map((c) => (
          <span key={c} className={c.toLowerCase()}>
            {c}
            {summary.colorPips[c]}
          </span>
        ))}
      </span>
    </div>
  );
}
