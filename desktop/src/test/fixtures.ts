import type { SealedAction, SealedState } from "../api/types";

/** Shared SealedState fixture factory. Used by the sealedAutoRun unit tests and
 *  the SealedPage / App component tests so the pool shape lives in one place
 *  instead of a byte-identical literal in each file. */
export const sealedState = (over: Partial<SealedState> = {}): SealedState => ({
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

/** Shared SealedAction fixture factory — the wrapper every sealed command
 *  returns, so tests can hand the page a populated deck after auto-run. */
export const sealedAction = (
  state: SealedState,
  message = "",
): SealedAction => ({ ok: true, message, state });
