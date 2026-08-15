"""
src/draft_session.py

The persistence seam for ArenaScanner (ticket 12). DraftSession is the single
authority for the scanner's persisted state — draft identity, pack/pick, card
pools, draft history, and the log cursors — plus the state-file
load/save/clear/complete migrations that used to live inline in
src/log_scanner.py.

The scanner keeps same-name adapter properties over these fields (no second
copy); this module owns the JSON contract: the exact state-file keys, the
v4.19 legacy draft_type coercion, the truncation-recovery file_size, and the
partial/full clear and completion migrations. draft_start_offset, sideboard
and data_source are runtime-only: the first two live here without JSON keys,
data_source stays scanner-owned and never enters the session.

This module is internal to the scanner: it imports only the standard library,
src.constants and src.logger, so it passes the 02 layering lint (no tkinter /
ttkbootstrap / src.ui).
"""

import json
import os
from typing import Optional

import src.constants as constants
from src.logger import create_logger

logger = create_logger()


class LogOffset:
    """A mutable log-cursor position passed by object reference to the scan
    helpers. Replaces the old offset_attr string reflection: renaming a scanner
    offset attribute now raises AttributeError at the call site instead of
    silently breaking a getattr/setattr round-trip."""

    __slots__ = ("position",)

    def __init__(self, position: int = 0):
        self.position = position


class DraftSession:
    """The single authority for ArenaScanner's draft state and its persistence.

    Owns identity, pack/pick, pools/history, and the log cursors (three
    mutable LogOffset objects plus the search/draft-start/file-size scalars),
    and the state-file JSON contract. The scanner holds no second copy of
    these fields and never reads or writes the JSON itself — it delegates
    through adapter properties and calls save/clear/complete on the session.

    Phase is deliberately NOT maintained here: derive_scanner_phase
    (src/scanner_state.py) keeps computing the phase from these fields, and
    the scanner recomputes it at the same transition points as before.
    """

    def __init__(self, state_file: str, number_of_players: int = 8):
        self.state_file = state_file

        # Identity
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN
        self.draft_label = ""
        self.draft_sets = []
        self.event_string = ""
        self.current_draft_id = ""
        self.current_transaction_id = ""
        self.draft_start_time = ""
        self.number_of_players = number_of_players

        # Pack/pick
        self.current_pack = 0
        self.current_pick = 0
        self.current_picked_pick = 0
        self.previous_scanned_pack = 0
        self.previous_picked_pack = 0

        # Pools / history
        self.taken_cards = []
        self.picked_cards = [[] for _ in range(number_of_players)]
        self.pack_cards = [[] for _ in range(number_of_players)]
        self.initial_pack = [[] for _ in range(number_of_players)]
        self.sideboard = []
        self.draft_history = []

        # Cursors / runtime recovery. pick/pack/pool offsets are mutable
        # LogOffset objects the scanner's scan helpers advance by reference;
        # search_offset/draft_start_offset/file_size are scalars.
        self.pick_offset = LogOffset()
        self.pack_offset = LogOffset()
        self.pool_offset = LogOffset()
        self.search_offset = 0
        self.draft_start_offset = 0
        self.file_size = 0

    def load(self, target_draft_id: Optional[str] = None) -> bool:
        """Recovers the active draft state if the app was closed mid-draft.

        Returns False when the state file is missing or unreadable, or when
        target_draft_id is given and does not strictly (string) match the
        persisted current_draft_id — memory is left untouched in that case.
        On success every state key is read with its pre-refactor default.
        """
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                # If an ID is provided, strictly match it.
                if target_draft_id is not None and str(
                    state.get("current_draft_id", "")
                ) != str(target_draft_id):
                    return False

                self.draft_type = state.get(
                    "draft_type", constants.LIMITED_TYPE_UNKNOWN
                )
                # States saved before v4.19 could hold an event-name string
                # (e.g. "ContenderDraft"), which matches no parser dispatch.
                if not isinstance(self.draft_type, int):
                    self.draft_type = constants.LIMITED_TYPES_DICT.get(
                        self.draft_type, constants.LIMITED_TYPE_UNKNOWN
                    )
                self.draft_sets = state.get("draft_sets", [])
                self.draft_label = state.get("draft_label", "")
                self.event_string = state.get("event_string", "")
                self.current_draft_id = state.get("current_draft_id", "")
                self.current_transaction_id = state.get("current_transaction_id", "")
                self.number_of_players = state.get("number_of_players", 8)
                self.taken_cards = state.get("taken_cards", [])
                self.picked_cards = state.get(
                    "picked_cards", [[] for _ in range(self.number_of_players)]
                )
                self.initial_pack = state.get(
                    "initial_pack", [[] for _ in range(self.number_of_players)]
                )
                self.pack_cards = state.get(
                    "pack_cards", [[] for _ in range(self.number_of_players)]
                )
                self.current_pack = state.get("current_pack", 0)
                self.current_pick = state.get("current_pick", 0)
                self.previous_scanned_pack = state.get("previous_scanned_pack", 0)
                self.previous_picked_pack = state.get("previous_picked_pack", 0)
                self.current_picked_pick = state.get("current_picked_pick", 0)
                self.draft_history = state.get("draft_history", [])
                self.draft_start_time = state.get("draft_start_time", "")

                # Scan pointers resume where the app left off so a reopened
                # mid-draft never re-scans old EventJoins and wipes the
                # restored pool. file_size makes the truncation check in
                # draft_start_search work across restarts (a recreated log is
                # smaller than the saved size → full clear_draft(True)).
                self.search_offset = state.get("search_offset", 0)
                self.pick_offset.position = state.get("pick_offset", 0)
                self.pack_offset.position = state.get("pack_offset", 0)
                self.pool_offset.position = state.get("pool_offset", 0)
                self.file_size = state.get("file_size", 0)

                if self.draft_type != constants.LIMITED_TYPE_UNKNOWN:
                    logger.info(
                        f"Restored previous draft state: {self.event_string} "
                        f"(Pack {self.current_pack}, Pick {self.current_pick})"
                    )

                return True
        except Exception as e:
            logger.error(f"Failed to load draft state: {e}")
        return False

    def save(self) -> None:
        """Persists the memory state to disk to survive application crashes.

        Writes the pre-refactor state keys verbatim — including the three
        offset positions — and swallows IO errors with the existing error log
        (never raises into the scan callers). Runtime-only fields
        (draft_start_offset, sideboard, data_source) are not persisted.
        """
        try:
            state = {
                "draft_type": self.draft_type,
                "draft_sets": self.draft_sets,
                "draft_label": self.draft_label,
                "event_string": self.event_string,
                "current_draft_id": self.current_draft_id,
                "current_transaction_id": self.current_transaction_id,
                "number_of_players": self.number_of_players,
                "taken_cards": self.taken_cards,
                "picked_cards": self.picked_cards,
                "initial_pack": self.initial_pack,
                "pack_cards": self.pack_cards,
                "current_pack": self.current_pack,
                "current_pick": self.current_pick,
                "previous_scanned_pack": self.previous_scanned_pack,
                "previous_picked_pack": self.previous_picked_pack,
                "current_picked_pick": self.current_picked_pick,
                "draft_history": self.draft_history,
                "draft_start_time": self.draft_start_time,
                "search_offset": self.search_offset,
                "pick_offset": self.pick_offset.position,
                "pack_offset": self.pack_offset.position,
                "pool_offset": self.pool_offset.position,
                "file_size": self.file_size,
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save draft state: {e}")

    def clear(self, full_clear: bool) -> None:
        """Resets the draft state (the exact pre-refactor clear_draft split).

        full_clear additionally resets the search/draft-start/file-size
        cursors and the transaction id, deletes the state file (a failed
        delete is ignored, matching the old code), and does not re-save.
        A partial clear resets the draft state and persists it.
        """
        if full_clear:
            self.search_offset = 0
            self.draft_start_offset = 0
            self.file_size = 0
            self.current_transaction_id = ""
            if os.path.exists(self.state_file):
                try:
                    os.remove(self.state_file)
                except Exception:
                    pass

        self.draft_type = constants.LIMITED_TYPE_UNKNOWN
        self.pick_offset.position = 0
        self.pack_offset.position = 0
        self.pool_offset.position = 0
        self.draft_sets = None
        self.current_pick = 0
        self.current_pack = 0
        self.previous_scanned_pack = 0
        self.previous_picked_pack = 0
        self.current_picked_pick = 0
        self.number_of_players = 8
        self.picked_cards = [[] for _ in range(self.number_of_players)]
        self.pack_cards = [[] for _ in range(self.number_of_players)]
        self.initial_pack = [[] for _ in range(self.number_of_players)]
        self.taken_cards = []
        self.sideboard = []
        self.draft_label = ""
        self.draft_history = []
        self.current_draft_id = ""
        self.event_string = ""
        self.draft_start_time = ""

        if not full_clear:
            self.save()

    def complete(self) -> None:
        """Retires the live pack/pick of a finished draft (was
        _mark_draft_complete's migration).

        The drafted pool (taken_cards) and draft history are kept so the recap
        of the finished draft still works; only the live "currently drafting"
        state is retired. draft_type is reset to UNKNOWN so the next EventJoin
        is treated as a fresh draft. The event identity (event_string /
        draft_label / draft_sets) is preserved — the recap gate
        (compute_draft_complete) keys off draft_label, so wiping it here would
        permanently block the recap. The result is persisted.
        """
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN
        self.current_pack = 0
        self.current_pick = 0
        self.previous_scanned_pack = 0
        self.previous_picked_pack = 0
        self.current_picked_pick = 0
        self.picked_cards = [[] for _ in range(self.number_of_players)]
        self.pack_cards = [[] for _ in range(self.number_of_players)]
        self.initial_pack = [[] for _ in range(self.number_of_players)]
        self.save()
