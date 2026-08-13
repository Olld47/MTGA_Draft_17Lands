import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BootStatus, DraftState, Settings } from "./api/types";
import App from "./App";
import { setLanguage } from "./i18n/useLanguage";
import { navigateTab } from "./state/navigation";

// SealedPage is stubbed so this test exercises App's gating (tab strip + body
// branch) without pulling in SealedPage's own data hooks.
vi.mock("./features/sealed/SealedPage", () => ({
  SealedPage: () => <div data-testid="sealed-page-stub" />,
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
  getSetMetrics,
  getSettings,
  listDraftLogs,
} from "./api/client";

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
      expect(screen.queryByTestId("sealed-page-stub")).not.toBeInTheDocument(),
    );
  });

  it("shows the Sealed tab and renders the page for a Sealed draft", async () => {
    await renderBooted(draftState({ eventType: "Sealed" }));

    fireEvent.click(screen.getByRole("button", { name: "Sealed Deck" }));

    await screen.findByTestId("sealed-page-stub");
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
