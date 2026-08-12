"""
mtga_bridge.suggest_session
Headless port of src/ui/windows/suggest_deck.py::SuggestDeckPanel. Extracts the
engine calls (_calculate_suggestions / _finalize_build / _render_deck) out of
the tkinter panel, leaving image loading to the frontend — it reads the
Scryfall URLs on DeckRowVM directly instead of downloading and resizing in
Python.

No tkinter, no pytauri. The panel dispatched the build to a ThreadPoolExecutor
and marshalled progress back with .after(); here calculate() runs on the
caller's thread (a pytauri worker thread) and streams progress through a
callback the command forwards over a Channel.
"""

import logging
from typing import Callable, Dict, List, Optional

from src import constants

from mtga_bridge.deck_view import (
    build_sample_hand,
    build_sim_result,
    build_stats,
    card_sort_key,
    row_vm,
)
from mtga_bridge.viewmodels import (
    DeckExportVM,
    SampleHandVM,
    SuggestArchetypeVM,
    SuggestStateVM,
)

logger = logging.getLogger(__name__)

MIN_PLAYABLE_SPELLS = 22


def _pool_key(pool) -> tuple:
    """Fingerprint of a draft pool: accumulated (name, count) pairs, sorted.
    Two pools with the same cards in the same quantities compare equal no
    matter the row order or whether copies are one row or several."""
    counts: Dict[str, int] = {}
    for card in pool or []:
        counts[card.get("name", "")] = counts.get(card.get("name", ""), 0) + card.get(
            "count", 1
        )
    return tuple(sorted(counts.items()))


class SuggestSession:
    """Stateful AI-suggestion model. One instance per runtime, reused across
    commands. Holds the last build's suggestions and the selected archetype."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.suggestions: Dict[str, dict] = {}
        self.selected: str = ""
        self.status: str = ""
        self.is_building = False
        self._built_pool_key = None

    # --- build ---------------------------------------------------------------

    def calculate(self, progress: Optional[Callable[[str, dict], None]] = None) -> None:
        """Port of _calculate_suggestions + _finalize_build. `progress` is
        called as (kind, payload) with kind in {"status", "variant"}.

        The scanner is only locked while snapshotting its inputs; the engine
        run itself takes seconds (10k-game simulations per variant) and must
        not block the log-scanning thread."""
        from src.advisor.deck_builder import suggest_deck

        with self.scanner.lock:
            raw_pool = self.scanner.retrieve_taken_cards() or []
            metrics = self.scanner.retrieve_set_metrics()
            _, event_type = self.scanner.retrieve_current_limited_event()
        pool_key = _pool_key(raw_pool)

        playable_spells = [c for c in raw_pool if "Land" not in c.get("types", [])]
        if len(playable_spells) < MIN_PLAYABLE_SPELLS:
            self.suggestions = {}
            self.selected = ""
            self.status = (
                f"Not enough spells drafted yet (Have {len(playable_spells)}, "
                f"Need {MIN_PLAYABLE_SPELLS})."
            )
            self._built_pool_key = pool_key
            return

        if self.is_building:
            return

        self.is_building = True
        try:
            dataset_name = self.config.card_data.latest_dataset

            def _progress_cb(msg: dict):
                if progress is None:
                    return
                if "status" in msg:
                    progress("status", {"text": msg["status"]})
                elif "variant_label" in msg:
                    progress(
                        "variant",
                        {
                            "archetype": self._archetype_vm(
                                msg["variant_label"], msg["variant_data"]
                            )
                        },
                    )

            results = suggest_deck(
                raw_pool,
                metrics,
                self.config,
                event_type,
                _progress_cb,
                dataset_name,
            )
        except Exception as exc:
            logger.error("Suggest deck build failed: %s", exc, exc_info=True)
            self.suggestions = {}
            self.selected = ""
            self.status = "Builder error — see the log for details."
            return
        finally:
            self.is_building = False

        if not results:
            self.suggestions = {}
            self.selected = ""
            self.status = (
                f"Not enough on-color playables to form a 40-card deck "
                f"(Need {MIN_PLAYABLE_SPELLS})."
            )
            self._built_pool_key = pool_key
            return

        self.suggestions = results
        self.status = ""
        # Snap to the mathematically strongest deck, as _finalize_build did.
        self.selected = next(iter(results))
        self._built_pool_key = pool_key

    def select(self, label: str) -> None:
        if label in self.suggestions:
            self.selected = label

    # --- active deck accessors ----------------------------------------------

    def _active(self) -> Optional[dict]:
        return self.suggestions.get(self.selected)

    def _active_lists(self) -> tuple[List[dict], List[dict]]:
        data = self._active()
        if not data:
            return [], []
        return data.get("deck_cards", []), data.get("sideboard_cards", [])

    def sample_hand(self) -> SampleHandVM:
        deck, _ = self._active_lists()
        return build_sample_hand(deck, self._active_filter())

    def export(self) -> DeckExportVM:
        from src.card_logic import copy_deck

        deck, sideboard = self._active_lists()
        return DeckExportVM(text=copy_deck(deck, sideboard))

    def deck_lists(self) -> tuple[List[dict], List[dict]]:
        """Deep-ish copies for handing the selected deck to the custom-deck
        builder, so edits there don't mutate the cached suggestion."""
        deck, sideboard = self._active_lists()
        return [dict(c) for c in deck], [dict(c) for c in sideboard]

    # --- serialization -------------------------------------------------------

    def _active_filter(self) -> str:
        active = self.config.settings.deck_filter
        return "All Decks" if active == constants.FILTER_OPTION_AUTO else active

    @staticmethod
    def _archetype_vm(label: str, data: dict) -> SuggestArchetypeVM:
        return SuggestArchetypeVM(
            label=label,
            label_prefix=data.get("label_prefix", ""),
            rating=round(float(data.get("rating", 0.0)), 1),
            record=data.get("record", ""),
            colors=list(data.get("colors", []) or []),
            identity_colors=list(data.get("identity_colors", []) or []),
            breakdown=data.get("breakdown", ""),
            main_count=sum(c.get("count", 1) for c in data.get("deck_cards", [])),
        )

    def build_state(self) -> SuggestStateVM:
        with self.scanner.lock:
            current_pool_key = _pool_key(self.scanner.retrieve_taken_cards() or [])
        # Stale: the shown suggestion was built from a pool that no longer
        # matches what the scanner holds — e.g. a freshly finished draft with no
        # build yet (_built_pool_key is None), or the user has drafted more
        # cards since the last build. Deliberately left True on engine error so
        # the frontend can retry instead of pinning an outdated message.
        stale = self._built_pool_key is None or current_pool_key != self._built_pool_key
        active_filter = self._active_filter()
        archetypes = [
            self._archetype_vm(label, data) for label, data in self.suggestions.items()
        ]
        data = self._active()
        if not data:
            return SuggestStateVM(
                status=self.status,
                is_building=self.is_building,
                archetypes=archetypes,
                active_filter=active_filter,
                stale=stale,
            )

        deck, sideboard = self._active_lists()
        deck_sorted = sorted(deck, key=card_sort_key)
        sb_sorted = sorted(sideboard, key=card_sort_key)

        stats = data.get("stats")
        sim = (
            build_sim_result(deck, sideboard, stats, data.get("optimization_note", ""))
            if stats
            else None
        )

        return SuggestStateVM(
            status=self.status,
            is_building=self.is_building,
            archetypes=archetypes,
            selected=self.selected,
            deck=[row_vm(c, active_filter) for c in deck_sorted],
            sideboard=[row_vm(c, active_filter) for c in sb_sorted],
            stats=build_stats(deck),
            main_count=sum(c.get("count", 1) for c in deck),
            sideboard_count=sum(c.get("count", 1) for c in sideboard),
            breakdown=data.get("breakdown", ""),
            sim=sim,
            active_filter=active_filter,
            stale=stale,
        )
