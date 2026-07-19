import type { DraftState } from "../../api/types";
import { AdvisorPanel } from "./AdvisorPanel";
import { PackTable } from "./PackTable";
import { PoolSummaryStrip } from "./PoolSummaryStrip";
import { SignalLedger } from "./SignalLedger";

interface Props {
  state: DraftState;
  colorTint: boolean;
}

export function DashboardPage({ state, colorTint }: Props) {
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
              emptyText="No missing cards"
            />
          </details>
        )}

        {state.poolSummary && state.poolSummary.cardCount > 0 && (
          <section className="panel">
            <h2>Pool</h2>
            <PoolSummaryStrip summary={state.poolSummary} />
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
