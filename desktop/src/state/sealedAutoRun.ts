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

/** Returns true when the loaded pool is fresh — an empty deck whose session the
 *  auto-run has not already consumed — meaning shells + lands should fire now.
 *  Every loaded pool's session is marked consumed either way, so a deliberate
 *  later clear (deck empty again) won't re-trigger. */
export function consumeSealedPool(state: SealedState | null): boolean {
  if (!state || !state.hasPool) return false;
  const fresh = state.mainCount === 0 && !consumedSessions.has(state.sessionId);
  consumedSessions.add(state.sessionId);
  return fresh;
}

/** Test hook: clears the consumed-session memory between tests. */
export function resetSealedAutoRun(): void {
  consumedSessions.clear();
}
