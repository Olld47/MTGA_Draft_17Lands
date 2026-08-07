import type { PoolSummary } from "../../api/types";
import { useLanguage } from "../../i18n/useLanguage";

const PIP_ORDER = ["W", "U", "B", "R", "G"] as const;

export function PoolSummaryStrip({ summary }: { summary: PoolSummary | null }) {
  const { t } = useLanguage();
  if (!summary || summary.cardCount === 0) {
    return null;
  }
  const maxBucket = Math.max(...summary.cmcDistribution, 1);
  return (
    <div className="pool-strip">
      <span>
        {t("dash.summary", {
          cards: summary.cardCount,
          creatures: summary.creatureCount,
          spells: summary.noncreatureCount,
        })}
      </span>
      <span className="curve" aria-label={t("dash.manaCurve")}>
        {summary.cmcDistribution.map((n, i) => (
          <i
            key={i}
            style={{ height: `${Math.max(9, (n / maxBucket) * 100)}%` }}
            title={t("dash.curveTooltip", {
              i,
              plus: i === 7 ? "+" : "",
              n,
            })}
          />
        ))}
      </span>
      <span>{t("dash.avg", { n: summary.cmcAverage.toFixed(1) })}</span>
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
