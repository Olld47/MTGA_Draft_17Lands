import pytest
from unittest.mock import MagicMock
from src.log_scanner import ArenaScanner
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
