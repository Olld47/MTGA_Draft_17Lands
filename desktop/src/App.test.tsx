import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  BootStatus,
  DraftLog,
  DraftLogList,
  DraftState,
  SealedState,
  Settings,
} from "./api/types";
import { EVENTS } from "./api/events";
import App from "./App";
import { setLanguage } from "./i18n/useLanguage";
import { navigateTab } from "./state/navigation";

// The real SealedPage mounts here: its auto-run through App's shell is a
// subject of the tests below, and its tab gating is what the "Sealed tab
// gating" describe block asserts against. Only its heavy children are not the
// subject — mock them the way SealedPage.test.tsx does.
vi.mock("./features/deck/DeckStatsView", () => ({
  DeckStatsView: () => null,
  DeckTable: () => null,
}));
vi.mock("./features/practice/PracticeDialog", () => ({
  PracticeDialog: () => null,
}));

// The bridge is the system boundary; App and the state hooks read through it.
// The extra exports cover the pages the default draft tab mounts (DashboardPage
// tree + RecapPage) so the shell renders without cascade errors.
vi.mock("./api/client", () => ({
  getBootStatus: vi.fn(),
  forceReload: vi.fn(),
  getDraftState: vi.fn(),
  getSettings: vi.fn(),
  resetSettings: vi.fn(),
  setSettings: vi.fn(),
  listDraftLogs: vi.fn(),
  setLogFile: vi.fn(),
  getDatasetSwitcher: vi.fn(),
  getSetMetrics: vi.fn(),
  reportFrontendError: vi.fn(),
  getDraftRecord: vi.fn(),
  getRecap: vi.fn(),
  compareAddCard: vi.fn(),
  openUrl: vi.fn(),
  selectDataset: vi.fn(),
  getSealedState: vi.fn(),
  sealedAutoGenerate: vi.fn(),
  sealedAutoLands: vi.fn(),
  sealedReloadPool: vi.fn(),
  sealedCreateVariant: vi.fn(),
  sealedRenameVariant: vi.fn(),
  sealedDeleteVariant: vi.fn(),
  sealedSelectVariant: vi.fn(),
  sealedMoveCard: vi.fn(),
  sealedClearDeck: vi.fn(),
  sealedAddBasic: vi.fn(),
  sealedRemoveBasic: vi.fn(),
  sealedImportDeck: vi.fn(),
  sealedExport: vi.fn(),
  sealedExportSealeddeck: vi.fn(),
}));

const { onMock, fireBridgeEvent, clearBridgeEvents } = vi.hoisted(() => {
  const handlers = new Map<string, Set<(payload: unknown) => void>>();
  return {
    onMock: vi.fn((event: string, handler: (payload: unknown) => void) => {
      let list = handlers.get(event);
      if (!list) handlers.set(event, (list = new Set()));
      list.add(handler);
      return Promise.resolve(() => {
        list.delete(handler);
      });
    }),
    fireBridgeEvent: (event: string, payload?: unknown) => {
      handlers.get(event)?.forEach((cb) => cb(payload));
    },
    clearBridgeEvents: () => handlers.clear(),
  };
});

// Keep the real EVENTS names; stub the listen() wrapper so no backend is
// contacted in jsdom, but capture handlers so tests can simulate bridge emits
// (e.g. the orchestrator's draft://refresh after set_log_file).
vi.mock("./api/events", async (importOriginal) => {
  const mod = await importOriginal<typeof import("./api/events")>();
  return { ...mod, on: onMock };
});

import {
  getBootStatus,
  getDatasetSwitcher,
  getDraftState,
  getSealedState,
  getSetMetrics,
  getSettings,
  listDraftLogs,
  sealedAutoGenerate,
  sealedAutoLands,
  setLogFile,
} from "./api/client";
import { resetSealedAutoRun } from "./state/sealedAutoRun";

const bootStatus = (): BootStatus => ({
  booted: true,
  lastMessage: "",
  error: null,
});

const settings = (over: Partial<Settings> = {}): Settings => ({
  deckFilter: "Auto",
  filterFormat: "Names",
  resultFormat: "Percentage",
  uiSize: "100%",
  desktopTheme: "System",
  language: "en",
  cardColorsEnabled: false,
  draftLogEnabled: true,
  updateNotificationsEnabled: true,
  missingNotificationsEnabled: true,
  autoSyncDatasets: true,
  arenaLogLocation: "",
  databaseLocation: "",
  columnConfigs: {},
  columnDisplayOrders: {},
  tableSortStates: {},
  alwaysOnTop: false,
  deckMidDistribution: [],
  overlayGeometry: "",
  ...over,
});

const draftState = (over: Partial<DraftState> = {}): DraftState => ({
  booted: true,
  eventSet: "",
  eventType: "",
  eventString: "",
  draftId: "",
  startTime: null,
  pack: 1,
  pick: 1,
  activeFilter: "",
  filterLabel: "",
  packCards: [],
  missingCards: [],
  takenCount: 0,
  draftComplete: false,
  signals: { scores: {} },
  poolSummary: null,
  datasetName: null,
  logSource: "live",
  logName: "",
  ...over,
});

const sealedState = (over: Partial<SealedState> = {}): SealedState => ({
  hasPool: true,
  poolSize: 60,
  sessionId: "s1",
  variants: [{ name: "Build 1", isActive: true, mainCount: 0 }],
  activeVariant: "Build 1",
  deck: [],
  sideboard: [],
  stats: {
    totalCards: 0,
    creatures: 0,
    noncreatures: 0,
    lands: 0,
    avgCmc: 0,
    pips: [],
    curve: {},
    tribes: [],
    tags: [],
    basics: {},
  },
  mainCount: 0,
  sideboardCount: 60,
  activeFilter: "Auto",
  ...over,
});

async function renderBooted(
  state: DraftState,
  opts: { logs?: DraftLogList } = {},
) {
  vi.mocked(getBootStatus).mockResolvedValue(bootStatus());
  vi.mocked(getDraftState).mockResolvedValue(state);
  vi.mocked(getSettings).mockResolvedValue(settings());
  vi.mocked(getSetMetrics).mockResolvedValue({ metrics: {}, hasData: false });
  vi.mocked(listDraftLogs).mockResolvedValue(
    opts.logs ?? { logs: [], current: "" },
  );
  vi.mocked(getDatasetSwitcher).mockResolvedValue({
    setCode: "",
    detectedEvent: null,
    activeEvent: null,
    activeGroup: null,
    events: [],
  });
  render(<App />);
  // The shell (with the tab strip) only mounts once boot completes.
  await screen.findByRole("navigation");
}

beforeEach(() => {
  setLanguage("en");
  // The bridge-handler capture map is a closure the mock factory owns; RTL's
  // unmount cleanup removes handlers via an async microtask and vi.clearAllMocks
  // only clears call history, so wipe the map here to isolate each case.
  clearBridgeEvents();
  // The consumed-session memory is module-level (it must survive SealedPage's
  // remounts), so every case starts from a clean slate — the "does not leak
  // across cases" test below verifies this is in place.
  resetSealedAutoRun();
  // Defaults for the real SealedPage when a gating test mounts it: a pool-less
  // page (empty state) so no auto-run fires; the auto-run tests override the
  // read below with a fresh pool.
  vi.mocked(getSealedState).mockResolvedValue(sealedState({ hasPool: false }));
  vi.mocked(sealedAutoGenerate).mockResolvedValue({
    ok: true,
    message: "",
    state: sealedState({ mainCount: 23 }),
  });
  vi.mocked(sealedAutoLands).mockResolvedValue({
    ok: true,
    message: "",
    state: sealedState({ mainCount: 40 }),
  });
});

afterEach(() => {
  setLanguage("en");
  vi.clearAllMocks();
});

describe("Sealed tab gating", () => {
  it("hides the Sealed tab and body for a non-Sealed draft", async () => {
    await renderBooted(draftState({ eventType: "PremierDraft" }));

    expect(
      screen.queryByRole("button", { name: "Sealed Deck" }),
    ).not.toBeInTheDocument();

    // The body branch is defensive: a non-Sealed draft can't reach the tab by
    // clicking, but a programmatic navigate (context-menu path) must not
    // render the page either.
    act(() => navigateTab("sealed"));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Reload pool" })).not.toBeInTheDocument(),
    );
  });

  it("shows the Sealed tab and renders the page for a Sealed draft", async () => {
    await renderBooted(draftState({ eventType: "Sealed" }));

    fireEvent.click(screen.getByRole("button", { name: "Sealed Deck" }));

    await screen.findByRole("button", { name: "Reload pool" });
  });

  it("treats TradSealed as a Sealed variant", async () => {
    await renderBooted(draftState({ eventType: "TradSealed" }));

    expect(
      screen.getByRole("button", { name: "Sealed Deck" }),
    ).toBeInTheDocument();
  });

  it("hides the Sealed tab with no active draft", async () => {
    await renderBooted(draftState({ eventType: "" }));

    expect(
      screen.queryByRole("button", { name: "Sealed Deck" }),
    ).not.toBeInTheDocument();
  });

  it("gates on the history log's own event type", async () => {
    await renderBooted(
      draftState({ logSource: "history", eventType: "Sealed" }),
    );

    expect(
      screen.getByRole("button", { name: "Sealed Deck" }),
    ).toBeInTheDocument();
  });

  it("shows the Sealed tab after loading a Sealed history log via the log switcher", async () => {
    const liveLog: DraftLog = {
      path: "/logs/Player.log",
      fileName: "Player.log",
      modified: 100,
      label: "Live Arena Log",
      isLive: true,
    };
    const sealedLog: DraftLog = {
      path: "/logs/DraftLog_OTJ_Sealed.log",
      fileName: "DraftLog_OTJ_Sealed.log",
      modified: 200,
      label: "OTJ Sealed",
      isLive: false,
    };

    await renderBooted(
      draftState({ eventType: "PremierDraft", logName: "Player.log" }),
      { logs: { logs: [liveLog, sealedLog], current: "Player.log" } },
    );

    // Live Premier draft: no Sealed tab.
    expect(
      screen.queryByRole("button", { name: "Sealed Deck" }),
    ).not.toBeInTheDocument();

    // The log switcher is the only combobox (DatasetSwitcher renders null).
    const switcher = await screen.findByRole("combobox");
    await act(async () => {
      fireEvent.change(switcher, { target: { value: sealedLog.path } });
    });

    // set_log_file ran, but the tab must stay hidden until the backend's
    // draft://refresh makes useDraftState re-fetch with the history log's own
    // event type.
    await waitFor(() => expect(setLogFile).toHaveBeenCalledWith(sealedLog.path));
    expect(
      screen.queryByRole("button", { name: "Sealed Deck" }),
    ).not.toBeInTheDocument();

    // The orchestrator re-scanned the log and emitted draft://refresh; the
    // re-fetched state carries the history log's Sealed event type.
    vi.mocked(getDraftState).mockResolvedValue(
      draftState({
        logSource: "history",
        eventType: "Sealed",
        logName: sealedLog.fileName,
      }),
    );
    await act(async () => {
      fireBridgeEvent(EVENTS.draftRefresh, { seq: 1 });
    });

    expect(
      screen.getByRole("button", { name: "Sealed Deck" }),
    ).toBeInTheDocument();
  });
});

// Convention for any App-level test that mounts the real SealedPage: the
// consumed-session memory lives at module level (state/sealedAutoRun.ts), so a
// session consumed by a previous case would silently skip the auto-run here —
// the beforeEach reset is what isolates each case.
describe("Sealed auto-run through App's shell", () => {
  it("auto-generates shells then auto-lands for a fresh pool", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState());
    await renderBooted(draftState({ eventType: "Sealed" }));

    fireEvent.click(screen.getByRole("button", { name: "Sealed Deck" }));

    await waitFor(() => expect(sealedAutoGenerate).toHaveBeenCalledTimes(1));
    expect(sealedAutoLands).toHaveBeenCalledTimes(1);
    expect(
      vi.mocked(sealedAutoGenerate).mock.invocationCallOrder[0],
    ).toBeLessThan(vi.mocked(sealedAutoLands).mock.invocationCallOrder[0]);
  });

  it("auto-runs again in a later case for the same session — consumed-session memory does not leak across cases", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState());
    await renderBooted(draftState({ eventType: "Sealed" }));

    fireEvent.click(screen.getByRole("button", { name: "Sealed Deck" }));

    await waitFor(() => expect(sealedAutoGenerate).toHaveBeenCalledTimes(1));
    expect(sealedAutoLands).toHaveBeenCalledTimes(1);
  });
});
