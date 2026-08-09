import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listDraftLogs } from "../api/client";
import type { DraftLog } from "../api/types";
import { useDraftLogs } from "./useDraftLogs";

// The hook talks to the pytauri bridge; mock it so nothing leaves jsdom. `on`
// returns a resolved unlisten so the draft://refresh subscription mounts.
vi.mock("../api/client", () => ({
  listDraftLogs: vi.fn(),
  setLogFile: vi.fn(),
}));

vi.mock("../api/events", () => ({
  EVENTS: { draftRefresh: "draft://refresh" },
  on: vi.fn(() => Promise.resolve(() => {})),
}));

const draftLog = (over: Partial<DraftLog>): DraftLog => ({
  path: "/logs/Player.log",
  fileName: "Player.log",
  modified: 100,
  label: "🔴 Live: OTJ",
  isLive: true,
  ...over,
});

const LIVE = draftLog({});
const NEWEST = draftLog({
  path: "/logs/DraftLog_OTJ_PremierDraft_A.log",
  fileName: "DraftLog_OTJ_PremierDraft_A.log",
  modified: 500,
  label: "📂 OTJ PremierDraft (08-09 12:00)",
  isLive: false,
});
const OLDER = draftLog({
  path: "/logs/DraftLog_OTJ_PremierDraft_B.log",
  fileName: "DraftLog_OTJ_PremierDraft_B.log",
  modified: 400,
  label: "📂 OTJ PremierDraft (08-08 20:00)",
  isLive: false,
});

describe("useDraftLogs", () => {
  beforeEach(() => {
    vi.mocked(listDraftLogs).mockResolvedValue({
      logs: [LIVE, NEWEST, OLDER], // live first, then DraftLog_* newest-first
      current: "Player.log",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("follows the scanner's current log when it is listed", async () => {
    const { result } = renderHook(() => useDraftLogs(true, "Player.log"));
    await waitFor(() => expect(result.current.selected).toBe(LIVE.path));
  });

  it("selects a matched saved draft log over the fallback", async () => {
    const { result } = renderHook(() =>
      useDraftLogs(true, "DraftLog_OTJ_PremierDraft_B.log"),
    );
    await waitFor(() => expect(result.current.selected).toBe(OLDER.path));
  });

  it("falls back to the newest draft record when the current log is unmatched", async () => {
    // On reconnect the scanner's logName may not have loaded yet — the dropdown
    // must not sit empty; it defaults to the newest saved DraftLog_* by time.
    const { result } = renderHook(() => useDraftLogs(true, ""));
    await waitFor(() => expect(result.current.selected).toBe(NEWEST.path));
  });

  it("falls back to the live log when no draft record exists", async () => {
    vi.mocked(listDraftLogs).mockResolvedValue({
      logs: [LIVE],
      current: "Player.log",
    });
    const { result } = renderHook(() => useDraftLogs(true, ""));
    await waitFor(() => expect(result.current.selected).toBe(LIVE.path));
  });

  it("returns an empty selection when no logs exist", async () => {
    vi.mocked(listDraftLogs).mockResolvedValue({ logs: [], current: "" });
    const { result } = renderHook(() => useDraftLogs(true, ""));
    await waitFor(() => expect(result.current.selected).toBe(""));
  });
});
