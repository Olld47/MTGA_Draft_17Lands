import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DatasetsUpdatedPayload } from "../api/events";
import { setLanguage } from "../i18n/useLanguage";
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

  // The language store is module-level; restore the English default so a
  // language switch here cannot leak into later tests (suite order-insensitive).
  afterEach(() => {
    setLanguage("en");
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

  it("re-translates the visible message when the language switches", () => {
    render(<DatasetUpdateToast />);

    act(() => handler?.({ updatedCount: 2 }));
    expect(screen.getByText("2 datasets updated")).toBeInTheDocument();

    act(() => setLanguage("zh"));

    expect(screen.getByText("已更新 2 个数据集")).toBeInTheDocument();
  });
});
