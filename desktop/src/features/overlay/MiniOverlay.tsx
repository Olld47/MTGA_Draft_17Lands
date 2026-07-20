import { useState } from "react";

import type { DraftState } from "../../api/types";
import { AdvisorPanel } from "../dashboard/AdvisorPanel";
import { PackTable } from "../dashboard/PackTable";
import { PoolSummaryStrip } from "../dashboard/PoolSummaryStrip";
import { SignalLedger } from "../dashboard/SignalLedger";

// The compact Mini Mode overlay — a dense, tabbed re-display of the live
// `DraftState` (Pack / Advisor / Stats / Pool), matching the four notebook
// tabs of the tkinter `CompactOverlay`. It renders the exact same data the
// full Dashboard consumes, so no extra bridge round-trip is needed.

type MiniTab = "pack" | "advisor" | "stats" | "pool";

const MINI_TABS: { id: MiniTab; label: string }[] = [
  { id: "pack", label: "Pack" },
  { id: "advisor", label: "Advisor" },
  { id: "stats", label: "Stats" },
  { id: "pool", label: "Pool" },
];

interface Props {
  state: DraftState | null;
  colorTint: boolean;
  live: boolean;
  onRestore: () => void;
  onDragStart: () => void;
}

export function MiniOverlay({
  state,
  colorTint,
  live,
  onRestore,
  onDragStart,
}: Props) {
  const [tab, setTab] = useState<MiniTab>("pack");

  const recommendations = (state?.packCards ?? [])
    .map((c) => c.recommendation)
    .filter((r): r is NonNullable<typeof r> => r != null);

  return (
    <div className="mini-overlay">
      <header
        className="mini-header"
        onMouseDown={onDragStart}
        title="Drag to move"
      >
        <span className="mini-info">
          {state?.eventString || "Waiting..."} · {state?.filterLabel ?? ""}
        </span>
        <span className="spacer" />
        {state && state.pack > 0 && (
          <span className="mini-status">
            P{state.pack}/P{state.pick}
          </span>
        )}
        <span
          className={`status-dot${live ? " live" : ""}`}
          title={live ? "Arena log is live" : "Arena log idle"}
        />
        <button
          className="mini-btn"
          onClick={onRestore}
          onMouseDown={(e) => e.stopPropagation()}
          title="Restore full window"
        >
          ⤢
        </button>
      </header>

      <nav className="mini-tabs">
        {MINI_TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="mini-body">
        {!state ? (
          <div className="empty-state">Waiting for draft data...</div>
        ) : tab === "pack" ? (
          <>
            <PackTable cards={state.packCards} colorTint={colorTint} />
            {state.missingCards.length > 0 && (
              <details className="disclosure">
                <summary>Seen · wheel ({state.missingCards.length})</summary>
                <PackTable
                  cards={state.missingCards}
                  colorTint={colorTint}
                  emptyText="No seen cards"
                />
              </details>
            )}
          </>
        ) : tab === "advisor" ? (
          <AdvisorPanel recommendations={recommendations} />
        ) : tab === "stats" ? (
          <div className="mini-stats">
            <h3>Open lanes</h3>
            <SignalLedger scores={state.signals.scores} />
            {state.poolSummary && state.poolSummary.cardCount > 0 && (
              <>
                <h3>Pool balance</h3>
                <PoolSummaryStrip summary={state.poolSummary} />
              </>
            )}
          </div>
        ) : (
          <PoolSummaryStrip summary={state.poolSummary} />
        )}
      </div>
    </div>
  );
}
