import { beforeEach, describe, expect, it } from "vitest";

import { sealedState } from "../test/fixtures";
import {
  isFreshSealedPool,
  markSealedPoolConsumed,
  resetSealedAutoRun,
} from "./sealedAutoRun";

beforeEach(() => {
  resetSealedAutoRun();
});

describe("isFreshSealedPool", () => {
  it("is true for a fresh pool (empty deck, unseen session)", () => {
    expect(isFreshSealedPool(sealedState())).toBe(true);
  });

  it("is false once the session has been marked consumed", () => {
    markSealedPoolConsumed(sealedState());
    expect(isFreshSealedPool(sealedState())).toBe(false);
  });

  it("is false for a populated deck", () => {
    expect(isFreshSealedPool(sealedState({ mainCount: 12 }))).toBe(false);
  });

  it("is false when no pool is loaded", () => {
    expect(isFreshSealedPool(null)).toBe(false);
    expect(isFreshSealedPool(sealedState({ hasPool: false }))).toBe(false);
  });

  it("is true again for a genuinely new session", () => {
    markSealedPoolConsumed(sealedState());
    expect(isFreshSealedPool(sealedState({ sessionId: "s2" }))).toBe(true);
  });
});

describe("markSealedPoolConsumed", () => {
  it("records the session even for a populated pool, so a later clear never re-triggers", () => {
    markSealedPoolConsumed(sealedState({ mainCount: 12 }));
    expect(isFreshSealedPool(sealedState({ mainCount: 0 }))).toBe(false);
  });

  it("records nothing when no pool is loaded", () => {
    markSealedPoolConsumed(null);
    markSealedPoolConsumed(sealedState({ hasPool: false }));
    expect(isFreshSealedPool(sealedState())).toBe(true);
  });
});
