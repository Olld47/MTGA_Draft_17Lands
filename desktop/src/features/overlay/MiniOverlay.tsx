import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

import type { DraftState } from "../../api/types";
import { DatasetSwitcher } from "../../components/DatasetSwitcher";
import { AdvisorPanel } from "../dashboard/AdvisorPanel";
import { ManaCurveChart } from "../dashboard/ManaCurveChart";
import { PackTable } from "../dashboard/PackTable";
import { PoolSummaryStrip } from "../dashboard/PoolSummaryStrip";
import { SignalLedger } from "../dashboard/SignalLedger";
import { useDatasetSwitcher } from "../../state/useDatasetSwitcher";
import { useFilterOptions } from "../../state/useFilterOptions";
import { useMiniMode } from "../../state/useMiniMode";
import { useSettings } from "../../state/useSettings";
import { navigateTab } from "../../state/navigation";

// The compact Mini Mode overlay — a dense, tabbed re-display of the live
// `DraftState` (Pack / Advisor / Stats / Pool), matching the four notebook
// tabs of the tkinter `CompactOverlay`. It renders the exact same data the
// full Dashboard consumes, so no extra bridge round-trip is needed. The ⚙ gear
// in the header is the port of the legacy `_show_settings_menu`: Colors
// (Filter), Event Type / User Group (via the shared DatasetSwitcher), and
// Preferences (which restores the full window onto the Settings tab).

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
  /** Ideal mid-range mana curve from Settings.deckMidDistribution. */
  idealCurve?: number[];
  onRestore: () => void;
  onDragStart: () => void;
}

export function MiniOverlay({
  state,
  colorTint,
  live,
  idealCurve = [],
  onRestore,
  onDragStart,
}: Props) {
  const [tab, setTab] = useState<MiniTab>("pack");
  const [gearOpen, setGearOpen] = useState(false);
  const { settings, patch } = useSettings();
  const { switcher } = useDatasetSwitcher();
  const filters = useFilterOptions(settings?.filterFormat);
  const { resizeOverlay } = useMiniMode();

  const recommendations = (state?.packCards ?? [])
    .map((c) => c.recommendation)
    .filter((r): r is NonNullable<typeof r> => r != null);

  // Close the gear popover on outside-click or Escape (the tkinter Menu
  // grabbed the app while open; a mousedown outside is the close equivalent).
  const gearRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!gearOpen) return;
    const onDown = (e: MouseEvent) => {
      if (gearRef.current && !gearRef.current.contains(e.target as Node)) {
        setGearOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setGearOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [gearOpen]);

  // Footer resize grip — the port of CompactOverlay._start/_do/_stop_resize:
  // drag from the bottom-right corner to grow the overlay; the live geometry
  // saver in useMiniMode persists the new size.
  const resizeStart = useRef<{ w: number; h: number; x: number; y: number } | null>(
    null,
  );
  const onResizeDown = (e: ReactMouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    resizeStart.current = {
      w: window.innerWidth,
      h: window.innerHeight,
      x: e.screenX,
      y: e.screenY,
    };
    const onMove = (ev: MouseEvent) => {
      const start = resizeStart.current;
      if (!start) return;
      const width = Math.max(250, start.w + (ev.screenX - start.x));
      const height = Math.max(200, start.h + (ev.screenY - start.y));
      void resizeOverlay(width, height);
    };
    const onUp = () => {
      resizeStart.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const filterOptions =
    filters?.options && filters.options.length > 0
      ? filters.options
      : [
          {
            key: settings?.deckFilter ?? "Auto",
            label: settings?.deckFilter ?? "Auto",
            winRate: null as number | null,
          },
        ];

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
        <div className="mini-gear-wrap" ref={gearRef}>
          <button
            className={`mini-btn${gearOpen ? " active" : ""}`}
            onClick={() => setGearOpen((o) => !o)}
            onMouseDown={(e) => e.stopPropagation()}
            title="Overlay settings"
          >
            ⚙
          </button>
          {gearOpen && (
            <div className="mini-gear">
              <label className="mini-gear-row">
                <span>Colors</span>
                <select
                  value={settings?.deckFilter ?? "Auto"}
                  onChange={(e) => patch({ deckFilter: e.target.value })}
                >
                  {filterOptions.map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.winRate != null ? `${f.label} (${f.winRate}%)` : f.label}
                    </option>
                  ))}
                </select>
              </label>
              {switcher.events.length > 0 && (
                <div className="mini-gear-row">
                  <span>Dataset</span>
                  <DatasetSwitcher switcher={switcher} />
                </div>
              )}
              <button
                className="ghost-btn mini-gear-prefs"
                onClick={() => {
                  setGearOpen(false);
                  navigateTab("settings");
                  onRestore();
                }}
              >
                Preferences…
              </button>
            </div>
          )}
        </div>
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
            <PackTable
              cards={state.packCards}
              colorTint={colorTint}
              viewId="overlay_table"
            />
            {state.missingCards.length > 0 && (
              <details className="disclosure">
                <summary>Seen · wheel ({state.missingCards.length})</summary>
                <PackTable
                  cards={state.missingCards}
                  colorTint={colorTint}
                  viewId="missing_table"
                  emptyText="No seen cards"
                />
              </details>
            )}
          </>
        ) : tab === "advisor" ? (
          <AdvisorPanel recommendations={recommendations} limit={5} />
        ) : tab === "stats" ? (
          <div className="mini-stats">
            <h3>Open lanes</h3>
            <SignalLedger scores={state.signals.scores} />
            {state.poolSummary && state.poolSummary.cardCount > 0 && (
              <>
                <h3>Mana curve</h3>
                <ManaCurveChart
                  distribution={state.poolSummary.cmcDistribution}
                  ideal={idealCurve}
                />
                <h3>Pool balance</h3>
                <PoolSummaryStrip summary={state.poolSummary} />
              </>
            )}
          </div>
        ) : (
          <PoolSummaryStrip summary={state.poolSummary} />
        )}
      </div>

      <footer className="mini-footer">
        <span
          className="mini-grip"
          onMouseDown={onResizeDown}
          title="Drag to resize"
        >
          ⇲
        </span>
      </footer>
    </div>
  );
}
