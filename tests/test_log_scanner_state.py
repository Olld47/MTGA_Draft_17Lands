import pytest
from unittest.mock import MagicMock
from src.log_scanner import ArenaScanner, _dataset_event_type_rank
from src.constants import LIMITED_TYPE_DRAFT_PREMIER_V2


@pytest.fixture
def scanner():
    s = ArenaScanner("mock.log", MagicMock(), retrieve_unknown=False)
    s.draft_type = LIMITED_TYPE_DRAFT_PREMIER_V2
    return s


def test_stale_pool_wipe_different_draft_id(scanner):
    """If Arena logs a completely new Transaction ID, wipe everything immediately."""
    scanner.current_draft_id = "draft_A"
    scanner.taken_cards = ["1", "2", "3"]
    scanner.current_pack = 1
    scanner.current_pick = 3

    # Provide new draft ID
    scanner._check_and_wipe_stale_pool(
        pack=1, pick=1, current_cards=["4", "5"], draft_id="draft_B"
    )

    assert len(scanner.taken_cards) == 0
    assert scanner.current_pack == 0
    assert scanner.current_draft_id == "draft_B"


def test_stale_pool_wipe_time_travel_backwards(scanner):
    """If we see an older pack/pick than our current state, and the cards don't match our history, it's a stale restart."""
    scanner.current_draft_id = ""  # No ID provided by log
    scanner.current_pack = 2
    scanner.current_pick = 5
    scanner.taken_cards = ["1"] * 20

    # Force the scanner into the time-travel logic block by providing a new draft ID
    # but mocking _load_state to simulate a successful load (so wipe starts False)
    scanner._load_state = MagicMock(return_value=True)

    # We suddenly see Pack 1 Pick 1, but we already have 20 cards. WIPE!
    scanner._check_and_wipe_stale_pool(
        pack=1, pick=1, current_cards=["99", "100"], draft_id="draft_B"
    )

    assert len(scanner.taken_cards) == 0
    assert scanner.current_pack == 0


def test_load_state_normalizes_legacy_string_draft_type(tmp_path):
    """States saved before v4.19 could persist an event-name string (e.g.
    "ContenderDraft") as draft_type, which matches no parser dispatch branch.
    Loading must coerce it to the int type code."""
    import json
    from src import constants

    state_file = tmp_path / "active_draft_state.json"
    state_file.write_text(
        json.dumps(
            {
                "draft_type": "ContenderDraft",
                "current_draft_id": "draft_A",
                "event_string": "ContenderDraft_MSH_20260707",
            }
        )
    )

    s = ArenaScanner("mock.log", MagicMock(), retrieve_unknown=False)
    s.state_file = str(state_file)
    assert s._load_state() is True
    assert s.draft_type == constants.LIMITED_TYPE_DRAFT_CONTENDER


def test_stale_pool_no_wipe_historical_replay(scanner):
    """If we time-travel backwards but the cards MATCH our history exactly, DO NOT WIPE. We are just re-parsing the log."""
    scanner.current_draft_id = ""
    scanner.current_pack = 2
    scanner.current_pick = 5
    scanner.taken_cards = ["1"] * 20

    # Build a matching history
    scanner.draft_history = [{"Pack": 1, "Pick": 2, "Cards": ["A", "B", "C"]}]

    # We see P1P2 again, and the cards match our history.
    scanner._check_and_wipe_stale_pool(
        pack=1, pick=2, current_cards=["B"], draft_id=None
    )

    # Pool should NOT be wiped
    assert len(scanner.taken_cards) == 20


# --- Dataset auto-select ------------------------------------------------------
# A set ships one dataset per event type; matching only the [SET] bracket loads
# the wrong one (e.g. PickTwo data for a QuickDraft) and every stat reads 0.0.

def test_dataset_event_type_rank_exact_section():
    """An exact event-name section match ranks highest (rank 0)."""
    assert _dataset_event_type_rank("QuickDraft", "QuickDraft_MSH_20260806") == 0
    assert _dataset_event_type_rank("PremierDraft", "PremierDraft_MSH_20260806") == 0


def test_dataset_event_type_rank_containment_fallback():
    """Pick-two variants still resolve via containment (rank 1)."""
    assert _dataset_event_type_rank("QuickDraft", "PickTwoQuickDraft_MSH_20260806") == 1
    assert _dataset_event_type_rank("QuickDraft", "PhantomPickTwoQuickDraft_MSH_20260806") == 1


def test_dataset_event_type_rank_mismatch():
    """An unrelated dataset type is rejected outright (None)."""
    assert _dataset_event_type_rank("PremierDraft", "QuickDraft_MSH_20260806") is None


def test_dataset_event_type_rank_unknown_event_matches_all():
    """An unparseable/empty event name matches every dataset type — the caller
    falls back to any source for the set."""
    assert _dataset_event_type_rank("QuickDraft", "") == 0


@pytest.fixture
def sources_scanner(scanner):
    """A scanner whose dataset catalog is stubbed to a controlled label->path map."""
    def _with(catalog):
        scanner.retrieve_data_sources = lambda: catalog
        return scanner
    return _with


def test_select_best_dataset_prefers_exact_type_then_all_group(sources_scanner):
    """QuickDraft event → the QuickDraft dataset, and "All" over "Top"."""
    s = sources_scanner(
        {
            "[MSH] QuickDraft (Top)": "/top.json",
            "[MSH] QuickDraft (All)": "/all.json",
            "[MSH] PickTwoQuickDraft (All)": "/picktwo.json",
            "[MSH] PremierDraft (All)": "/premier.json",
        }
    )
    assert s.select_best_dataset("MSH", "QuickDraft_MSH_20260806") == "/all.json"


def test_select_best_dataset_pick_two_event_resolves_to_quick_draft(sources_scanner):
    """A PickTwoQuickDraft event has no exact dataset, so containment picks the
    QuickDraft source over an unrelated PremierDraft, preferring the broad
    "All" group."""
    s = sources_scanner(
        {
            "[MSH] QuickDraft (Top)": "/top.json",
            "[MSH] QuickDraft (All)": "/all.json",
            "[MSH] PremierDraft (All)": "/premier.json",
        }
    )
    assert s.select_best_dataset("MSH", "PickTwoQuickDraft_MSH_20260806") == "/all.json"


def test_select_best_dataset_unknown_event_falls_back_to_any_source(sources_scanner):
    """An event type the set has no dataset for still resolves to a set source
    (preferring "All") instead of returning nothing."""
    s = sources_scanner(
        {
            "[MSH] QuickDraft (Top)": "/top.json",
            "[MSH] QuickDraft (All)": "/all.json",
        }
    )
    assert s.select_best_dataset("MSH", "MysteryFormat_MSH_20260806") == "/all.json"


def test_select_best_dataset_no_source_for_set_returns_empty(sources_scanner):
    s = sources_scanner(
        {
            "[OTJ] PremierDraft (All)": "/otj.json",
        }
    )
    assert s.select_best_dataset("MSH", "QuickDraft_MSH_20260806") == ""


# --- Draft completion ---------------------------------------------------------
# The terminal DeckSelect (DraftStatus "Completed") must retire the live
# pack/pick state but keep the drafted pool so the recap still works.

def test_mark_draft_complete_retires_live_state_keeps_pool(scanner):
    scanner.draft_type = LIMITED_TYPE_DRAFT_PREMIER_V2
    scanner.taken_cards = ["1", "2", "3"]
    scanner.draft_history = [{"Pack": 1, "Pick": 1, "Cards": ["1"]}]
    scanner.current_pack = 3
    scanner.current_pick = 14
    scanner.previous_scanned_pack = 3
    scanner.previous_picked_pack = 3
    scanner.current_picked_pick = 14
    scanner.picked_cards = [["1", "2", "3"]]
    scanner.pack_cards = [["9", "8"]]
    scanner.initial_pack = [["9", "8"]]
    scanner.event_string = "PremierDraft_MSH_20260731"
    scanner.draft_label = "PremierDraft"
    scanner.draft_start_time = "2026-07-31T12:00:00"
    scanner._save_state = MagicMock()

    scanner._mark_draft_complete()

    assert scanner.draft_type == 0  # LIMITED_TYPE_UNKNOWN → next EventJoin is fresh
    assert scanner.current_pack == 0
    assert scanner.current_pick == 0
    assert scanner.event_string == ""
    assert scanner.draft_label == ""
    assert scanner.draft_start_time == ""
    assert scanner.picked_cards == [[] for _ in range(8)]
    assert scanner.pack_cards == [[] for _ in range(8)]
    # The drafted pool and history survive — recap of the finished draft needs them.
    assert scanner.taken_cards == ["1", "2", "3"]
    assert scanner.draft_history == [{"Pack": 1, "Pick": 1, "Cards": ["1"]}]
    scanner._save_state.assert_called_once()


def test_mark_draft_complete_treats_no_active_draft_as_noop(scanner):
    scanner.draft_type = 0
    scanner.taken_cards = ["1", "2"]
    scanner._save_state = MagicMock()

    scanner._mark_draft_complete()

    assert scanner.taken_cards == ["1", "2"]
    scanner._save_state.assert_called_once()
