"""
src/deck_actions.py
Shared custom-deck model and action orchestration for the Deck Builder,
consumed by both the desktop bridge (mtga_bridge.deck_session) and the
legacy tkinter view (src/ui/windows/custom_deck.py). Pure: owns the mutable
deck_list / sb_list / known_pool_size state and every mutation / engine
operation (move, clear, basics, simulate, optimize, auto-lands, export)
through explicit parameters — raw pool rows come in as arguments, no
scanner/config access. No tkinter, no pytauri, no viewmodels; scanner
locking, thread marshalling, and presentation stay in the adapters.

Ticket 09 convergence: the handlers were previously duplicated verbatim
between the bridge DeckSession and the tkinter CustomDeckPanel (and had
drifted: the panel's simulate handler lacked the 40-card guard and handed
None to the results renderer, and its basic-land color map was a second
inline copy). This module is the single implementation both sides delegate
to.
"""

import copy
import logging
from typing import Dict, List, Optional, Tuple

from src import constants
from src.advisor.mana_base import brute_force_mana_base, get_strict_colors
from src.card_logic import copy_deck, count_copies, stack_cards, take_copies

logger = logging.getLogger(__name__)

BASIC_COLOR_MAP = {
    "Plains": "W",
    "Island": "U",
    "Swamp": "B",
    "Mountain": "R",
    "Forest": "G",
}

#: (ok, message, stats, note) — ok=False means the engine operation was
#: refused and the deck is unchanged; stats is the raw simulate_deck dict on
#: success (None when the deck is not yet analyzable); note is the optimizer's
#: summary line ("" when not applicable).
SimResult = Tuple[bool, str, Optional[dict], str]


def card_sort_key(card: dict):
    return (
        card.get(constants.DATA_FIELD_CMC, 0),
        card.get(constants.DATA_FIELD_NAME, ""),
    )


class DeckActions:
    """Pure custom-deck model (the "brain" both UIs delegate to). One instance
    per panel/session; owns deck_list / sb_list / known_pool_size. Every
    method takes UI/scanner inputs as explicit parameters and returns plain
    data — no widgets, no view-models."""

    def __init__(self):
        self.deck_list: List[Dict] = []
        self.sb_list: List[Dict] = []
        self.known_pool_size = 0

    # --- inbound -------------------------------------------------------------

    def import_deck(self, deck_cards: List[Dict], sb_cards: List[Dict], pool_size: int) -> None:
        self.deck_list = copy.deepcopy(deck_cards)
        self.sb_list = copy.deepcopy(sb_cards)
        self.known_pool_size = pool_size

    def refresh_pool(self, raw_pool) -> None:
        """Appends newly-drafted cards to the sideboard. An empty pool resets
        the deck (a new draft emptied the pool); a pool no larger than the last
        seen size is a no-op."""
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
            in_deck = next(
                (c for c in self.deck_list if c["name"] == name), {}
            ).get("count", 0)
            in_sb = next(
                (c for c in self.sb_list if c["name"] == name), {}
            ).get("count", 0)
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
        """Moves one copy of `card_name` between the main deck and the
        sideboard. Unknown names are a no-op."""
        source, dest = (
            (self.deck_list, self.sb_list)
            if to_sideboard
            else (self.sb_list, self.deck_list)
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
        """Returns every non-basic card to the sideboard and drops basics
        (basics are generated, not drafted — they must not pollute the pool)."""
        for card in list(self.deck_list):
            if card["name"] in constants.BASIC_LANDS:
                self.deck_list.remove(card)
            else:
                sb_card = next(
                    (c for c in self.sb_list if c["name"] == card["name"]), None
                )
                if sb_card:
                    sb_card["count"] += card["count"]
                else:
                    self.sb_list.append(dict(card))
                self.deck_list.remove(card)

    def add_basic(self, color_name: str) -> None:
        color = BASIC_COLOR_MAP.get(color_name, "")
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

    # --- engine operations ----------------------------------------------------

    def run_simulation(self) -> SimResult:
        """Runs the 10K Monte Carlo sim. Refuses decks that simulate_deck
        cannot analyze (fewer than 40 cards)."""
        from src.advisor.simulator import simulate_deck

        stats = simulate_deck(self.deck_list, iterations=10000)
        if not stats:
            return False, "Deck must have 40 cards to analyze.", None, ""
        return True, "", stats, ""

    def auto_optimize(self) -> SimResult:
        """Runs the AI optimize pass over the current deck. On success the
        deck/sideboard are replaced and sorted (cmc, then name)."""
        from src.advisor.deck_builder import optimize_deck

        base_deck = list(self.deck_list)
        base_sb = list(self.sb_list)
        total_cards = sum(c.get("count", 1) for c in base_deck)
        if total_cards != 40:
            return (
                False,
                f"Base deck must be exactly 40 cards to optimize (currently {total_cards}).",
                None,
                "",
            )
        spells = [c for c in base_deck if "Land" not in c.get("types", [])]
        deck_colors = get_strict_colors(spells)
        archetype_key = (
            "".join(sorted(deck_colors[:2])) if deck_colors else "All Decks"
        )

        final_deck, final_sb, final_stats, opt_note = optimize_deck(
            base_deck, base_sb, archetype_key, deck_colors
        )
        if not final_deck:
            return False, "Failed to optimize.", None, ""
        self.deck_list = final_deck
        self.sb_list = final_sb
        self.deck_list.sort(key=card_sort_key)
        self.sb_list.sort(key=card_sort_key)
        return True, "", final_stats, opt_note

    def apply_auto_lands(self) -> SimResult:
        """Strips the basics, computes the color-appropriate mana base for the
        remaining spells, fills the deck back to 40, then sims the result."""
        from src.advisor.simulator import simulate_deck

        spells = [c for c in self.deck_list if "Land" not in c.get("types", [])]
        non_basic_lands = [
            c
            for c in self.deck_list
            if "Land" in c.get("types", [])
            and "Basic" not in c.get("types", [])
            and c.get("name") not in constants.BASIC_LANDS
        ]
        if not spells:
            return False, "Add spells to the deck first.", None, ""

        deck_colors = get_strict_colors(spells) or ["W", "U", "B", "R", "G"]
        # Counted in copies, not rows: deck_list is stacked, so a row can be
        # several cards. len() here overshot the land count by one per
        # duplicate spell and produced decks larger than 40.
        total_lands_needed = 40 - count_copies(spells)

        if count_copies(non_basic_lands) > total_lands_needed:
            non_basic_lands.sort(
                key=lambda x: float(
                    x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                ),
                reverse=True,
            )
            non_basic_lands = take_copies(non_basic_lands, total_lands_needed)
        needed_basics = max(0, total_lands_needed - count_copies(non_basic_lands))

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

        stats = simulate_deck(self.deck_list, iterations=10000)
        if not stats:
            return True, "Lands applied; deck not yet 40 cards.", None, ""
        return True, "", stats, ""

    # --- export ---------------------------------------------------------------

    def export_text(self) -> str:
        """MTGA decklist export string for the current deck + sideboard."""
        return copy_deck(self.deck_list, self.sb_list)
