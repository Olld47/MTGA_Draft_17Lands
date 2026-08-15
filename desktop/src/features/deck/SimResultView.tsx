import type { SimResult } from "../../api/types";
import { useLanguage } from "../../i18n/useLanguage";

const pct = (v: number) => `${v.toFixed(1)}%`;

type Grade = "Great" | "Fair" | "Poor";

const GRADE_ICON: Record<Grade, string> = { Great: "🟢", Fair: "🟡", Poor: "🔴" };
const GRADE_CLASS: Record<Grade, string> = {
  Great: "great",
  Fair: "fair",
  Poor: "poor",
};

/** Port of legacy _add_stat (custom_deck.py:575 / suggest_deck.py:427): a
 *  metric is Great above `good`, Fair above `fair`, Poor otherwise; reverse
 *  metrics grade lower-is-better. Thresholds match the legacy calls exactly. */
function gradeOf(
  value: number,
  good: number,
  fair: number,
  reverse = false,
): Grade {
  if (reverse) {
    if (value <= good) return "Great";
    if (value <= fair) return "Fair";
    return "Poor";
  }
  if (value >= good) return "Great";
  if (value >= fair) return "Fair";
  return "Poor";
}

interface Metric {
  label: string;
  value: number;
  /** When absent the row renders value-only (legacy has no threshold for
   *  Flood T5, which the desktop added beyond the legacy set). */
  thresholds?: [number, number];
  reverse?: boolean;
  percent?: boolean;
}

function MetricRow({ m }: { m: Metric }) {
  const { t } = useLanguage();
  const grade = m.thresholds
    ? gradeOf(m.value, m.thresholds[0], m.thresholds[1], m.reverse)
    : null;
  return (
    <tr>
      <td>{m.label}</td>
      <td className="num">
        {m.percent === false ? m.value.toFixed(2) : pct(m.value)}
      </td>
      {grade ? (
        <td
          className={`sim-grade ${GRADE_CLASS[grade]}`}
          title={t(`sim.${grade.toLowerCase()}`)}
        >
          {GRADE_ICON[grade]} {t(`sim.${grade.toLowerCase()}`)}
        </td>
      ) : (
        <td />
      )}
    </tr>
  );
}

function MetricSection({
  title,
  metrics,
}: {
  title: string;
  metrics: Metric[];
}) {
  return (
    <>
      <tr className="sim-section">
        <td colSpan={3}>{title}</td>
      </tr>
      {metrics.map((m) => (
        <MetricRow key={m.label} m={m} />
      ))}
    </>
  );
}

/** Monte-Carlo simulation results + advisor heuristics, graded Great/Fair/Poor
 *  per metric exactly as the legacy custom-deck and suggest-deck panels did.
 *  Shared by the Custom Deck and Suggest pages. */
export function SimResultView({ result }: { result: SimResult }) {
  const { t } = useLanguage();
  if (!result.ok || !result.stats) {
    return (
      <section className="panel">
        <h2>{t("sim.title")}</h2>
        <div className="empty-inline">
          {result.message || t("sim.noResult")}
        </div>
      </section>
    );
  }
  const s = result.stats;
  return (
    <section className="panel">
      <h2>{t("sim.title")}</h2>
      {result.optimizationNote && (
        <div className="sim-note">{result.optimizationNote}</div>
      )}
      <table className="sim-table">
        <tbody>
          <MetricSection
            title={t("sim.consistency")}
            metrics={[
              { label: t("sim.t2Play"), value: s.castT2, thresholds: [65, 50] },
              { label: t("sim.t3Play"), value: s.castT3, thresholds: [65, 50] },
              { label: t("sim.t4Play"), value: s.castT4, thresholds: [55, 40] },
              {
                label: t("sim.perfectCurve"),
                value: s.curveOut,
                thresholds: [25, 15],
              },
              { label: t("sim.removalByT4"), value: s.removalT4, thresholds: [60, 45] },
            ]}
          />
          <MetricSection
            title={t("sim.risk")}
            metrics={[
              {
                label: t("sim.mulligans"),
                value: s.mulligans,
                thresholds: [15, 25],
                reverse: true,
              },
              {
                label: t("sim.avgHandSize"),
                value: s.avgHandSize,
                thresholds: [6.8, 6.5],
                percent: false,
              },
              {
                label: t("sim.missed3rdLand"),
                value: s.screwT3,
                thresholds: [15, 25],
                reverse: true,
              },
              {
                label: t("sim.missed4thLand"),
                value: s.screwT4,
                thresholds: [25, 35],
                reverse: true,
              },
              {
                label: t("sim.colorScrewed"),
                value: s.colorScrewT3,
                thresholds: [6, 12],
                reverse: true,
              },
              { label: t("sim.floodByT5"), value: s.floodT5 },
            ]}
          />
        </tbody>
      </table>
      {result.advice.length > 0 && (
        <ul className="sim-advice">
          {result.advice.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
