"""
src/sealed_actions.py
Shared action orchestration for the Sealed Studio, consumed by both the
desktop bridge (mtga_bridge.sealed_session) and the legacy tkinter view
(src/ui/windows/sealed_studio.py). Operates on a src.sealed_logic.SealedSession
through pure methods: every action mutates the session and returns an
(ok, message) pair. No tkinter, no pytauri, no viewmodels — presentation,
pool loading, and persistence timing stay in the adapters.

Ticket 09 convergence: the action handlers were previously duplicated verbatim
between the two UIs (auto-generate shells, variant management, move to/from
main, auto-lands, clipboard import/export) and drifted. This module is the
single implementation both sides delegate to.
"""

import logging
import re
from typing import List, Optional, Tuple

from src import constants
from src.advisor.mana_base import calculate_dynamic_mana_base, get_strict_colors
from src.card_logic import copy_deck, count_copies
from src.sealed_logic import SealedSession, generate_sealed_shells
from src.utils import sanitize_card_name

logger = logging.getLogger(__name__)

#: (ok, message) — ok=False means the mutation was refused and the session is
#: unchanged; message is user-facing and UI-agnostic.
ActionResult = Tuple[bool, str]


class SealedStudioActions:
    """Pure action handlers for a SealedSession (the "brain" both UIs delegate
    to). One instance per session; never touches widgets or view-models."""

    def __init__(self, session: SealedSession):
        self.session = session

    # --- shell generation ----------------------------------------------------

    def auto_generate(self, metrics, tier_data=None) -> ActionResult:
        """Builds the 3 candidate shells into the session's variants."""
        if not self.session.master_pool:
            return False, "No sealed pool detected."
        if len(self.session.master_pool) < 40:
            return False, "A sealed pool needs at least 40 cards to build shells."
        generate_sealed_shells(self.session, metrics, tier_data)
        return True, "Generated 3 candidate shells."

    # --- variant management --------------------------------------------------

    def select_variant(self, name: str) -> ActionResult:
        if name in self.session.variants:
            self.session.active_variant_name = name
        return True, ""

    def create_variant(self, name: str, copy_from: Optional[str] = None) -> ActionResult:
        self.session.create_variant(name, copy_from)
        return True, f"Created '{self.session.active_variant_name}'."

    def delete_variant(self, name: str) -> ActionResult:
        if len(self.session.variants) <= 1:
            return False, "Cannot delete the only build."
        self.session.delete_variant(name)
        return True, f"Deleted '{name}'."

    def rename_variant(self, old_name: str, new_name: str) -> ActionResult:
        if not new_name.strip():
            return False, "Name cannot be empty."
        if self.session.rename_variant(old_name, new_name):
            return True, ""
        return False, "Rename failed (name in use?)."

    # --- card movement -------------------------------------------------------

    def move_card(self, card_name: str, to_sideboard: bool, count: int = 1) -> ActionResult:
        if to_sideboard:
            self.session.move_to_sideboard(card_name, count)
            return True, ""
        if self.session.move_to_main(card_name, count):
            return True, ""
        return False, f"Can't add '{card_name}' (not in pool / quantity limit)."

    def clear_deck(self) -> ActionResult:
        if self.session.active_variant_name:
            self.session.variants[
                self.session.active_variant_name
            ].main_deck_counts.clear()
        return True, "Cleared main deck."

    def add_all_to_main(self) -> ActionResult:
        """Moves every sideboard card into the main deck (the legacy studio's
        Add All button)."""
        _, sideboard = self.session.get_active_deck_lists()
        for c in sideboard:
            self.session.move_to_main(c["name"], c.get("count", 1))
        return True, ""

    # --- basic lands ---------------------------------------------------------

    # The legacy sealed_studio.py binds left-click to add and right-click to
    # remove on each basic-land button. move_to_main/move_to_sideboard
    # special-case BASIC_LANDS (sealed_logic.py) so basics bypass the
    # pool-inventory limit the way the legacy buttons did.

    def add_basic(self, color_name: str) -> ActionResult:
        if not self.session.active_variant_name:
            return False, "No build selected."
        self.session.move_to_main(color_name)
        return True, ""

    def remove_basic(self, color_name: str) -> ActionResult:
        if not self.session.active_variant_name:
            return False, "No build selected."
        self.session.move_to_sideboard(color_name)
        return True, ""

    # --- auto-lands ----------------------------------------------------------

    def apply_auto_lands(self) -> ActionResult:
        """Strips basics from the main deck, computes the color-appropriate
        mana base for the remaining spells, and fills the deck back to 40."""
        main_deck, _ = self.session.get_active_deck_lists()
        for c in main_deck:
            if c["name"] in constants.BASIC_LANDS:
                self.session.move_to_sideboard(c["name"], c.get("count", 1))

        main_deck, _ = self.session.get_active_deck_lists()
        spells = [c for c in main_deck if "Land" not in c.get("types", [])]
        non_basic_lands = [c for c in main_deck if "Land" in c.get("types", [])]

        if not spells:
            return False, "Add spells to the deck first."

        colors = get_strict_colors(spells) or ["W", "U", "B", "R", "G"]
        # get_active_deck_lists returns stacked rows, so count copies.
        needed = max(0, 40 - count_copies(spells) - count_copies(non_basic_lands))

        basics_to_add = calculate_dynamic_mana_base(
            spells, non_basic_lands, colors, forced_count=needed
        )
        for b in basics_to_add:
            self.session.move_to_main(b["name"], 1)
        return True, "Mana base optimized."

    # --- clipboard import ----------------------------------------------------

    def import_deck(self, text: str) -> ActionResult:
        """Parses an MTGA decklist string into a new 'Imported Deck' variant.
        Cards that cannot be moved (not in pool / over owned quantity) are
        reported in the message; the rest of the import still succeeds."""
        deck_cards: List[dict] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.lower() in (
                "deck",
                "sideboard",
                "commander",
                "companion",
            ):
                continue
            match = re.match(r"^(\d+)\s+([^(]+)", line)
            if match:
                count = int(match.group(1))
                name = match.group(2).strip()
                deck_cards.append({"name": name, "count": count})

        if not deck_cards:
            return False, "No valid MTGA format cards found in the pasted text."

        self.session.create_variant("Imported Deck")
        self.session.variants[
            self.session.active_variant_name
        ].main_deck_counts.clear()

        missing_cards = []
        for req in deck_cards:
            clean_name = sanitize_card_name(req["name"])
            if not self.session.move_to_main(clean_name, req["count"]):
                # Fallback for DFC imports (which often only list the front face).
                if not self.session.move_to_main(req["name"], req["count"]):
                    missing_cards.append(req["name"])

        if missing_cards:
            preview = ", ".join(missing_cards[:10])
            if len(missing_cards) > 10:
                preview += f" ...and {len(missing_cards) - 10} more."
            return True, (
                "Deck imported, but these cards were skipped (not in pool / over "
                f"owned quantity): {preview}"
            )
        return True, "Deck imported successfully."

    # --- export --------------------------------------------------------------

    def export(self) -> str:
        """MTGA export string for the active deck (clipboard text and the
        sealeddeck.tech payload share the same format)."""
        main_deck, sideboard = self.session.get_active_deck_lists()
        return copy_deck(main_deck, sideboard)
