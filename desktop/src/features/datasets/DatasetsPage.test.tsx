import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  listAvailableSets,
  listDatasets,
} from "../../api/client";
import type { AvailableSets, DatasetList } from "../../api/types";
import { setLanguage } from "../../i18n/useLanguage";
import { DatasetsPage } from "./DatasetsPage";

vi.mock("../../api/client", () => ({
  listDatasets: vi.fn(),
  listAvailableSets: vi.fn(),
  downloadDataset: vi.fn(),
  selectDataset: vi.fn(),
  deleteDataset: vi.fn(),
}));

const datasets = (over: Partial<DatasetList> = {}): DatasetList => ({
  datasets: [],
  activeDataset: null,
  lastSyncDate: "",
  newestAgeDays: -1,
  stale: false,
  ...over,
});

describe("DatasetsPage", () => {
  beforeEach(() => {
    setLanguage("en");
    vi.mocked(listAvailableSets).mockResolvedValue({ sets: [] } as AvailableSets);
  });

  it("stays silent when the newest dataset is fresh", async () => {
    vi.mocked(listDatasets).mockResolvedValue(
      datasets({ newestAgeDays: 1, stale: false }),
    );

    render(<DatasetsPage />);

    expect(await screen.findByText("Local datasets")).toBeInTheDocument();
    expect(screen.queryByText(/out of date/i)).not.toBeInTheDocument();
  });

  it("flags datasets older than the stale threshold with their age and last sync", async () => {
    vi.mocked(listDatasets).mockResolvedValue(
      datasets({ newestAgeDays: 8, stale: true, lastSyncDate: "2026-08-05" }),
    );

    render(<DatasetsPage />);

    expect(await screen.findByText(/8 days old/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-08-05/)).toBeInTheDocument();
  });

  it("mentions the missing last sync when auto-sync never succeeded", async () => {
    vi.mocked(listDatasets).mockResolvedValue(
      datasets({ newestAgeDays: 8, stale: true, lastSyncDate: "" }),
    );

    render(<DatasetsPage />);

    expect(await screen.findByText(/no successful auto-sync/i)).toBeInTheDocument();
  });
});
