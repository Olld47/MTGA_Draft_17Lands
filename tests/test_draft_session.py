"""
tests/test_draft_session.py

Pure-layer persistence tests for ticket 12 — DraftSession (src/draft_session.py)
is the single authority for ArenaScanner's persisted state. Constructed with
tmp_path state files only, no tkinter/ttkbootstrap and no UI, mirroring
tests/test_scanner_state.py. Pins the state-file JSON contract: every
persisted key survives a save/load round-trip, the three offset positions,
defaults for missing keys, target_draft_id strict matching, the v4.19 legacy
draft_type string coercion, the runtime-only fields that must NOT become JSON
keys, and the partial/full clear + completion migrations.
"""

import json

import pytest

import src.constants as constants
from src.draft_session import DraftSession, LogOffset


STATE_FILE_NAME = "active_draft_state.json"


def _state_path(tmp_path):
    return str(tmp_path / STATE_FILE_NAME)


def _filled_session(tmp_path, draft_id="draft_abc"):
    """A session with every persisted field populated (4-player PickTwo-like
    pool shape so the per-player list defaults are distinguishable from 8)."""
    s = DraftSession(_state_path(tmp_path))
    s.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    s.draft_label = "PremierDraft"
    s.draft_sets = ["MSH"]
    s.event_string = "PremierDraft_MSH_20260731"
    s.current_draft_id = draft_id
    s.current_transaction_id = "txn_abc"
    s.draft_start_time = "2026-07-31T12:00:00"
    s.number_of_players = 4
    s.taken_cards = ["1000", "1001", "1002"]
    s.picked_cards = [["1000"], [], ["1002"], []]
    s.pack_cards = [["9", "8"], [], [], []]
    s.initial_pack = [["9", "8", "7"], [], [], []]
    s.sideboard = ["2000"]  # runtime-only: never persisted
    s.draft_history = [{"Pack": 1, "Pick": 1, "Cards": ["1000"]}]
    s.current_pack = 2
    s.current_pick = 3
    s.current_picked_pick = 3
    s.previous_scanned_pack = 2
    s.previous_picked_pack = 2
    s.search_offset = 1111
    s.pick_offset.position = 2222
    s.pack_offset.position = 3333
    s.pool_offset.position = 4444
    s.draft_start_offset = 5555  # runtime-only: never persisted
    s.file_size = 6666
    return s


# --- Fresh-session defaults --------------------------------------------------

def test_fresh_session_defaults(tmp_path):
    """The pre-refactor initial values: unknown draft type, empty identity /
    history / pools, zero pack/pick and cursors, 8 players, three 8-slot
    per-player lists."""
    s = DraftSession(_state_path(tmp_path))
    assert s.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert s.draft_label == ""
    assert s.draft_sets == []
    assert s.event_string == ""
    assert s.current_draft_id == ""
    assert s.current_transaction_id == ""
    assert s.draft_start_time == ""
    assert s.number_of_players == 8
    assert s.current_pack == 0
    assert s.current_pick == 0
    assert s.current_picked_pick == 0
    assert s.previous_scanned_pack == 0
    assert s.previous_picked_pack == 0
    assert s.taken_cards == []
    assert s.picked_cards == [[] for _ in range(8)]
    assert s.pack_cards == [[] for _ in range(8)]
    assert s.initial_pack == [[] for _ in range(8)]
    assert s.sideboard == []
    assert s.draft_history == []
    assert isinstance(s.pick_offset, LogOffset)
    assert s.pick_offset.position == 0
    assert s.pack_offset.position == 0
    assert s.pool_offset.position == 0
    assert s.search_offset == 0
    assert s.draft_start_offset == 0
    assert s.file_size == 0
    assert s.load() is False  # no state file yet


# --- Save/load round-trip ----------------------------------------------------

def test_save_load_round_trip_preserves_every_state_key(tmp_path):
    """Every persisted key survives save → load: identity, pools/history,
    pack/pick, the three offset positions and file_size."""
    s = _filled_session(tmp_path)
    s.save()

    fresh = DraftSession(_state_path(tmp_path))
    assert fresh.load("draft_abc") is True

    assert fresh.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    assert fresh.draft_label == "PremierDraft"
    assert fresh.draft_sets == ["MSH"]
    assert fresh.event_string == "PremierDraft_MSH_20260731"
    assert fresh.current_draft_id == "draft_abc"
    assert fresh.current_transaction_id == "txn_abc"
    assert fresh.draft_start_time == "2026-07-31T12:00:00"
    assert fresh.number_of_players == 4
    assert fresh.taken_cards == ["1000", "1001", "1002"]
    assert fresh.picked_cards == [["1000"], [], ["1002"], []]
    assert fresh.pack_cards == [["9", "8"], [], [], []]
    assert fresh.initial_pack == [["9", "8", "7"], [], [], []]
    assert fresh.draft_history == [{"Pack": 1, "Pick": 1, "Cards": ["1000"]}]
    assert fresh.current_pack == 2
    assert fresh.current_pick == 3
    assert fresh.current_picked_pick == 3
    assert fresh.previous_scanned_pack == 2
    assert fresh.previous_picked_pack == 2
    assert fresh.search_offset == 1111
    assert fresh.pick_offset.position == 2222
    assert fresh.pack_offset.position == 3333
    assert fresh.pool_offset.position == 4444
    assert fresh.file_size == 6666


def test_state_file_contract_excludes_runtime_only_fields(tmp_path):
    """draft_start_offset, sideboard and data_source are runtime-only: they
    must not appear as JSON keys (the pre-refactor contract never persisted
    them), while every persisted key keeps its exact name."""
    s = _filled_session(tmp_path)
    s.save()
    raw = json.loads((tmp_path / STATE_FILE_NAME).read_text(encoding="utf-8"))

    assert "draft_start_offset" not in raw
    assert "sideboard" not in raw
    assert "data_source" not in raw
    for key in (
        "draft_type",
        "draft_sets",
        "draft_label",
        "event_string",
        "current_draft_id",
        "current_transaction_id",
        "number_of_players",
        "taken_cards",
        "picked_cards",
        "initial_pack",
        "pack_cards",
        "current_pack",
        "current_pick",
        "previous_scanned_pack",
        "previous_picked_pack",
        "current_picked_pick",
        "draft_history",
        "draft_start_time",
        "search_offset",
        "pick_offset",
        "pack_offset",
        "pool_offset",
        "file_size",
    ):
        assert key in raw


def test_load_missing_file_returns_false(tmp_path):
    s = DraftSession(_state_path(tmp_path))
    assert s.load() is False


def test_load_target_match_returns_true(tmp_path):
    s = _filled_session(tmp_path)
    s.save()
    fresh = DraftSession(_state_path(tmp_path))
    assert fresh.load("draft_abc") is True
    assert fresh.current_draft_id == "draft_abc"


def test_load_without_target_loads_any_persisted_draft(tmp_path):
    s = _filled_session(tmp_path)
    s.save()
    fresh = DraftSession(_state_path(tmp_path))
    assert fresh.load() is True
    assert fresh.event_string == "PremierDraft_MSH_20260731"


def test_load_target_mismatch_returns_false_and_leaves_memory_untouched(tmp_path):
    """A non-matching target_draft_id returns False without touching memory —
    the pre-refactor contract (a failed _load_state must not clobber the
    in-memory draft the scanner is about to wipe-check against)."""
    s = _filled_session(tmp_path)
    s.save()

    fresh = DraftSession(_state_path(tmp_path))
    assert fresh.load("other_draft") is False
    assert fresh.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert fresh.current_draft_id == ""
    assert fresh.taken_cards == []
    assert fresh.pick_offset.position == 0
    assert fresh.search_offset == 0


def test_load_applies_defaults_for_missing_keys(tmp_path):
    """A minimal state file (only draft_type) loads with every other key at
    its default, including the player-count-derived per-player lists."""
    (tmp_path / STATE_FILE_NAME).write_text(
        json.dumps({"draft_type": constants.LIMITED_TYPE_DRAFT_QUICK})
    )
    s = DraftSession(_state_path(tmp_path))
    assert s.load() is True
    assert s.draft_type == constants.LIMITED_TYPE_DRAFT_QUICK
    assert s.draft_sets == []
    assert s.draft_label == ""
    assert s.event_string == ""
    assert s.current_draft_id == ""
    assert s.current_transaction_id == ""
    assert s.draft_start_time == ""
    assert s.number_of_players == 8
    assert s.taken_cards == []
    assert s.picked_cards == [[] for _ in range(8)]
    assert s.pack_cards == [[] for _ in range(8)]
    assert s.initial_pack == [[] for _ in range(8)]
    assert s.current_pack == 0
    assert s.current_pick == 0
    assert s.previous_scanned_pack == 0
    assert s.previous_picked_pack == 0
    assert s.current_picked_pick == 0
    assert s.draft_history == []
    assert s.search_offset == 0
    assert s.pick_offset.position == 0
    assert s.pack_offset.position == 0
    assert s.pool_offset.position == 0
    assert s.file_size == 0


# --- Legacy draft_type coercion (states saved before v4.19) ------------------

def test_load_coerces_legacy_string_draft_type(tmp_path):
    """A persisted event-name string (e.g. "ContenderDraft") matches no parser
    dispatch; loading must coerce it to the int type code."""
    (tmp_path / STATE_FILE_NAME).write_text(
        json.dumps({"draft_type": "ContenderDraft", "current_draft_id": "d"})
    )
    s = DraftSession(_state_path(tmp_path))
    assert s.load() is True
    assert s.draft_type == constants.LIMITED_TYPE_DRAFT_CONTENDER


def test_load_unknown_event_name_becomes_unknown_type(tmp_path):
    """A string that maps to no known limited type falls back to UNKNOWN."""
    (tmp_path / STATE_FILE_NAME).write_text(
        json.dumps({"draft_type": "MysteryFormat"})
    )
    s = DraftSession(_state_path(tmp_path))
    assert s.load() is True
    assert s.draft_type == constants.LIMITED_TYPE_UNKNOWN


# --- Clear migrations --------------------------------------------------------

def test_partial_clear_resets_draft_state_and_saves(tmp_path):
    """clear(full_clear=False) resets the draft state (draft_sets → None keeps
    the pre-refactor None semantics) but keeps the state file and re-persists
    the reset state."""
    s = _filled_session(tmp_path)
    s.save()
    assert (tmp_path / STATE_FILE_NAME).exists()

    s.clear(full_clear=False)

    assert s.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert s.draft_sets is None
    assert s.draft_label == ""
    assert s.event_string == ""
    assert s.current_draft_id == ""
    # Only full clear resets the transaction id (the pre-refactor split: a
    # partial clear is an event re-registration, which overwrites the id right
    # after in __check_event).
    assert s.current_transaction_id == "txn_abc"
    assert s.draft_start_time == ""
    assert s.number_of_players == 8
    assert s.current_pack == 0
    assert s.current_pick == 0
    assert s.current_picked_pick == 0
    assert s.previous_scanned_pack == 0
    assert s.previous_picked_pack == 0
    assert s.taken_cards == []
    assert s.picked_cards == [[] for _ in range(8)]
    assert s.pack_cards == [[] for _ in range(8)]
    assert s.initial_pack == [[] for _ in range(8)]
    assert s.sideboard == []
    assert s.draft_history == []
    assert s.pick_offset.position == 0
    assert s.pack_offset.position == 0
    assert s.pool_offset.position == 0

    # Partial clear persists: a fresh session reloads the reset state.
    assert (tmp_path / STATE_FILE_NAME).exists()
    fresh = DraftSession(_state_path(tmp_path))
    assert fresh.load() is True
    assert fresh.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert fresh.taken_cards == []
    assert fresh.pack_cards == [[] for _ in range(8)]


def test_full_clear_resets_cursors_transaction_and_deletes_file(tmp_path):
    """clear(full_clear=True) additionally resets the search/draft-start/
    file-size cursors and the transaction id, and deletes the state file
    instead of re-saving it."""
    s = _filled_session(tmp_path)
    s.save()
    assert (tmp_path / STATE_FILE_NAME).exists()

    s.clear(full_clear=True)

    assert s.search_offset == 0
    assert s.draft_start_offset == 0
    assert s.file_size == 0
    assert s.current_transaction_id == ""
    assert s.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert s.taken_cards == []
    assert s.pick_offset.position == 0
    assert s.pack_offset.position == 0
    assert s.pool_offset.position == 0
    # State file removed, not saved.
    assert not (tmp_path / STATE_FILE_NAME).exists()


def test_full_clear_without_existing_file_is_noop(tmp_path):
    """Deleting a state file that does not exist must not raise (the old
    clear_draft swallowed removal failures)."""
    s = _filled_session(tmp_path)
    s.clear(full_clear=True)
    assert not (tmp_path / STATE_FILE_NAME).exists()
    assert s.draft_type == constants.LIMITED_TYPE_UNKNOWN


# --- Completion migration ----------------------------------------------------

def test_complete_retires_live_state_keeps_recap_and_saves(tmp_path):
    """complete() retires the live pack/pick and the three live card lists,
    keeps taken_cards / draft_history / the recap identity, and persists."""
    s = _filled_session(tmp_path)
    s.save()

    s.complete()

    assert s.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert s.current_pack == 0
    assert s.current_pick == 0
    assert s.current_picked_pick == 0
    assert s.previous_scanned_pack == 0
    assert s.previous_picked_pack == 0
    assert s.picked_cards == [[] for _ in range(4)]
    assert s.pack_cards == [[] for _ in range(4)]
    assert s.initial_pack == [[] for _ in range(4)]
    # The drafted pool and history survive — recap of the finished draft needs
    # them, and the recap gate keys off draft_label/draft_sets.
    assert s.taken_cards == ["1000", "1001", "1002"]
    assert s.draft_history == [{"Pack": 1, "Pick": 1, "Cards": ["1000"]}]
    assert s.event_string == "PremierDraft_MSH_20260731"
    assert s.draft_label == "PremierDraft"
    assert s.draft_sets == ["MSH"]
    assert s.current_draft_id == "draft_abc"
    assert s.draft_start_time == "2026-07-31T12:00:00"

    # Completion persists: a fresh session reloads the retired state.
    fresh = DraftSession(_state_path(tmp_path))
    assert fresh.load() is True
    assert fresh.draft_type == constants.LIMITED_TYPE_UNKNOWN
    assert fresh.current_pack == 0
    assert fresh.taken_cards == ["1000", "1001", "1002"]
    assert fresh.draft_label == "PremierDraft"
