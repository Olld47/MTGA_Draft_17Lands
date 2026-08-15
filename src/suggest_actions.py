"""
src/suggest_actions.py
Shared action orchestration for the AI Deck Builder suggestion engine,
consumed by both the desktop bridge (mtga_bridge.suggest_session) and the
legacy tkinter view (src/ui/windows/suggest_deck.py). Pure: owns the build
state (suggestions / selection / status / building flag / built-pool key) and
the calculate pipeline — pool guard, engine invocation, error/empty settling,
snap-to-strongest — through explicit parameters. No tkinter, no pytauri, no
viewmodels; the adapters own scanner locking, thread marshalling, progress
formatting, and presentation.

Ticket 09 convergence: the pipeline was previously duplicated verbatim between
the bridge and the tkinter panel (and had drifted: the panel hardcoded the
22-spell threshold and the "Builder Error" label while the bridge had a
constant and a different message). This module is the single implementation
both sides delegate to.
"""

import logging
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_PLAYABLE_SPELLS = 22

#: (ok, message) — ok=False means the build settled without a suggestion
#: (thin pool / empty result / engine error) and the reason is in ``status``;
#: message is user-facing and UI-agnostic.
ActionResult = Tuple[bool, str]


def pool_key(pool) -> tuple:
    """Fingerprint of a draft pool: accumulated (name, count) pairs, sorted.
    Two pools with the same cards in the same quantities compare equal no
    matter the row order or whether copies are one row or several."""
    counts: Dict[str, int] = {}
    for card in pool or []:
        counts[card.get("name", "")] = counts.get(card.get("name", ""), 0) + card.get(
            "count", 1
        )
    return tuple(sorted(counts.items()))


def playable_spell_message(pool) -> Optional[str]:
    """None when the pool clears the minimum-spell guard, else the user-facing
    message. The tkinter panel calls this synchronously for instant feedback;
    ``SuggestActions.calculate`` re-checks it as the authoritative guard."""
    playable = [c for c in pool or [] if "Land" not in c.get("types", [])]
    if len(playable) < MIN_PLAYABLE_SPELLS:
        return (
            f"Not enough spells drafted yet (Have {len(playable)}, "
            f"Need {MIN_PLAYABLE_SPELLS})."
        )
    return None


class SuggestActions:
    """Pure action pipeline for the deck-builder suggestion engine (the "brain"
    both UIs delegate to). One instance per session; state lives here, so a
    build started from either UI is visible to the other through the same
    object."""

    def __init__(self):
        self.suggestions: Dict[str, dict] = {}
        self.selected: str = ""
        self.status: str = ""
        self.is_building = False
        #: Pool fingerprint the current suggestion was built from. None until
        #: the first build settles (success or thin-pool guard), so stale
        #: starts True — the frontend auto-triggers a build on a fresh pool.
        self.built_pool_key: Optional[tuple] = None

    # --- build ---------------------------------------------------------------

    def calculate(
        self,
        pool,
        metrics,
        event_type,
        configuration,
        progress: Optional[Callable[[dict], None]] = None,
    ) -> ActionResult:
        """Runs the suggestion pipeline: spell-count guard → engine call →
        settle state. Runs synchronously on the caller's thread; adapters
        decide the thread (the panel uses its executor, the bridge a pytauri
        worker) and pass ``progress``, which receives raw engine messages
        (dicts with "status" or "variant_label"/"variant_data") — formatting
        them for the frontend or the widgets is the adapter's job. The
        is_building flag is set here around the engine call; adapters that
        declare "building" up front (the panel's synchronous double-submit
        guard) may set it before calling — the flag is reset on every path,
        so a stale True never sticks."""
        pool_fingerprint = pool_key(pool)

        guard = playable_spell_message(pool)
        if guard is not None:
            self.suggestions = {}
            self.selected = ""
            self.status = guard
            self.built_pool_key = pool_fingerprint
            return False, guard

        self.is_building = True
        try:
            # Imported lazily: deck_builder pulls in the simulator (numpy),
            # which neither adapter should pay for at module import time.
            from src.advisor.deck_builder import suggest_deck

            results = suggest_deck(
                pool,
                metrics,
                configuration,
                event_type,
                progress,
                configuration.card_data.latest_dataset,
            )
        except Exception as exc:
            logger.error("Suggest deck build failed: %s", exc, exc_info=True)
            self.suggestions = {}
            self.selected = ""
            self.status = "Builder error — see the log for details."
            return False, self.status
        finally:
            self.is_building = False

        if not results:
            self.suggestions = {}
            self.selected = ""
            self.status = (
                f"Not enough on-color playables to form a 40-card deck "
                f"(Need {MIN_PLAYABLE_SPELLS})."
            )
            self.built_pool_key = pool_fingerprint
            return False, self.status

        self.suggestions = results
        self.status = ""
        # Snap to the mathematically strongest deck (the engine returns decks
        # ordered best-first), as the legacy _finalize_build did.
        self.selected = next(iter(results))
        self.built_pool_key = pool_fingerprint
        return True, ""

    def select(self, label: str) -> None:
        if label in self.suggestions:
            self.selected = label

    # --- active deck accessors ----------------------------------------------

    def active(self) -> Optional[dict]:
        return self.suggestions.get(self.selected)

    def active_lists(self) -> tuple[List[dict], List[dict]]:
        data = self.active()
        if not data:
            return [], []
        return data.get("deck_cards", []), data.get("sideboard_cards", [])

    def deck_lists(self) -> tuple[List[dict], List[dict]]:
        """Deep-ish copies for handing the selected deck to the custom-deck
        builder, so edits there don't mutate the cached suggestion."""
        deck, sideboard = self.active_lists()
        return [dict(c) for c in deck], [dict(c) for c in sideboard]

    def export_text(self) -> str:
        """MTGA export string for the selected deck (clipboard text)."""
        from src.card_logic import copy_deck

        deck, sideboard = self.active_lists()
        return copy_deck(deck, sideboard)

    def is_stale(self, pool) -> bool:
        """True when the shown suggestion was built from a pool that no longer
        matches ``pool`` — a freshly finished draft with no build yet
        (built_pool_key is None), or the user has drafted more cards since the
        last build. Deliberately True after an engine error so the frontend can
        retry instead of pinning an outdated message."""
        current = pool_key(pool)
        return self.built_pool_key is None or current != self.built_pool_key
