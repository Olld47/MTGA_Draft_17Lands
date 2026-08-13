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
import { DatasetSwitcher } from "./components/DatasetSwitcher";
import { DatasetUpdateToast } from "./components/DatasetUpdateToast";
import { useDatasetSwitcher } from "./state/useDatasetSwitcher";
import { onNavigateTab } from "./state/navigation";
import { draftPhase } from "./state/draftPhase";
import { isSealedEvent } from "./state/sealedTab";
import { useDraftLogs } from "./state/useDraftLogs";
import { useSettings } from "./state/useSettings";
import { useMiniMode } from "./state/useMiniMode";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useLanguage } from "./i18n/useLanguage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { MiniOverlay } from "./features/overlay/MiniOverlay";
import { TakenPage } from "./features/taken/TakenPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { DatasetsPage } from "./features/datasets/DatasetsPage";
import { RecapPage } from "./features/recap/RecapPage";
import { DeckPage } from "./features/deck/DeckPage";
import { SuggestPage } from "./features/suggest/SuggestPage";
import { SealedPage } from "./features/sealed/SealedPage";
import { ComparePage } from "./features/compare/ComparePage";
import { TiersPage } from "./features/tiers/TiersPage";

type Tab =
  | "draft"
  | "taken"
  | "deck"
  | "suggest"
  | "sealed"
  | "compare"
  | "tiers"
  | "datasets"
  | "settings";

const TABS: { id: Tab; labelKey: string }[] = [
  { id: "draft", labelKey: "tab.draft" },
  { id: "taken", labelKey: "tab.taken" },
  { id: "deck", labelKey: "tab.deck" },
  { id: "suggest", labelKey: "tab.suggest" },
  { id: "sealed", labelKey: "tab.sealed" },
  { id: "compare", labelKey: "tab.compare" },
  { id: "tiers", labelKey: "tab.tiers" },
  { id: "datasets", labelKey: "tab.datasets" },
  { id: "settings", labelKey: "tab.settings" },
];

function BootScreen({ message, error }: { message: string; error: string }) {
  const { t } = useLanguage();
  return (
    <div className="boot-screen">
      <h1>MTGA Draft Tool</h1>
      {error ? (
        <>
          <div className="boot-error">{error}</div>
          <button onClick={() => window.location.reload()}>{t("boot.retry")}</button>
        </>
      ) : (
        <div className="boot-log">{message || t("boot.starting")}</div>
      )}
    </div>
  );
}

export default function App() {
  const { t } = useLanguage();
  const [booted, setBooted] = useState(false);
  const [bootMessage, setBootMessage] = useState("");
  const [bootError, setBootError] = useState("");
  const [tab, setTab] = useState<Tab>("draft");
  const [live, setLive] = useState(false);
  const [appError, setAppError] = useState("");

  const { state, statusText } = useDraftState(booted);
  const { settings, patch: patchSettings } = useSettings();
  const { mini, toggle: toggleMini, startDragging } = useMiniMode(
    settings?.overlayGeometry,
    (g) => patchSettings({ overlayGeometry: g }),
    settings?.alwaysOnTop ?? false,
  );
  const logs = useDraftLogs(booted, state?.logName ?? "");
  const { switcher } = useDatasetSwitcher();

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

  // Context-menu "Compare" navigates here from deep inside the table tree.
  useEffect(() => onNavigateTab((tab) => setTab(tab as Tab)), []);

  if (!booted) {
    return <BootScreen message={bootMessage} error={bootError} />;
  }

  const missingSet =
    state && state.eventSet && !state.datasetName ? state.eventSet : undefined;
  const colorTint = settings?.cardColorsEnabled ?? false;
  const phase = draftPhase(state);
  // The Sealed tab only belongs to a Sealed draft; hiding it for Premier /
  // Traditional / Quick drafts keeps the strip honest for the active log (live
  // or a loaded history log — state.eventType follows whichever is loaded).
  const sealedVisible = isSealedEvent(state?.eventType);
  const tabs = TABS.filter((t) => t.id !== "sealed" || sealedVisible);

  if (mini) {
    return (
      <MiniOverlay
        state={state}
        colorTint={colorTint}
        live={live}
        idealCurve={settings?.deckMidDistribution ?? []}
        onRestore={toggleMini}
        onDragStart={startDragging}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="masthead">
        <span className="event-name">
          {state?.eventString || t("masthead.noActiveDraft")}
        </span>
        {state && state.pack > 0 && (
          <span className="pack-pick">
            P{state.pack} · P{state.pick}
          </span>
        )}
        <DatasetSwitcher switcher={switcher} />
        <span className="spacer" />
        {logs.logs.length > 0 && (
          <select
            className="log-switcher"
            title={t("masthead.logSwitcherTitle")}
            value={logs.selected}
            disabled={logs.swapping}
            onChange={(e) => logs.select(e.target.value)}
          >
            {logs.logs.map((l) => (
              <option key={l.path} value={l.path}>
                {l.label}
              </option>
            ))}
          </select>
        )}
        {state && (
          <button
            className="filter-pill"
            title={t("masthead.filterTitle")}
            onClick={() => setTab("settings")}
          >
            {state.filterLabel}
          </button>
        )}
        <span
          className={`status-dot${live ? " live" : ""}`}
          title={live ? t("masthead.statusLive") : t("masthead.statusIdle")}
        />
        <span className="status-text">{statusText}</span>
        <button
          onClick={() => toggleMini()}
          title={t("masthead.miniTitle")}
        >
          {t("masthead.mini")}
        </button>
        <button onClick={() => forceReload()} title={t("masthead.rescanTitle")}>
          {t("masthead.rescan")}
        </button>
      </header>

      <nav className="tab-strip">
        {tabs.map((tabDef) => (
          <button
            key={tabDef.id}
            className={tab === tabDef.id ? "active" : ""}
            onClick={() => setTab(tabDef.id)}
          >
            {t(tabDef.labelKey)}
          </button>
        ))}
      </nav>

      <main className="tab-body">
        <ErrorBoundary resetKey={tab}>
          {tab === "draft" &&
            (phase === "recap" && state ? (
              // Full pool picked: the legacy dashboard swaps to the recap
              // screen (dashboard.py) instead of showing an empty pack. The
              // standalone Recap tab was removed — this is the only recap.
              <RecapPage idealCurve={settings?.deckMidDistribution ?? []} />
            ) : phase === "live" && state ? (
              <DashboardPage
                state={state}
                colorTint={colorTint}
                idealCurve={settings?.deckMidDistribution ?? []}
              />
            ) : (
              <div className="empty-state">{t("shell.waitingDraft")}</div>
            ))}
          {tab === "taken" && <TakenPage colorTint={colorTint} />}
          {tab === "deck" && <DeckPage colorTint={colorTint} />}
          {tab === "suggest" && (
            <SuggestPage
              colorTint={colorTint}
              draftState={state}
              onSentToBuilder={() => setTab("deck")}
            />
          )}
          {tab === "sealed" && sealedVisible && (
            <SealedPage colorTint={colorTint} />
          )}
          {tab === "compare" && <ComparePage colorTint={colorTint} />}
          {tab === "tiers" && <TiersPage />}
          {tab === "datasets" && <DatasetsPage missingSet={missingSet} />}
          {tab === "settings" && <SettingsPage />}
        </ErrorBoundary>
      </main>

      {appError && <div className="error-toast">{appError}</div>}
      <DatasetUpdateToast />
    </div>
  );
}
