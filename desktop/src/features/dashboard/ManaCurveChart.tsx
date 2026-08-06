// ManaCurveChart — the pool's mana curve as 7 columns (CMC 0…6+) with a dashed
// "ideal" overlay from the mid-range deck config. Port of the legacy
// ManaCurvePlot (src/ui/components.py): a bar above the ideal by more than one
// is "over", a bar below it is "under", at/above target is "ok".

interface Props {
  /** 8 buckets straight from PoolSummary.cmcDistribution. */
  distribution: number[];
  /** 7 ideal buckets from Settings.deckMidDistribution. */
  ideal: number[];
}

export function ManaCurveChart({ distribution, ideal }: Props) {
  const current = [
    ...distribution.slice(0, 6),
    distribution.slice(6).reduce((a, b) => a + b, 0),
  ];
  const ideal7 = ideal.slice(0, 7);
  while (ideal7.length < 7) ideal7.push(0);

  const maxVal = Math.max(...current, ...ideal7, 5);

  return (
    <div className="mana-curve" aria-label="Mana curve">
      {current.map((count, i) => {
        const target = ideal7[i];
        const cls =
          count > target + 1 ? "over" : count < target && target > 0 ? "under" : "ok";
        return (
          <div key={i} className="curve-col">
            <div className="curve-bar-wrap">
              <span
                className={`curve-bar ${cls}`}
                style={{ height: `${(count / maxVal) * 100}%` }}
                title={`CMC ${i}: ${count} (ideal ${target})`}
              />
              {target > 0 && (
                <span
                  className="curve-ideal"
                  style={{ height: `${(target / maxVal) * 100}%` }}
                  title={`CMC ${i}: ideal ${target}`}
                />
              )}
            </div>
            <span className="curve-value">{count > 0 ? count : ""}</span>
            <span className="curve-label">{i === 6 ? "6+" : i}</span>
          </div>
        );
      })}
    </div>
  );
}
