import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DatasetSyncFailedPayload } from "../api/events";
import { DatasetSyncFailedToast } from "./DatasetSyncFailedToast";

// The component subscribes through @tauri-apps listen(), which has no backend
// in a jsdom test — capture the handler on() is given so the test can fire the
// event the Python bridge would emit when the background dataset sync fails.
let handler: ((payload: DatasetSyncFailedPayload) => void) | undefined;

vi.mock("../api/events", () => ({
  EVENTS: { datasetsSyncFailed: "datasets://syncFailed" },
  on: vi.fn(
    (
      _event: string,
      h: (payload: DatasetSyncFailedPayload) => void,
    ): Promise<() => void> => {
      handler = h;
      return Promise.resolve(() => {});
    },
  ),
}));

describe("DatasetSyncFailedToast", () => {
  beforeEach(() => {
    handler = undefined;
  });

  it("renders nothing before a sync failure", () => {
    render(<DatasetSyncFailedToast />);

    expect(screen.queryByText(/sync failed/i)).not.toBeInTheDocument();
  });

  it("shows the localized toast when the background sync fails", () => {
    render(<DatasetSyncFailedToast />);

    act(() => handler?.({}));

    expect(screen.getByText(/dataset sync failed/i)).toBeInTheDocument();
  });
});
