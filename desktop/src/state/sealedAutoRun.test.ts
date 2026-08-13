import { beforeEach, describe, expect, it } from "vitest";

import type { SealedState } from "../api/types";
import { consumeSealedPool, resetSealedAutoRun } from "./sealedAutoRun";

const pool = (over: Partial<SealedState> = {}): SealedState => ({
  hasPool: true,
  poolSize: 60,
  sessionId: "s1",
  variants: [{ name: "Build 1", isActive: true, mainCount: 0 }],
  activeVariant: "Build 1",
  deck: [],
  sideboard: [],
  stats: {
    totalCards: 0,
    creatures: 0,
    noncreatures: 0,
    lands: 0,
    avgCmc: 0,
    pips: [],
    curve: {},
    tribes: [],
    tags: [],
    basics: {},
  },
  mainCount: 0,
  sideboardCount: 60,
  activeFilter: "Auto",
  ...over,
});

beforeEach(() => {
  resetSealedAutoRun();
});

describe("consumeSealedPool", () => {
  it("returns true for a fresh pool (empty deck, unseen session)", () => {
    expect(consumeSealedPool(pool())).toBe(true);
  });

  it("returns false on a second look at the same session — the fresh state is consumed", () => {
    expect(consumeSealedPool(pool())).toBe(true);
    expect(consumeSealedPool(pool())).toBe(false);
  });

  it("returns false for a populated deck and keeps the session consumed, so a later clear never re-triggers", () => {
    expect(consumeSealedPool(pool({ mainCount: 12 }))).toBe(false);
    expect(consumeSealedPool(pool({ mainCount: 0 }))).toBe(false);
  });

  it("returns true again for a genuinely new session", () => {
    consumeSealedPool(pool());
    expect(consumeSealedPool(pool({ sessionId: "s2" }))).toBe(true);
  });

  it("returns false and consumes nothing when no pool is loaded", () => {
    expect(consumeSealedPool(null)).toBe(false);
    expect(consumeSealedPool(pool({ hasPool: false }))).toBe(false);
    // A pool arriving later is still treated as fresh.
    expect(consumeSealedPool(pool())).toBe(true);
  });
});
