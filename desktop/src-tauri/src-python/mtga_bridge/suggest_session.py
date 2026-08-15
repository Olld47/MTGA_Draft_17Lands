"""
mtga_bridge.suggest_session
Suggest Deck adapter for the desktop bridge. Loads the pool/metrics/event-type
snapshot from the scanner and delegates the build pipeline to the shared
src.suggest_actions.SuggestActions (the single implementation both this bridge
and the legacy tkinter panel consume — ticket 09 convergence), then maps the
resulting state to view-models for the frontend. Image loading stays in the
frontend: it reads the Scryfall URLs on DeckRowVM directly instead of
downloading and resizing in Python.

No tkinter, no pytauri. calculate() runs on the caller's thread (a pytauri
worker thread); the scanner is only locked while snapshotting its inputs, and
progress is streamed through a callback the command forwards over a Channel.
"""

import logging
from typing import Callable, List, Optional

from src.suggest_actions import SuggestActions

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


class SuggestSession:
    """Stateful AI-suggestion adapter. One instance per runtime, reused across
    commands. Holds the last build's suggestions and the selected archetype in
    the shared SuggestActions layer."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.actions = SuggestActions()

    # --- shared state (commands/tests read these) ----------------------------

    @property
    def suggestions(self) -> dict:
        return self.actions.suggestions

    @property
    def selected(self) -> str:
        return self.actions.selected

    @property
    def status(self) -> str:
        return self.actions.status

    @property
    def is_building(self) -> bool:
        return self.actions.is_building

    # --- build ---------------------------------------------------------------

    def calculate(self, progress: Optional[Callable[[str, dict], None]] = None) -> None:
        """Delegates the build pipeline to the shared actions layer. `progress`
        is called as (kind, payload) with kind in {"status", "variant"} — the
        bridge formats the engine's raw messages for the frontend here.

        The scanner is only locked while snapshotting its inputs; the engine
        run itself takes seconds (10k-game simulations per variant) and must
        not block the log-scanning thread."""
        # Concurrency guard: a build is already running (e.g. a second
        # suggest_calculate command) — don't start another engine run.
        if self.actions.is_building:
            return

        with self.scanner.lock:
            raw_pool = self.scanner.retrieve_taken_cards() or []
            metrics = self.scanner.retrieve_set_metrics()
            _, event_type = self.scanner.retrieve_current_limited_event()

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

        self.actions.calculate(
            raw_pool,
            metrics,
            event_type,
            self.config,
            progress=_progress_cb,
        )

    def select(self, label: str) -> None:
        self.actions.select(label)

    # --- active deck accessors ----------------------------------------------

    def sample_hand(self) -> SampleHandVM:
        deck, _ = self.actions.active_lists()
        return build_sample_hand(deck, self._active_filter())

    def export(self) -> DeckExportVM:
        return DeckExportVM(text=self.actions.export_text())

    def deck_lists(self) -> tuple[List[dict], List[dict]]:
        """Deep-ish copies for handing the selected deck to the custom-deck
        builder, so edits there don't mutate the cached suggestion."""
        return self.actions.deck_lists()

    # --- serialization -------------------------------------------------------

    def _active_filter(self) -> str:
        from src import constants

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
            current_pool = self.scanner.retrieve_taken_cards() or []
        # Stale: the shown suggestion was built from a pool that no longer
        # matches what the scanner holds — e.g. a freshly finished draft with no
        # build yet, or the user has drafted more cards since the last build.
        # Deliberately left True on engine error so the frontend can retry
        # instead of pinning an outdated message.
        stale = self.actions.is_stale(current_pool)
        active_filter = self._active_filter()
        archetypes = [
            self._archetype_vm(label, data) for label, data in self.suggestions.items()
        ]
        data = self.actions.active()
        if not data:
            return SuggestStateVM(
                status=self.status,
                is_building=self.is_building,
                archetypes=archetypes,
                active_filter=active_filter,
                stale=stale,
            )

        deck, sideboard = self.actions.active_lists()
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
