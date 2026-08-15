"""
src/compare_actions.py
Shared comparison-workspace logic for the Card Compare tab, consumed by both
the desktop bridge (mtga_bridge.compare_session) and the legacy tkinter view
(src/ui/windows/compare.py). Pure: owns the mutable compare_list and the
card-database lookups, dedup, and deck-color resolution — no tkinter, no
pytauri, no viewmodels. Scanner/config access and presentation stay in the
adapters.

Ticket 09 convergence: the lookup/dedup and color-resolution code was
duplicated verbatim between the bridge session and the tkinter panel (and had
drifted: the panel's completion list included blanks and unsorted names, and
its duplicate check compared dict objects instead of names). This module is
the single implementation both sides delegate to.
"""

import logging
from typing import Dict, List, Optional

from src import constants
from src.card_logic import filter_options

logger = logging.getLogger(__name__)


def available_names(card_map: Dict) -> List[str]:
    """Sorted, unique card names for the autocomplete search box."""
    names = {v.get("name", "") for v in card_map.values()}
    names.discard("")
    return sorted(names)


def find_card(card_map: Dict, name: str) -> Optional[Dict]:
    """Case-insensitive lookup of a card by name in the card database."""
    typed = (name or "").strip().lower()
    if not typed:
        return None
    return next(
        (d for d in card_map.values() if d.get("name", "").lower() == typed),
        None,
    )


def resolve_active_filter(raw_pool, deck_filter, metrics, config) -> str:
    """The deck-color filter to apply against the current pool; 'All Decks'
    when the pool or filter resolves to nothing."""
    colors = filter_options(raw_pool, deck_filter, metrics, config)
    return colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS


class CompareActions:
    """Pure comparison-workspace model (the "brain" both UIs delegate to).
    Owns the mutable compare_list; lookups take the card database as an
    explicit parameter."""

    def __init__(self):
        self.compare_list: List[Dict] = []

    def add_card(self, card_map: Dict, name: str) -> bool:
        """Resolves `name` in the card database and appends it unless a card
        of the same name is already present. Returns True if added."""
        found = find_card(card_map, name)
        if not found:
            return False
        if any(c.get("name") == found.get("name") for c in self.compare_list):
            return False
        self.compare_list.append(found)
        return True

    def add_card_data(self, card_data: Optional[Dict]) -> bool:
        """Appends a pre-resolved card (e.g. pushed from another tab) unless
        a card of the same name is already present. Returns True if added."""
        if not card_data:
            return False
        if any(c.get("name") == card_data.get("name") for c in self.compare_list):
            return False
        self.compare_list.append(card_data)
        return True

    def remove_card(self, name: str) -> None:
        self.compare_list = [c for c in self.compare_list if c.get("name") != name]

    def clear(self) -> None:
        self.compare_list = []
