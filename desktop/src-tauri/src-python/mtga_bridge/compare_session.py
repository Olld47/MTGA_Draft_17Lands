"""
mtga_bridge.compare_session
Headless port of src/ui/windows/compare.py::ComparePanel. Owns the mutable
compare_list (the set of cards the user has pinned for side-by-side
comparison) and renders each as a full CardVM under the active deck-color
filter, including 17Lands stats and tier ratings. Pure — no tkinter, no
pytauri.

The tkinter panel maintained compare_list as an instance attr and re-rendered
a Treeview after each mutation; here each mutation is followed by build_state()
returning a CompareStateVM the frontend re-renders from.
"""

import logging
from typing import Dict, List, Optional

from src import constants
from src.card_logic import filter_options

from mtga_bridge.snapshot import card_to_vm
from mtga_bridge.viewmodels import CompareStateVM

logger = logging.getLogger(__name__)


class CompareSession:
    """Stateful comparison workspace. One instance per runtime, reused across
    commands. scanner/config supply the card database + display context."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.compare_list: List[Dict] = []

    # --- card database -------------------------------------------------------

    def _card_map(self) -> Dict:
        set_data = getattr(self.scanner, "set_data", None)
        if set_data is None:
            return {}
        return set_data.get_card_ratings() or {}

    def available_names(self) -> List[str]:
        """Sorted, unique card names for the autocomplete search box."""
        names = {v.get("name", "") for v in self._card_map().values()}
        names.discard("")
        return sorted(names)

    def _find_card(self, name: str) -> Optional[Dict]:
        typed = (name or "").strip().lower()
        if not typed:
            return None
        return next(
            (d for d in self._card_map().values() if d.get("name", "").lower() == typed),
            None,
        )

    # --- mutations -----------------------------------------------------------

    def add_card(self, name: str) -> bool:
        """Port of ComparePanel._add_card: resolves the name in the dataset and
        appends it unless already present. Returns True if added."""
        found = self._find_card(name)
        if not found:
            return False
        if any(c.get("name") == found.get("name") for c in self.compare_list):
            return False
        self.compare_list.append(found)
        return True

    def remove_card(self, name: str) -> None:
        self.compare_list = [c for c in self.compare_list if c.get("name") != name]

    def clear(self) -> None:
        self.compare_list = []

    # --- serialization -------------------------------------------------------

    def _active_filter(self) -> str:
        """Port of ComparePanel._update_content's color resolution: the deck
        filter applied against the current pool."""
        raw_pool = self.scanner.retrieve_taken_cards()
        metrics = self.scanner.retrieve_set_metrics()
        colors = filter_options(
            raw_pool, self.config.settings.deck_filter, metrics, self.config
        )
        return colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS

    def build_state(self) -> CompareStateVM:
        active = self._active_filter()
        tier_data = self.scanner.retrieve_tier_data()
        cards = [
            card_to_vm(card, active, tier_data=tier_data) for card in self.compare_list
        ]
        return CompareStateVM(
            cards=cards,
            active_filter=active,
            available_names=self.available_names(),
        )
