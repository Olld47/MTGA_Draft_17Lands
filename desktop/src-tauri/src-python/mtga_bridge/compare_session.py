"""
mtga_bridge.compare_session
Comparison-workspace adapter for the desktop bridge. Loads the card database
and display context from the scanner/config, delegates every mutation and
lookup to the shared src.compare_actions (the single implementation both this bridge and the pre-convergence panel consumed — ticket 09), and
maps the list to view-models for the frontend.

Pure — no pytauri. The mutable compare_list lives in CompareActions;
this session owns only the scanner/config context and the view-model mapping.
The list stays readable as an instance attribute (delegating property) so the
command surface and existing callers are unchanged.
"""

import logging
from typing import Dict, List, Optional

from src.compare_actions import (
    CompareActions,
    available_names,
    find_card,
    resolve_active_filter,
)

from mtga_bridge.snapshot import card_to_vm
from mtga_bridge.viewmodels import CompareStateVM

logger = logging.getLogger(__name__)


class CompareSession:
    """Stateful comparison-workspace adapter. One instance per runtime, reused
    across commands. scanner/config supply the card database + display
    context; the mutable compare_list is owned by the shared CompareActions
    layer."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.actions = CompareActions()

    # State stays readable through the old attribute name (delegation, not a
    # copy) so callers that read compare_list keep working unchanged.
    @property
    def compare_list(self) -> List[Dict]:
        return self.actions.compare_list

    @compare_list.setter
    def compare_list(self, value: List[Dict]) -> None:
        self.actions.compare_list = value

    # --- card database -------------------------------------------------------

    def _card_map(self) -> Dict:
        set_data = getattr(self.scanner, "set_data", None)
        if set_data is None:
            return {}
        return set_data.get_card_ratings() or {}

    def available_names(self) -> List[str]:
        """Sorted, unique card names for the autocomplete search box."""
        return available_names(self._card_map())

    def _find_card(self, name: str) -> Optional[Dict]:
        return find_card(self._card_map(), name)

    # --- mutations -----------------------------------------------------------

    def add_card(self, name: str) -> bool:
        """Resolves the name in the dataset and appends it unless already
        present. Returns True if added."""
        return self.actions.add_card(self._card_map(), name)

    def remove_card(self, name: str) -> None:
        self.actions.remove_card(name)

    def clear(self) -> None:
        self.actions.clear()

    # --- serialization -------------------------------------------------------

    def _active_filter(self) -> str:
        """The deck filter applied against the current pool."""
        raw_pool = self.scanner.retrieve_taken_cards()
        metrics = self.scanner.retrieve_set_metrics()
        return resolve_active_filter(
            raw_pool, self.config.settings.deck_filter, metrics, self.config
        )

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
