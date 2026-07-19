import type { Recommendation } from "../../api/types";

interface Props {
  recommendations: Recommendation[];
}

/** Top-3 advisor picks with reasoning chips. */
export function AdvisorPanel({ recommendations }: Props) {
  const top = [...recommendations]
    .sort((a, b) => b.contextualScore - a.contextualScore)
    .slice(0, 3);

  if (top.length === 0) {
    return <div className="empty-state">Advice appears with the next pack</div>;
  }

  return (
    <div>
      {top.map((rec, i) => (
        <div
          key={rec.cardName}
          className={`advisor-rec${rec.isElite ? " elite" : ""}`}
        >
          <div className="rec-head">
            <span className="rec-rank">{i + 1}.</span>
            <span className="rec-name">{rec.cardName}</span>
            <span className="rec-score">
              {rec.contextualScore.toFixed(0)}
            </span>
          </div>
          {rec.reasoning.length > 0 && (
            <div className="reason-chips">
              {rec.reasoning.slice(0, 4).map((r) => (
                <span key={r}>{r}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
