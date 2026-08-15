import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FilterOptions, Settings } from "../../api/types";
import { setLanguage } from "../../i18n/useLanguage";
import { SettingsPage } from "./SettingsPage";

// The label and <select> are siblings inside a .setting-row (no htmlFor), so
// the select has no implicit accessible name — locate the row via its visible
// label text, then grab the control inside it.
const languageSelect = (): HTMLSelectElement => {
  const row = screen
    .getByText(/^Language/, { selector: "label" })
    .closest(".setting-row")! as HTMLElement;
  return within(row).getByRole("combobox") as HTMLSelectElement;
};

// The page pulls settings through the shared useSettings store; mock the
// bridge so nothing talks to a real backend in jsdom.
vi.mock("../../api/client", () => ({
  getSettings: vi.fn(),
  setSettings: vi.fn(),
  resetSettings: vi.fn(),
  getFilterOptions: vi.fn(),
}));

// useFilterOptions subscribes to draft://refresh via @tauri-apps listen(), which
// has no backend in a jsdom test — stub the event module so the effect mounts.
vi.mock("../../api/events", () => ({
  EVENTS: { draftRefresh: "draft://refresh" },
  on: vi.fn(() => Promise.resolve(() => {})),
}));

import { getFilterOptions, getSettings, setSettings } from "../../api/client";

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

const filterOptions = (): FilterOptions => ({
  options: [{ key: "Auto", label: "Auto", winRate: null }],
  active: "Auto",
  autoDetected: "",
  autoDetectedLabel: "",
});

beforeEach(() => {
  vi.mocked(getSettings).mockResolvedValue(settings());
  vi.mocked(getFilterOptions).mockResolvedValue(filterOptions());
});

afterEach(() => {
  setLanguage("en");
  vi.clearAllMocks();
});

describe("SettingsPage", () => {
  it("renders the language dropdown with both locale options", async () => {
    render(<SettingsPage />);

    const select = await waitFor(() => languageSelect());
    expect(select).toHaveValue("en");
    // Endonyms are never translated.
    expect(screen.getByRole("option", { name: "English" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "简体中文" }),
    ).toBeInTheDocument();
    // The rest of the page renders English by default.
    expect(
      screen.getByRole("heading", { name: "Display" }),
    ).toBeInTheDocument();
    // receive() applies the persisted uiSize (100% here) to the global zoom.
    // If that line is removed (mutation), --ui-scale is never set and fails.
    expect(
      document.documentElement.style.getPropertyValue("--ui-scale"),
    ).toBe("1");
  });

  it("renders the UI scale select and patches the backend live", async () => {
    render(<SettingsPage />);
    const row = await waitFor(() =>
      screen
        .getByText(/^UI scale/, { selector: "label" })
        .closest(".setting-row")! as HTMLElement,
    );
    const select = within(row).getByRole("combobox") as HTMLSelectElement;

    // The value IS the persisted uiSize string — a legacy 22-option scale.
    expect(select).toHaveValue("100%");
    expect(within(select).getAllByRole("option")).toHaveLength(22);
    expect(
      within(select).getByRole("option", { name: "150%" }),
    ).toBeInTheDocument();

    // Keep the backend response in flight so the only path to zoom 150% is the
    // optimistic applyUiScale in useSettings.patch — if that line is removed
    // (mutation), the CSS var stays "1" and this test fails.
    vi.mocked(setSettings).mockReturnValue(new Promise<Settings>(() => {}));

    fireEvent.change(select, { target: { value: "150%" } });

    await waitFor(() =>
      expect(setSettings).toHaveBeenCalledWith({ uiSize: "150%" }),
    );
    expect(
      document.documentElement.style.getPropertyValue("--ui-scale"),
    ).toBe("1.5");
  });

  it("renders the update-notifications toggle and patches it", async () => {
    render(<SettingsPage />);
    const row = await waitFor(() =>
      screen
        .getByText(/^Notify about dataset updates/, { selector: "label" })
        .closest(".setting-row")! as HTMLElement,
    );
    const checkbox = within(row).getByRole("checkbox") as HTMLInputElement;
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);

    await waitFor(() =>
      expect(setSettings).toHaveBeenCalledWith({
        updateNotificationsEnabled: false,
      }),
    );
  });

  it("switching the language patches the backend and flips the UI", async () => {
    render(<SettingsPage />);
    const select = await waitFor(() => languageSelect());

    // Keep the backend response in flight so the only path to Chinese is the
    // optimistic setLanguage in useSettings.patch — if that line is removed
    // (mutation), the UI stays English and this test fails.
    vi.mocked(setSettings).mockReturnValue(new Promise<Settings>(() => {}));

    fireEvent.change(select, { target: { value: "zh" } });

    await waitFor(() =>
      expect(setSettings).toHaveBeenCalledWith({ language: "zh" }),
    );
    expect(select).toHaveValue("zh");
    expect(
      screen.getByRole("heading", { name: "显示" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "简体中文" }),
    ).toBeInTheDocument();
  });
});
