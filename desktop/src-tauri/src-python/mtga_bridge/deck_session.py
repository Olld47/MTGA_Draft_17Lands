"""
mtga_bridge.deck_session
Headless port of src/ui/windows/custom_deck.py::CustomDeckPanel. Owns the
mutable deck_list / sb_list model and ports every deck-mutation and engine
operation (move, clear, basics, simulate, optimize, auto-lands, sample hand)
as pure methods returning view-models. No tkinter, no pytauri.

The tkinter panel kept deck_list/sb_list as instance attrs and re-rendered
widgets after each mutation; here each mutation returns a DeckStateVM the
frontend re-renders from.
"""

import copy
import logging
from typing import Dict, List

from src import constants
from src.card_logic import (
    copy_deck,
    get_strict_colors,
    stack_cards,
)

from mtga_bridge.deck_view import (
    BASIC_COLOR_MAP as _BASIC_COLOR_MAP,
    build_sample_hand,
    build_sim_result,
    build_stats,
    card_sort_key as _card_sort_key,
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


def _copies(cards: List[Dict]) -> int:
    """Card count of a stacked list, where each row carries a count."""
    return sum(c.get("count", 1) for c in cards)


def _take_copies(cards: List[Dict], limit: int) -> List[Dict]:
    """The first `limit` copies, splitting the row that straddles the boundary."""
    taken: List[Dict] = []
    remaining = limit
    for card in cards:
        if remaining <= 0:
            break
        count = min(card.get("count", 1), remaining)
        row = dict(card)
        row["count"] = count
        taken.append(row)
        remaining -= count
    return taken


class DeckSession:
    """Stateful custom-deck model. One instance per runtime, reused across
    commands. scanner/config supply live pool + display context."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.deck_list: List[Dict] = []
        self.sb_list: List[Dict] = []
        self.known_pool_size = 0

    # --- inbound -------------------------------------------------------------

    def import_deck(self, deck_cards: List[Dict], sb_cards: List[Dict]) -> None:
        self.deck_list = copy.deepcopy(deck_cards)
        self.sb_list = copy.deepcopy(sb_cards)
        raw_pool = self.scanner.retrieve_taken_cards()
        self.known_pool_size = len(raw_pool) if raw_pool else 0

    def refresh_pool(self) -> None:
        """Appends newly-drafted cards to the sideboard (port of refresh())."""
        raw_pool = self.scanner.retrieve_taken_cards()
        if not raw_pool:
            self.deck_list = []
            self.sb_list = []
            self.known_pool_size = 0
            return
        if len(raw_pool) <= self.known_pool_size:
            return
        for pool_card in stack_cards(raw_pool):
            name = pool_card["name"]
            total_count = pool_card.get("count", 1)
            in_deck = next((c for c in self.deck_list if c["name"] == name), {}).get("count", 0)
            in_sb = next((c for c in self.sb_list if c["name"] == name), {}).get("count", 0)
            diff = total_count - (in_deck + in_sb)
            if diff > 0:
                sb_card = next((c for c in self.sb_list if c["name"] == name), None)
                if sb_card:
                    sb_card["count"] += diff
                else:
                    new_c = dict(pool_card)
                    new_c["count"] = diff
                    self.sb_list.append(new_c)
        self.known_pool_size = len(raw_pool)

    # --- mutations -----------------------------------------------------------

    def move_card(self, card_name: str, to_sideboard: bool) -> None:
        source, dest = (
            (self.deck_list, self.sb_list) if to_sideboard else (self.sb_list, self.deck_list)
        )
        src_card = next((c for c in source if c["name"] == card_name), None)
        if not src_card:
            return
        src_card["count"] -= 1
        if src_card["count"] <= 0:
            source.remove(src_card)
        dest_card = next((c for c in dest if c["name"] == card_name), None)
        if dest_card:
            dest_card["count"] += 1
        else:
            new_c = dict(src_card)
            new_c["count"] = 1
            dest.append(new_c)

    def clear_deck(self) -> None:
        for card in list(self.deck_list):
            if card["name"] in constants.BASIC_LANDS:
                self.deck_list.remove(card)
            else:
                sb_card = next((c for c in self.sb_list if c["name"] == card["name"]), None)
                if sb_card:
                    sb_card["count"] += card["count"]
                else:
                    self.sb_list.append(dict(card))
                self.deck_list.remove(card)

    def add_basic(self, color_name: str) -> None:
        color = _BASIC_COLOR_MAP.get(color_name, "")
        dest_card = next((c for c in self.deck_list if c["name"] == color_name), None)
        if dest_card:
            dest_card["count"] += 1
        else:
            self.deck_list.append(
                {
                    "name": color_name,
                    "cmc": 0,
                    "types": ["Land", "Basic"],
                    "colors": [color] if color else [],
                    "count": 1,
                }
            )

    def remove_basic(self, color_name: str) -> None:
        dest_card = next((c for c in self.deck_list if c["name"] == color_name), None)
        if not dest_card:
            return
        dest_card["count"] -= 1
        if dest_card["count"] <= 0:
            self.deck_list.remove(dest_card)

    # --- engine operations --------------------------------------------------

    def run_simulation(self) -> SimResultVM:
        from src.card_logic import simulate_deck

        stats = simulate_deck(self.deck_list, iterations=10000)
        if not stats:
            return SimResultVM(
                ok=False, message="Deck must have 40 cards to analyze.", stats=None
            )
        return self._sim_result(stats, "")

    def auto_optimize(self) -> SimResultVM:
        from src.card_logic import optimize_deck

        base_deck = list(self.deck_list)
        base_sb = list(self.sb_list)
        total_cards = sum(c.get("count", 1) for c in base_deck)
        if total_cards != 40:
            return SimResultVM(
                ok=False,
                message=f"Base deck must be exactly 40 cards to optimize (currently {total_cards}).",
            )
        spells = [c for c in base_deck if "Land" not in c.get("types", [])]
        deck_colors = get_strict_colors(spells)
        archetype_key = "".join(sorted(deck_colors[:2])) if deck_colors else "All Decks"

        final_deck, final_sb, final_stats, opt_note = optimize_deck(
            base_deck, base_sb, archetype_key, deck_colors
        )
        if not final_deck:
            return SimResultVM(ok=False, message="Failed to optimize.")
        self.deck_list = final_deck
        self.sb_list = final_sb
        self.deck_list.sort(key=_card_sort_key)
        self.sb_list.sort(key=_card_sort_key)
        return self._sim_result(final_stats, opt_note)

    def apply_auto_lands(self) -> SimResultVM:
        from src.advisor.mana_base import brute_force_mana_base

        spells = [c for c in self.deck_list if "Land" not in c.get("types", [])]
        non_basic_lands = [
            c
            for c in self.deck_list
            if "Land" in c.get("types", [])
            and "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]
        if not spells:
            return SimResultVM(ok=False, message="Add spells to the deck first.")

        deck_colors = get_strict_colors(spells) or ["W", "U", "B", "R", "G"]
        # Counted in copies, not rows: deck_list is stacked, so a row can be
        # several cards. len() here overshot the land count by one per duplicate
        # spell and produced decks larger than 40.
        total_lands_needed = 40 - _copies(spells)

        if _copies(non_basic_lands) > total_lands_needed:
            non_basic_lands.sort(
                key=lambda x: float(
                    x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                ),
                reverse=True,
            )
            non_basic_lands = _take_copies(non_basic_lands, total_lands_needed)
        needed_basics = max(0, total_lands_needed - _copies(non_basic_lands))

        basics_to_add = brute_force_mana_base(
            spells, non_basic_lands, deck_colors, forced_count=needed_basics
        )

        self.deck_list = [
            c for c in self.deck_list if c["name"] not in constants.BASIC_LANDS
        ]
        for basic in basics_to_add:
            dest_card = next(
                (c for c in self.deck_list if c["name"] == basic["name"]), None
            )
            if dest_card:
                dest_card["count"] += 1
            else:
                self.deck_list.append(dict(basic))

        from src.card_logic import simulate_deck

        stats = simulate_deck(self.deck_list, iterations=10000)
        if not stats:
            return SimResultVM(
                ok=True, message="Lands applied; deck not yet 40 cards.", stats=None
            )
        return self._sim_result(stats, "")

    def _sim_result(self, stats: dict, optimization_note: str) -> SimResultVM:
        return build_sim_result(self.deck_list, self.sb_list, stats, optimization_note)

    def sample_hand(self) -> SampleHandVM:
        return build_sample_hand(self.deck_list, self._active_filter())

    def export(self) -> DeckExportVM:
        return DeckExportVM(text=copy_deck(self.deck_list, self.sb_list))

    # --- serialization -------------------------------------------------------

    def _active_filter(self) -> str:
        active = self.config.settings.deck_filter
        return "All Decks" if active == constants.FILTER_OPTION_AUTO else active

    def _row_vm(self, card: dict) -> DeckRowVM:
        return row_vm(card, self._active_filter())

    def build_state(self) -> DeckStateVM:
        deck_rows = [self._row_vm(c) for c in sorted(self.deck_list, key=_card_sort_key)]
        sb_rows = [self._row_vm(c) for c in sorted(self.sb_list, key=_card_sort_key)]
        return DeckStateVM(
            deck=deck_rows,
            sideboard=sb_rows,
            stats=self._build_stats(),
            main_count=sum(c.get("count", 1) for c in self.deck_list),
            sideboard_count=sum(c.get("count", 1) for c in self.sb_list),
            active_filter=self._active_filter(),
        )

    def _build_stats(self) -> DeckStatsVM:
        return build_stats(self.deck_list)
