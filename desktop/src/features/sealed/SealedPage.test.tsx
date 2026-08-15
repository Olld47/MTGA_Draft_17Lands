import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetSealedAutoRun } from "../../state/sealedAutoRun";
import { sealedAction, sealedState } from "../../test/fixtures";
import { SealedPage } from "./SealedPage";

// The bridge is the system boundary: the page reads the pool through
// getSealedState and the auto-run fires the two sealed commands.
vi.mock("../../api/client", () => ({
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

// No backend in jsdom — stub the listen() wrapper so the refresh effect mounts.
vi.mock("../../api/events", () => ({
  EVENTS: { draftRefresh: "draft://refresh" },
  on: vi.fn(() => Promise.resolve(() => {})),
}));

// Heavy child UI is not the subject here; mock it so the test focuses on the
// auto-run invocation (their own behavior is covered elsewhere).
vi.mock("../deck/DeckStatsView", () => ({
  DeckStatsView: () => null,
  DeckTable: () => null,
}));
vi.mock("../practice/PracticeDialog", () => ({
  PracticeDialog: () => null,
}));

import {
  getSealedState,
  sealedAutoGenerate,
  sealedAutoLands,
} from "../../api/client";

beforeEach(() => {
  // The consumed-session memory is module-level (it must survive remounts), so
  // each test starts from a clean slate.
  resetSealedAutoRun();
  vi.mocked(sealedAutoGenerate).mockResolvedValue(
    sealedAction(sealedState({ mainCount: 23 })),
  );
  vi.mocked(sealedAutoLands).mockResolvedValue(
    sealedAction(sealedState({ mainCount: 40 })),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("SealedPage auto-run on a fresh pool", () => {
  it("auto-generates shells then auto-lands, once, when a fresh pool loads", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState());

    render(<SealedPage colorTint={false} />);

    await waitFor(() => expect(sealedAutoGenerate).toHaveBeenCalledTimes(1));
    expect(sealedAutoLands).toHaveBeenCalledTimes(1);
    // Lands must follow the generated shells, not race ahead of them.
    expect(
      vi.mocked(sealedAutoGenerate).mock.invocationCallOrder[0],
    ).toBeLessThan(vi.mocked(sealedAutoLands).mock.invocationCallOrder[0]);
  });

  it("does not re-invoke after a remount of the same pool", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState());

    const { unmount } = render(<SealedPage colorTint={false} />);
    await waitFor(() => expect(sealedAutoGenerate).toHaveBeenCalledTimes(1));

    unmount();

    // The re-read still reports the fresh empty pool — the consumed-session
    // gate (not the populated deck) is what must stop a second run.
    render(<SealedPage colorTint={false} />);

    await waitFor(() =>
      expect(sealedAutoLands).toHaveBeenCalledTimes(1),
    );
    expect(sealedAutoGenerate).toHaveBeenCalledTimes(1);
  });

  it("auto-runs again for a genuinely new pool", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState());

    const { unmount } = render(<SealedPage colorTint={false} />);
    await waitFor(() => expect(sealedAutoGenerate).toHaveBeenCalledTimes(1));
    unmount();

    vi.mocked(getSealedState).mockResolvedValue(sealedState({ sessionId: "s2" }));
    render(<SealedPage colorTint={false} />);

    await waitFor(() => expect(sealedAutoGenerate).toHaveBeenCalledTimes(2));
    expect(sealedAutoLands).toHaveBeenCalledTimes(2);
  });

  it("is a silent no-op when no pool is loaded", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState({ hasPool: false }));

    render(<SealedPage colorTint={false} />);

    await screen.findByRole("button", { name: "Reload pool" });
    expect(sealedAutoGenerate).not.toHaveBeenCalled();
    expect(sealedAutoLands).not.toHaveBeenCalled();
  });

  it("does not auto-run on a pool that already has a deck", async () => {
    vi.mocked(getSealedState).mockResolvedValue(sealedState({ mainCount: 40 }));

    render(<SealedPage colorTint={false} />);

    await waitFor(() => expect(getSealedState).toHaveBeenCalledTimes(1));
    expect(sealedAutoGenerate).not.toHaveBeenCalled();
    expect(sealedAutoLands).not.toHaveBeenCalled();
  });
});
