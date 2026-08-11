import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DatasetsUpdatedPayload } from "../api/events";
import { DatasetUpdateToast } from "./DatasetUpdateToast";

// The component subscribes through @tauri-apps listen(), which has no backend
// in a jsdom test — capture the handler on() is given so the test can fire the
// event the Python bridge would emit.
let handler: ((payload: DatasetsUpdatedPayload) => void) | undefined;

vi.mock("../api/events", () => ({
  EVENTS: { datasetsUpdated: "datasets://updated" },
  on: vi.fn(
    (
      _event: string,
      h: (payload: DatasetsUpdatedPayload) => void,
    ): Promise<() => void> => {
      handler = h;
      return Promise.resolve(() => {});
    },
  ),
}));

describe("DatasetUpdateToast", () => {
  beforeEach(() => {
    handler = undefined;
  });

  it("renders nothing before the background check fires", () => {
    render(<DatasetUpdateToast />);

    expect(screen.queryByText(/datasets updated/)).not.toBeInTheDocument();
  });

  it("shows the localized count when datasets were actually updated", () => {
    render(<DatasetUpdateToast />);

    act(() => handler?.({ updatedCount: 2 }));

    expect(screen.getByText("2 datasets updated")).toBeInTheDocument();
  });
});
