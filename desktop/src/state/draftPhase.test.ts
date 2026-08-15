import { describe, expect, it } from "vitest";

import type { DraftState } from "../api/types";
import { draftPhase } from "./draftPhase";

const state = (over: Partial<DraftState> = {}): DraftState => ({
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

describe("draftPhase", () => {
  it("reports empty with no draft state", () => {
    expect(draftPhase(null)).toBe("empty");
  });
  it("is live while a draft is in progress", () => {
    expect(draftPhase(state())).toBe("live");
    expect(draftPhase(state({ takenCount: 20 }))).toBe("live");
  });
  it("swaps to recap once the pool is fully picked", () => {
    expect(draftPhase(state({ draftComplete: true }))).toBe("recap");
  });
});
