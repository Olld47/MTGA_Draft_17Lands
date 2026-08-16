import type { Recommendation } from "../../api/types";
import { tagChip } from "../../components/cardColumns";
import { useLanguage } from "../../i18n/useLanguage";
import { localizeReason } from "./advisorReasons";

interface Props {
  recommendations: Recommendation[];
  /** Max recommendations shown. The dashboard shows 3 (legacy advisor_view.py
   *  default); the mini overlay shows 5 (legacy overlay mini_mode limit). */
  limit?: number;
}

/** Top-`limit` advisor picks with reasoning chips and card-role tags. */
export function AdvisorPanel({ recommendations, limit = 3 }: Props) {
  const { t, lang } = useLanguage();
  const top = [...recommendations]
    .sort((a, b) => b.contextualScore - a.contextualScore)
    .slice(0, limit);

  if (top.length === 0) {
    return <div className="empty-state">{t("dash.adviceNextPack")}</div>;
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
              {rec.isElite ? ` +${rec.zScore}σ` : ""}
            </span>
          </div>
          {rec.reasoning.length > 0 && (
            <div className="reason-chips">
              {rec.reasoning.map((r) => (
                <span key={r}>{localizeReason(r, lang)}</span>
              ))}
            </div>
          )}
          {rec.tags.length > 0 && (
            <div className="rec-tags">
              {rec.tags.map((tag) => (
                <span key={tag}>{tagChip(tag, lang, t)}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
