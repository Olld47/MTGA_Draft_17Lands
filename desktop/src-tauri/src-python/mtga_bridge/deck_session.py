"""
mtga_bridge.deck_session
Custom-deck adapter for the desktop bridge. Loads the draft pool from the
scanner, delegates every mutation and engine operation to the shared
src.deck_actions.DeckActions (the single implementation both this bridge and the pre-convergence panel consumed — ticket 09), and maps results
to view-models for the frontend.

Pure — no pytauri. The mutable deck model lives in DeckActions; this
session owns only the scanner/config context and the view-model mapping.
decks/sideboards stay readable as instance attributes (delegating properties)
so the command surface and existing callers are unchanged.
"""

import logging
from typing import List

from src import constants
from src.deck_actions import DeckActions

from mtga_bridge.deck_view import (
    build_sample_hand,
    build_sim_result,
    build_stats,
    card_sort_key,
    row_vm,
)
from mtga_bridge.viewmodels import (
    DeckExportVM,
    DeckRowVM,
    DeckStateVM,
    DeckStatsVM,
    SampleHandVM,
    SimResultVM,
)

logger = logging.getLogger(__name__)


class DeckSession:
    """Stateful custom-deck adapter. One instance per runtime, reused across
    commands. scanner/config supply live pool + display context; the mutable
    deck model is owned by the shared DeckActions layer."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.actions = DeckActions()

    # State stays readable through the old attribute names (delegation, not
    # copies) so callers that read deck_list/sb_list keep working unchanged.
    @property
    def deck_list(self) -> List[dict]:
        return self.actions.deck_list

    @deck_list.setter
    def deck_list(self, value: List[dict]) -> None:
        self.actions.deck_list = value

    @property
    def sb_list(self) -> List[dict]:
        return self.actions.sb_list

    @sb_list.setter
    def sb_list(self, value: List[dict]) -> None:
        self.actions.sb_list = value

    @property
    def known_pool_size(self) -> int:
        return self.actions.known_pool_size

    @known_pool_size.setter
    def known_pool_size(self, value: int) -> None:
        self.actions.known_pool_size = value

    # --- inbound -------------------------------------------------------------

    def import_deck(self, deck_cards: List[dict], sb_cards: List[dict]) -> None:
        raw_pool = self.scanner.retrieve_taken_cards()
        self.actions.import_deck(
            deck_cards, sb_cards, len(raw_pool) if raw_pool else 0
        )

    def refresh_pool(self) -> None:
        """Appends newly-drafted cards to the sideboard (port of refresh())."""
        self.actions.refresh_pool(self.scanner.retrieve_taken_cards())

    # --- mutations -----------------------------------------------------------

    def move_card(self, card_name: str, to_sideboard: bool) -> None:
        self.actions.move_card(card_name, to_sideboard)

    def clear_deck(self) -> None:
        self.actions.clear_deck()

    def add_basic(self, color_name: str) -> None:
        self.actions.add_basic(color_name)

    def remove_basic(self, color_name: str) -> None:
        self.actions.remove_basic(color_name)

    # --- engine operations ----------------------------------------------------

    def run_simulation(self) -> SimResultVM:
        ok, message, stats, note = self.actions.run_simulation()
        if not ok:
            return SimResultVM(ok=False, message=message, stats=None)
        return self._sim_result(stats, note)

    def auto_optimize(self) -> SimResultVM:
        ok, message, stats, note = self.actions.auto_optimize()
        if not ok:
            return SimResultVM(ok=False, message=message, stats=None)
        return self._sim_result(stats, note)

    def apply_auto_lands(self) -> SimResultVM:
        ok, message, stats, note = self.actions.apply_auto_lands()
        if not ok:
            return SimResultVM(ok=False, message=message, stats=None)
        if stats is None:
            return SimResultVM(ok=True, message=message, stats=None)
        return self._sim_result(stats, note)

    def _sim_result(self, stats: dict, optimization_note: str) -> SimResultVM:
        return build_sim_result(
            self.actions.deck_list, self.actions.sb_list, stats, optimization_note
        )

    def sample_hand(self) -> SampleHandVM:
        return build_sample_hand(self.actions.deck_list, self._active_filter())

    def export(self) -> DeckExportVM:
        return DeckExportVM(text=self.actions.export_text())

    # --- serialization -------------------------------------------------------

    def _active_filter(self) -> str:
        active = self.config.settings.deck_filter
        return "All Decks" if active == constants.FILTER_OPTION_AUTO else active

    def _row_vm(self, card: dict) -> DeckRowVM:
        return row_vm(card, self._active_filter())

    def build_state(self) -> DeckStateVM:
        deck_rows = [
            self._row_vm(c) for c in sorted(self.actions.deck_list, key=card_sort_key)
        ]
        sb_rows = [
            self._row_vm(c) for c in sorted(self.actions.sb_list, key=card_sort_key)
        ]
        return DeckStateVM(
            deck=deck_rows,
            sideboard=sb_rows,
            stats=self._build_stats(),
            main_count=sum(c.get("count", 1) for c in self.actions.deck_list),
            sideboard_count=sum(c.get("count", 1) for c in self.actions.sb_list),
            active_filter=self._active_filter(),
        )

    def _build_stats(self) -> DeckStatsVM:
        return build_stats(self.actions.deck_list)
