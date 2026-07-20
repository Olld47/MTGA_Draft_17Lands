"""
mtga_bridge.sealed_session
Headless port of src/ui/windows/sealed_studio.py::SealedStudio. Wraps the
already-pure src.sealed_logic.SealedSession with the studio's action handlers
(auto-generate shells, variant management, move to/from main, auto-lands,
clipboard import, export) as pure methods returning view-models.

No tkinter, no pytauri. The tkinter studio held a SealedSession plus StringVars
and clipboard access; here the pool is loaded from the scanner, clipboard text
arrives as an argument, and every mutation returns a SealedStateVM the frontend
re-renders from.
"""

import logging
import re
from typing import List, Optional

from src import constants
from src.card_logic import copy_deck, get_strict_colors
from src.sealed_logic import SealedSession, generate_sealed_shells
from src.utils import sanitize_card_name

from mtga_bridge.deck_view import build_stats, card_sort_key, row_vm
from mtga_bridge.viewmodels import (
    SealedActionVM,
    SealedExportVM,
    SealedStateVM,
    SealedVariantVM,
)

logger = logging.getLogger(__name__)


class SealedStudioSession:
    """Stateful sealed-pool model. One instance per runtime, reused across
    commands. Lazily loads the pool from the scanner on first access."""

    def __init__(self, scanner, config):
        self.scanner = scanner
        self.config = config
        self.session: Optional[SealedSession] = None

    # --- pool loading --------------------------------------------------------

    def ensure_pool(self) -> bool:
        """Loads the sealed pool from the scanner if not already loaded.
        Returns True when a usable pool is present."""
        if self.session is not None and self.session.master_pool:
            return True

        raw_pool = self.scanner.retrieve_taken_cards()
        if not raw_pool:
            return False

        draft_id = self.scanner.current_draft_id or "local_sealed"
        session = SealedSession.load_session(draft_id, raw_pool)
        if not session:
            session = SealedSession(draft_id)
            session.load_pool(raw_pool)
        self.session = session
        return True

    def reload_pool(self) -> bool:
        """Forces a fresh pool load, discarding the in-memory session."""
        self.session = None
        return self.ensure_pool()

    # --- shell generation ----------------------------------------------------

    def auto_generate(self) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        if len(self.session.master_pool) < 40:
            return self._action(
                "A sealed pool needs at least 40 cards to build shells.", ok=False
            )
        metrics = self.scanner.retrieve_set_metrics()
        tier_data = self.scanner.retrieve_tier_data()
        generate_sealed_shells(self.session, metrics, tier_data)
        self._save()
        return self._action("Generated 3 candidate shells.")

    # --- variant management --------------------------------------------------

    def select_variant(self, name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        if name in self.session.variants:
            self.session.active_variant_name = name
            self._save()
        return self._action()

    def create_variant(self, name: str, copy_from: Optional[str] = None) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        self.session.create_variant(name, copy_from)
        self._save()
        return self._action(f"Created '{self.session.active_variant_name}'.")

    def delete_variant(self, name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        if len(self.session.variants) <= 1:
            return self._action("Cannot delete the only build.", ok=False)
        self.session.delete_variant(name)
        self._save()
        return self._action(f"Deleted '{name}'.")

    def rename_variant(self, old_name: str, new_name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        if not new_name.strip():
            return self._action("Name cannot be empty.", ok=False)
        if self.session.rename_variant(old_name, new_name):
            self._save()
            return self._action()
        return self._action("Rename failed (name in use?).", ok=False)

    # --- card movement -------------------------------------------------------

    def move_card(self, card_name: str, to_sideboard: bool, count: int = 1) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        if to_sideboard:
            self.session.move_to_sideboard(card_name, count)
        else:
            if not self.session.move_to_main(card_name, count):
                return self._action(
                    f"Can't add '{card_name}' (not in pool / quantity limit).", ok=False
                )
        self._save()
        return self._action()

    def clear_deck(self) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        if self.session.active_variant_name:
            self.session.variants[
                self.session.active_variant_name
            ].main_deck_counts.clear()
            self._save()
        return self._action("Cleared main deck.")

    # --- auto-lands (port of _apply_auto_lands) ------------------------------

    def apply_auto_lands(self) -> SealedActionVM:
        from src.card_logic import calculate_dynamic_mana_base

        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)

        main_deck, _ = self.session.get_active_deck_lists()
        for c in main_deck:
            if c["name"] in constants.BASIC_LANDS:
                self.session.move_to_sideboard(c["name"], c.get("count", 1))

        main_deck, _ = self.session.get_active_deck_lists()
        spells = [c for c in main_deck if "Land" not in c.get("types", [])]
        non_basic_lands = [c for c in main_deck if "Land" in c.get("types", [])]

        if not spells:
            return self._action("Add spells to the deck first.", ok=False)

        colors = get_strict_colors(spells) or ["W", "U", "B", "R", "G"]
        needed = max(0, 40 - len(spells) - len(non_basic_lands))

        basics_to_add = calculate_dynamic_mana_base(
            spells, non_basic_lands, colors, forced_count=needed
        )
        for b in basics_to_add:
            self.session.move_to_main(b["name"], 1)

        self._save()
        return self._action("Mana base optimized.")

    # --- clipboard import (port of _import_deck_from_clipboard) ---------------

    def import_deck(self, text: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)

        deck_cards = []
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
            return self._action(
                "No valid MTGA format cards found in the pasted text.", ok=False
            )

        self.session.create_variant("Imported Deck")
        self.session.variants[
            self.session.active_variant_name
        ].main_deck_counts.clear()

        missing_cards = []
        for req in deck_cards:
            clean_name = sanitize_card_name(req["name"])
            success = self.session.move_to_main(clean_name, req["count"])
            if not success:
                success = self.session.move_to_main(req["name"], req["count"])
                if not success:
                    missing_cards.append(req["name"])

        self._save()

        if missing_cards:
            preview = ", ".join(missing_cards[:10])
            if len(missing_cards) > 10:
                preview += f" ...and {len(missing_cards) - 10} more."
            return self._action(
                f"Deck imported, but these cards were skipped (not in pool / over "
                f"owned quantity): {preview}"
            )
        return self._action("Deck imported successfully.")

    # --- export --------------------------------------------------------------

    def export(self) -> SealedExportVM:
        if not self.ensure_pool():
            return SealedExportVM(text="")
        main_deck, sideboard = self.session.get_active_deck_lists()
        return SealedExportVM(text=copy_deck(main_deck, sideboard))

    def export_payload(self) -> str:
        """MTGA export string for the active deck (used by sealeddeck.tech)."""
        if not self.ensure_pool():
            return ""
        main_deck, sideboard = self.session.get_active_deck_lists()
        return copy_deck(main_deck, sideboard)

    # --- serialization -------------------------------------------------------

    def _save(self) -> None:
        if self.session is not None:
            try:
                self.session.save_session()
            except Exception as exc:  # persistence is best-effort
                logger.warning("Failed to persist sealed session: %s", exc)

    def _active_filter(self) -> str:
        active = self.config.settings.deck_filter
        return "All Decks" if active == constants.FILTER_OPTION_AUTO else active

    def _variant_vms(self) -> List[SealedVariantVM]:
        vms = []
        for name, variant in self.session.variants.items():
            vms.append(
                SealedVariantVM(
                    name=name,
                    is_active=(name == self.session.active_variant_name),
                    main_count=sum(variant.main_deck_counts.values()),
                )
            )
        return vms

    def build_state(self) -> SealedStateVM:
        if self.session is None or not self.session.master_pool:
            return SealedStateVM(has_pool=False)

        active_filter = self._active_filter()
        main_deck, sideboard = self.session.get_active_deck_lists()
        deck_rows = [row_vm(c, active_filter) for c in sorted(main_deck, key=card_sort_key)]
        sb_rows = [row_vm(c, active_filter) for c in sorted(sideboard, key=card_sort_key)]
        return SealedStateVM(
            has_pool=True,
            pool_size=sum(c.get("count", 1) for c in self.session.master_pool),
            session_id=self.session.session_id,
            variants=self._variant_vms(),
            active_variant=self.session.active_variant_name,
            deck=deck_rows,
            sideboard=sb_rows,
            stats=build_stats(main_deck),
            main_count=sum(c.get("count", 1) for c in main_deck),
            sideboard_count=sum(c.get("count", 1) for c in sideboard),
            active_filter=active_filter,
        )

    def _action(self, message: str = "", ok: bool = True) -> SealedActionVM:
        return SealedActionVM(ok=ok, message=message, state=self.build_state())
