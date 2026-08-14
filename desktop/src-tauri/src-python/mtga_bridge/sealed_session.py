"""
mtga_bridge.sealed_session
Sealed Studio adapter for the desktop bridge. Loads the sealed pool from the
scanner, delegates every action to the shared src.sealed_actions.SealedStudioActions
(the single implementation both this bridge and the legacy tkinter studio
consume — ticket 09 convergence), and maps results to view-models for the
frontend.

No tkinter, no pytauri. Pool loading is scanner-driven, clipboard text arrives
as an argument, and every mutation returns a SealedStateVM the frontend
re-renders from. Persistence is an adapter policy: the bridge saves best-effort
after each mutation (the tkinter studio saves on close); the shared actions
layer mutates only.
"""

import logging
from typing import List, Optional

from src import constants
from src.sealed_actions import SealedStudioActions
from src.sealed_logic import SealedSession

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

    def load_external_pool(self, pool: List[dict], session_id: str) -> None:
        """Replaces the scanner-derived pool with one supplied by the caller
        (the practice generator/importer), under its own session id so it
        persists separately from the live draft."""
        session = SealedSession(session_id)
        session.load_pool(pool)
        self.session = session
        self._save()

    # --- shared action delegation --------------------------------------------

    def _actions(self) -> SealedStudioActions:
        return SealedStudioActions(self.session)

    # --- shell generation ----------------------------------------------------

    def auto_generate(self) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        metrics = self.scanner.retrieve_set_metrics()
        tier_data = self.scanner.retrieve_tier_data()
        ok, message = self._actions().auto_generate(metrics, tier_data)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    # --- variant management --------------------------------------------------

    def select_variant(self, name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().select_variant(name)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    def create_variant(self, name: str, copy_from: Optional[str] = None) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().create_variant(name, copy_from)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    def delete_variant(self, name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().delete_variant(name)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    def rename_variant(self, old_name: str, new_name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().rename_variant(old_name, new_name)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    # --- card movement -------------------------------------------------------

    def move_card(self, card_name: str, to_sideboard: bool, count: int = 1) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().move_card(card_name, to_sideboard, count)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    def clear_deck(self) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().clear_deck()
        if ok:
            self._save()
        return self._action(message, ok=ok)

    # --- basic lands ---------------------------------------------------------

    def add_basic(self, color_name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().add_basic(color_name)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    def remove_basic(self, color_name: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().remove_basic(color_name)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    # --- auto-lands ----------------------------------------------------------

    def apply_auto_lands(self) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().apply_auto_lands()
        if ok:
            self._save()
        return self._action(message, ok=ok)

    # --- clipboard import / export -------------------------------------------

    def import_deck(self, text: str) -> SealedActionVM:
        if not self.ensure_pool():
            return self._action("No sealed pool detected.", ok=False)
        ok, message = self._actions().import_deck(text)
        if ok:
            self._save()
        return self._action(message, ok=ok)

    def export(self) -> SealedExportVM:
        if not self.ensure_pool():
            return SealedExportVM(text="")
        return SealedExportVM(text=self._actions().export())

    def export_payload(self) -> str:
        """MTGA export string for the active deck (used by sealeddeck.tech)."""
        if not self.ensure_pool():
            return ""
        return self._actions().export()

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
