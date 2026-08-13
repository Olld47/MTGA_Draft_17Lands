import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BootStatus, DraftState, SealedState, Settings } from "./api/types";
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

// Keep the real EVENTS names; stub the listen() wrapper so no backend is
// contacted in jsdom.
vi.mock("./api/events", async (importOriginal) => {
  const mod = await importOriginal<typeof import("./api/events")>();
  return { ...mod, on: vi.fn(() => Promise.resolve(() => {})) };
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

async function renderBooted(state: DraftState) {
  vi.mocked(getBootStatus).mockResolvedValue(bootStatus());
  vi.mocked(getDraftState).mockResolvedValue(state);
  vi.mocked(getSettings).mockResolvedValue(settings());
  vi.mocked(getSetMetrics).mockResolvedValue({ metrics: {}, hasData: false });
  vi.mocked(listDraftLogs).mockResolvedValue({ logs: [], current: "" });
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
