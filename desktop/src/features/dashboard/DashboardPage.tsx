import type { DraftState } from "../../api/types";
import { AdvisorPanel } from "./AdvisorPanel";
import { PackTable } from "./PackTable";
import { PoolSummaryStrip } from "./PoolSummaryStrip";
import { ManaCurveChart } from "./ManaCurveChart";
import { PoolBalanceChart } from "./PoolBalanceChart";
import { SignalLedger } from "./SignalLedger";

interface Props {
  state: DraftState;
  colorTint: boolean;
  /** Ideal mid-range mana curve from Settings.deckMidDistribution. */
  idealCurve?: number[];
}

export function DashboardPage({ state, colorTint, idealCurve = [] }: Props) {
  const recommendations = state.packCards
    .map((c) => c.recommendation)
    .filter((r): r is NonNullable<typeof r> => r != null);

  return (
    <div className="dashboard">
      <div className="main-col" style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
        <section className="panel">
          <h2>Pack ({state.packCards.length})</h2>
          <PackTable cards={state.packCards} colorTint={colorTint} />
        </section>

        {state.missingCards.length > 0 && (
          <details className="disclosure panel">
            <summary>Missing ({state.missingCards.length})</summary>
            <PackTable
              cards={state.missingCards}
              colorTint={colorTint}
              viewId="missing_table"
              defaultSort={{ id: "gihwr", desc: true }}
              emptyText="No missing cards"
            />
          </details>
        )}

        {state.poolSummary && state.poolSummary.cardCount > 0 && (
          <section className="panel">
            <h2>Pool</h2>
            <PoolSummaryStrip summary={state.poolSummary} />
            <div className="pool-charts">
              <div className="pool-chart">
                <span className="pool-chart-title">Mana curve</span>
                <ManaCurveChart
                  distribution={state.poolSummary.cmcDistribution}
                  ideal={idealCurve}
                />
              </div>
              <div className="pool-chart">
                <span className="pool-chart-title">Pool balance</span>
                <PoolBalanceChart counts={state.poolSummary.typeCounts ?? {}} />
              </div>
            </div>
          </section>
        )}
      </div>

      <aside className="rail">
        <section className="panel">
          <h2>Advisor</h2>
          <AdvisorPanel recommendations={recommendations} />
        </section>
        <section className="panel">
          <h2>Signals</h2>
          <SignalLedger scores={state.signals.scores} />
        </section>
      </aside>
    </div>
  );
}
