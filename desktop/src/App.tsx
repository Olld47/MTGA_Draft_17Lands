import { useEffect, useState } from "react";

import { forceReload, getBootStatus } from "./api/client";
import {
  EVENTS,
  on,
  type AppErrorPayload,
  type BootCompletePayload,
  type BootErrorPayload,
  type BootProgressPayload,
  type HeartbeatPayload,
} from "./api/events";
import { useDraftState } from "./state/useDraftState";
import { useSettings } from "./state/useSettings";
import { useMiniMode } from "./state/useMiniMode";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { MiniOverlay } from "./features/overlay/MiniOverlay";
import { TakenPage } from "./features/taken/TakenPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { DatasetsPage } from "./features/datasets/DatasetsPage";
import { RecapPage } from "./features/recap/RecapPage";
import { DeckPage } from "./features/deck/DeckPage";
import { SealedPage } from "./features/sealed/SealedPage";
import { ComparePage } from "./features/compare/ComparePage";
import { TiersPage } from "./features/tiers/TiersPage";

type Tab =
  | "draft"
  | "taken"
  | "recap"
  | "deck"
  | "sealed"
  | "compare"
  | "tiers"
  | "datasets"
  | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "draft", label: "Draft" },
  { id: "taken", label: "Taken" },
  { id: "recap", label: "Recap" },
  { id: "deck", label: "Deck" },
  { id: "sealed", label: "Sealed" },
  { id: "compare", label: "Compare" },
  { id: "tiers", label: "Tiers" },
  { id: "datasets", label: "Datasets" },
  { id: "settings", label: "Settings" },
];

function BootScreen({ message, error }: { message: string; error: string }) {
  return (
    <div className="boot-screen">
      <h1>MTGA Draft Tool</h1>
      {error ? (
        <>
          <div className="boot-error">{error}</div>
          <button onClick={() => window.location.reload()}>Retry</button>
        </>
      ) : (
        <div className="boot-log">{message || "Starting..."}</div>
      )}
    </div>
  );
}

export default function App() {
  const [booted, setBooted] = useState(false);
  const [bootMessage, setBootMessage] = useState("");
  const [bootError, setBootError] = useState("");
  const [tab, setTab] = useState<Tab>("draft");
  const [live, setLive] = useState(false);
  const [appError, setAppError] = useState("");

  const { state, statusText } = useDraftState(booted);
  const { settings } = useSettings();
  const { mini, toggle: toggleMini, startDragging } = useMiniMode();

  // Boot lifecycle
  useEffect(() => {
    // Recover state if the webview reloaded after boot finished
    getBootStatus()
      .then((s) => {
        if (s.booted) setBooted(true);
        if (s.error) setBootError(s.error);
        setBootMessage(s.lastMessage);
      })
      .catch(() => {});

    const unlisteners = [
      on<BootProgressPayload>(EVENTS.bootProgress, (p) =>
        setBootMessage(p.message),
      ),
      on<BootCompletePayload>(EVENTS.bootComplete, (p) => {
        setBooted(true);
        if (p.foundDraft && !p.hasDataset) setTab("datasets");
      }),
      on<BootErrorPayload>(EVENTS.bootError, (p) => setBootError(p.message)),
      on<AppErrorPayload>(EVENTS.appError, (p) => {
        setAppError(p.message);
        setTimeout(() => setAppError(""), 8000);
      }),
    ];
    return () => {
      unlisteners.forEach((u) => u.then((f) => f()));
    };
  }, []);

  // Heartbeat → live dot (log written to within the last 60s)
  useEffect(() => {
    const un = on<HeartbeatPayload>(EVENTS.draftHeartbeat, (p) => {
      setLive(Date.now() / 1000 - p.logMtime < 60);
    });
    return () => {
      un.then((f) => f());
    };
  }, []);

  if (!booted) {
    return <BootScreen message={bootMessage} error={bootError} />;
  }

  const missingSet =
    state && state.eventSet && !state.datasetName ? state.eventSet : undefined;
  const colorTint = settings?.cardColorsEnabled ?? false;

  if (mini) {
    return (
      <MiniOverlay
        state={state}
        colorTint={colorTint}
        live={live}
        onRestore={toggleMini}
        onDragStart={startDragging}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="masthead">
        <span className="event-name">
          {state?.eventString || "No active draft"}
        </span>
        {state && state.pack > 0 && (
          <span className="pack-pick">
            P{state.pack} · P{state.pick}
          </span>
        )}
        <span className="spacer" />
        {state && (
          <button
            className="filter-pill"
            title="Active deck-color filter"
            onClick={() => setTab("settings")}
          >
            {state.filterLabel}
          </button>
        )}
        <span
          className={`status-dot${live ? " live" : ""}`}
          title={live ? "Arena log is live" : "Arena log idle"}
        />
        <span className="status-text">{statusText}</span>
        <button onClick={() => toggleMini()} title="Shrink to always-on-top Mini Mode">
          Mini
        </button>
        <button onClick={() => forceReload()} title="Deep-rescan the Arena log">
          Rescan
        </button>
      </header>

      <nav className="tab-strip">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="tab-body">
        {tab === "draft" &&
          (state ? (
            <DashboardPage state={state} colorTint={colorTint} />
          ) : (
            <div className="empty-state">Waiting for draft data...</div>
          ))}
        {tab === "taken" && <TakenPage colorTint={colorTint} />}
        {tab === "recap" && <RecapPage />}
        {tab === "deck" && <DeckPage colorTint={colorTint} />}
        {tab === "sealed" && <SealedPage colorTint={colorTint} />}
        {tab === "compare" && <ComparePage colorTint={colorTint} />}
        {tab === "tiers" && <TiersPage />}
        {tab === "datasets" && <DatasetsPage missingSet={missingSet} />}
        {tab === "settings" && <SettingsPage />}
      </main>

      {appError && <div className="error-toast">{appError}</div>}
    </div>
  );
}
