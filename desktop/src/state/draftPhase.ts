import type { DraftState } from "../api/types";

/** What the Draft tab renders for a given state. Mirrors the legacy dashboard's
 *  three-way split: empty (no draft yet), live (active drafting/deckbuilding),
 *  recap (the full pool is picked — dashboard.py swaps to the recap screen).
 *  The recap phase keys off the backend's count-based draftComplete, not the
 *  scanner's pack value, so the swap fires the moment the last card is picked. */
export type DraftPhase = "empty" | "live" | "recap";

export function draftPhase(state: DraftState | null): DraftPhase {
  if (!state) return "empty";
  if (state.draftComplete) return "recap";
  return "live";
}
