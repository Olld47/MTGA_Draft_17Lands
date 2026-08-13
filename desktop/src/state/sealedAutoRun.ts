import type { SealedState } from "../api/types";

// Module-level memory of sealed pools whose fresh state has already been
// consumed by the auto-run — either it fired, or the deck arrived non-empty so
// there was nothing fresh to run. It lives here (not in SealedPage) so it
// survives the page's conditional remount on every tab switch: App.tsx renders
// <SealedPage> only while the tab is active, so a bare "first mount" effect
// would re-run on every switch and clobber manual edits. The Set resets on app
// restart, which is safe because the empty-deck gate below still stops a
// clobbering re-run of an already-built deck.
const consumedSessions = new Set<string>();

/** True when the loaded pool is fresh — an empty deck whose session the auto-run
 *  has not already seen — meaning shells + lands should fire now. Pure: reads
 *  module memory, mutates nothing. */
export function isFreshSealedPool(state: SealedState | null): boolean {
  if (!state || !state.hasPool) return false;
  return state.mainCount === 0 && !consumedSessions.has(state.sessionId);
}

/** Records that the auto-run has now seen this pool's session. Every loaded
 *  pool is marked — even a populated one — so a deliberate later clear (deck
 *  empty again) won't re-trigger. Call after isFreshSealedPool: the fresh state
 *  is gone the moment the pool is seen, fresh or not. */
export function markSealedPoolConsumed(state: SealedState | null): void {
  if (state && state.hasPool) consumedSessions.add(state.sessionId);
}

/** Test hook: clears the consumed-session memory between tests. */
export function resetSealedAutoRun(): void {
  consumedSessions.clear();
}
