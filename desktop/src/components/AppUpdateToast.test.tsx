import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { UpdateAvailablePayload } from "../api/events";
import { openUrl } from "../api/client";
import { AppUpdateToast } from "./AppUpdateToast";

// The component subscribes through @tauri-apps listen(), which has no backend
// in a jsdom test — capture the handler on() is given so the test can fire the
// event the Python bridge would emit. Keep the real EVENTS map; only stub on().
let handler: ((payload: UpdateAvailablePayload) => void) | undefined;

vi.mock("../api/events", async (importOriginal) => {
  const mod = await importOriginal<typeof import("../api/events")>();
  return {
    ...mod,
    on: vi.fn(
      (
        _event: string,
        h: (payload: UpdateAvailablePayload) => void,
      ): Promise<() => void> => {
        handler = h;
        return Promise.resolve(() => {});
      },
    ),
  };
});

vi.mock("../api/client", () => ({
  // A real open_url command resolves a promise; without the resolution the
  // click handler's .catch(console.warn) reads .catch off undefined.
  openUrl: vi.fn(() => Promise.resolve()),
}));

const releaseUrl =
  "https://github.com/Olld47/MTGA_Draft_17Lands/releases/tag/v0.40.0";

describe("AppUpdateToast", () => {
  beforeEach(() => {
    handler = undefined;
  });

  it("renders nothing before the update check fires", () => {
    render(<AppUpdateToast />);

    expect(screen.queryByText(/new version/)).not.toBeInTheDocument();
  });

  it("shows the localized version when a newer release exists", () => {
    render(<AppUpdateToast />);

    act(() => handler?.({ latestVersion: "v0.40.0", releaseUrl }));

    expect(
      screen.getByText("New version v0.40.0 available"),
    ).toBeInTheDocument();
  });

  it("opens the release page in the OS browser on link click", () => {
    render(<AppUpdateToast />);

    act(() => handler?.({ latestVersion: "v0.40.0", releaseUrl }));

    fireEvent.click(screen.getByRole("link", { name: "Open Releases" }));

    expect(openUrl).toHaveBeenCalledWith(releaseUrl);
  });
});
