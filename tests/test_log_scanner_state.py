import pytest
from unittest.mock import MagicMock
import os
import logging
import src.constants as constants
from src.log_scanner import ArenaScanner
from src.constants import LIMITED_TYPE_DRAFT_PREMIER_V2
from src.limited_sets import SetDictionary, SetInfo


@pytest.fixture
def scanner(tmp_path):
    s = ArenaScanner(
        "mock.log",
        MagicMock(),
        retrieve_unknown=False,
        state_file=str(tmp_path / "active_draft_state.json"),
    )
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

    s = ArenaScanner(
        "mock.log",
        MagicMock(),
        retrieve_unknown=False,
        state_file=str(state_file),
    )
    assert s._load_state() is True
    assert s.draft_type == constants.LIMITED_TYPE_DRAFT_CONTENDER


# --- state_file injection ----------------------------------------------------
# Ticket 08: the draft-state path was a module-level constant with no injection
# point; tests hacked `s.state_file = ...` after construction and conftest wiped
# the fixed file around every test. The seam is now a constructor argument.

def test_state_file_injection_persists_only_to_injected_path(tmp_path):
    """A scanner given a state_file constructor arg persists draft state there —
    and never touches the module-level TEMP_FOLDER default."""
    from pathlib import Path

    state_file = tmp_path / "active_draft_state.json"
    s = ArenaScanner(
        "mock.log",
        MagicMock(),
        retrieve_unknown=False,
        state_file=str(state_file),
    )
    s.draft_type = LIMITED_TYPE_DRAFT_PREMIER_V2
    s.current_draft_id = "draft_injected"
    s.taken_cards = ["1", "2", "3"]
    s._save_state()

    assert state_file.exists()
    default_file = Path(constants.TEMP_FOLDER) / "active_draft_state.json"
    assert not default_file.exists()

    fresh = ArenaScanner(
        "mock.log",
        MagicMock(),
        retrieve_unknown=False,
        state_file=str(state_file),
    )
    assert fresh._load_state() is True
    assert fresh.draft_type == LIMITED_TYPE_DRAFT_PREMIER_V2
    assert fresh.current_draft_id == "draft_injected"
    assert fresh.taken_cards == ["1", "2", "3"]


def test_state_file_injection_clear_draft_removes_injected_file(tmp_path):
    """clear_draft(True) must delete the injected file, not a fixed default."""
    state_file = tmp_path / "active_draft_state.json"
    s = ArenaScanner(
        "mock.log", MagicMock(), retrieve_unknown=False, state_file=str(state_file)
    )
    s._save_state()
    assert state_file.exists()

    s.clear_draft(True)

    assert not state_file.exists()


def test_state_file_defaults_to_temp_folder(monkeypatch, tmp_path):
    """Omitting state_file keeps the legacy TEMP_FOLDER-derived path, resolved at
    construction time so monkeypatched TEMP_FOLDER still applies."""
    monkeypatch.setattr(constants, "TEMP_FOLDER", str(tmp_path))
    s = ArenaScanner("mock.log", MagicMock(), retrieve_unknown=False)
    assert s.state_file == str(tmp_path / "active_draft_state.json")


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


def test_retrieve_data_sources_proxy_forwards_draft_type(scanner, monkeypatch):
    """ArenaScanner.retrieve_data_sources is a thin proxy for
    DatasetSelector.retrieve_data_sources: it forwards the scanner's
    draft_type (the collection-date tie-break) and returns the selector's
    result untouched."""
    from src import dataset_selector

    received = {}
    monkeypatch.setattr(
        dataset_selector.DatasetSelector,
        "retrieve_data_sources",
        lambda _self, draft_type: received.update(draft_type=draft_type)
        or "/proxied.json",
    )
    scanner.draft_type = constants.LIMITED_TYPE_DRAFT_QUICK
    assert scanner.retrieve_data_sources() == "/proxied.json"
    assert received["draft_type"] == constants.LIMITED_TYPE_DRAFT_QUICK


def test_retrieve_color_win_rate_builds_label_to_key_map(scanner):
    """The legacy OptionMenu label->key map: rated archetypes carry the rate,
    Auto / All Decks are always present (bare when unrated), unrated guilds are
    omitted rather than rendered as a fake 0%. Shared with card_logic's
    format_filter_label, so the two cannot drift."""
    scanner.set_data.get_color_ratings = lambda: {"WU": 56.3, "All Decks": 58.0}

    names = scanner.retrieve_color_win_rate(constants.DECK_FILTER_FORMAT_NAMES)
    assert names["Auto"] == constants.FILTER_OPTION_AUTO
    assert names["All Decks (58.0%)"] == constants.FILTER_OPTION_ALL_DECKS
    assert names["Azorius (56.3%)"] == "WU"
    assert "Azorius" not in names  # bare name only when unrated → omitted
    assert "UB (0.0%)" not in names  # absent rate is not rendered as 0.0

    colors = scanner.retrieve_color_win_rate(constants.DECK_FILTER_FORMAT_COLORS)
    assert colors["WU (56.3%)"] == "WU"
    assert colors["Auto"] == constants.FILTER_OPTION_AUTO


# --- Draft completion ---------------------------------------------------------
# The terminal DeckSelect (DraftStatus "Completed") must retire the live
# pack/pick state but keep the drafted pool so the recap still works.

def test_mark_draft_complete_retires_live_state_keeps_pool(scanner):
    """The recap identity (event_string/draft_label/draft_sets) must survive
    completion — the desktop recap gate keys off draft_label, so zeroing it here
    would permanently block the recap. Only the live pack/pick retires; a later
    EventJoin with a new transaction id still wipes via __check_event."""
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
    scanner.draft_sets = ["MSH"]
    scanner.draft_start_time = "2026-07-31T12:00:00"
    scanner._save_state = MagicMock()

    scanner._mark_draft_complete()

    assert scanner.draft_type == 0  # LIMITED_TYPE_UNKNOWN → next EventJoin is fresh
    assert scanner.current_pack == 0
    assert scanner.current_pick == 0
    # Recap identity preserved so compute_draft_complete still recognizes it.
    assert scanner.event_string == "PremierDraft_MSH_20260731"
    assert scanner.draft_label == "PremierDraft"
    assert scanner.draft_sets == ["MSH"]
    assert scanner.draft_start_time == "2026-07-31T12:00:00"
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


# --- CardPool recovery vs. reopened drafts -----------------------------------
# On reopen the pool_offset is 0 (not persisted), so _search_card_pool rescans
# the whole log and hits MTGA's deck-recovery "CardPool" dump. For a draft that
# dump lists every card offered across all packs, NOT the cards picked — it must
# never replace the accurate taken_cards of a restored mid-draft.

def _recovery_scanner(tmp_path, line):
    """A scanner pointed at a real log file containing one CardPool dump line."""
    log = tmp_path / "Player.log"
    log.write_text(line + "\n")
    s = ArenaScanner(
        str(log),
        SetDictionary(
            data={"MSH": SetInfo(seventeenlands=["MSH"], set_code="MSH"),
                  "DSK": SetInfo(seventeenlands=["DSK"], set_code="DSK")}
        ),
        retrieve_unknown=False,
        state_file=str(tmp_path / "active_draft_state.json"),
    )
    s.log_enable(False)
    return s


MSH_RECOVERY_DUMP = (
    '{"InternalEventName":"QuickDraft_MSH_20260731","CurrentModule":"CreateMatch",'
    '"CardPool":[' + ",".join(str(1000 + i) for i in range(42)) + "]}"
)
DSK_SEALED_DUMP = (
    '{"InternalEventName":"Sealed_DSK_20240924","CurrentModule":"DeckSelect",'
    '"CardPool":[' + ",".join(str(2000 + i) for i in range(20)) + "]}"
)


def test_card_pool_recovery_does_not_clobber_reopened_draft(tmp_path):
    """A reopened mid-draft keeps its accurate taken_cards: the 42-card deck
    recovery dump (all cards offered) must not replace the 16 picks."""
    s = _recovery_scanner(tmp_path, MSH_RECOVERY_DUMP)
    from src import constants
    s.draft_type = constants.LIMITED_TYPE_DRAFT_QUICK
    s.event_string = "QuickDraft_MSH_20260731"
    s.current_transaction_id = "b2b24af9-d1b3-4034-be5b-a36f93bc696e"
    s.taken_cards = [str(1000 + i) for i in range(16)]  # 16 accurate picks

    s._search_card_pool()

    assert s.taken_cards == [str(1000 + i) for i in range(16)]


def test_card_pool_recovery_still_adopts_sealed_pool(tmp_path):
    """Sealed's CardPool dump IS the whole pool, so a tracked sealed event may
    still adopt it."""
    s = _recovery_scanner(tmp_path, DSK_SEALED_DUMP)
    from src import constants
    s.draft_type = constants.LIMITED_TYPE_SEALED
    s.event_string = "Sealed_DSK_20240924"

    s._search_card_pool()

    assert s.taken_cards == [str(2000 + i) for i in range(20)]


def test_card_pool_recovery_cold_start_adopts_sealed_pool(tmp_path):
    """No event registered yet (cold boot): the recovery pool registers the
    sealed event and seeds taken_cards from the dump."""
    s = _recovery_scanner(tmp_path, DSK_SEALED_DUMP)
    from src import constants
    s.draft_type = constants.LIMITED_TYPE_UNKNOWN

    s._search_card_pool()

    assert s.event_string == "Sealed_DSK_20240924"
    assert s.taken_cards == [str(2000 + i) for i in range(20)]


# --- Scan-offset persistence --------------------------------------------------
# The scan pointers are persisted so a reopened mid-draft resumes where the app
# left off instead of re-scanning the append-only Player.log from 0 — which
# hits the OLD draft's EventJoin (different transaction id), wipes the restored
# pool, and resets the signals. file_size makes the truncation check survive a
# restart (a recreated, shorter log → full clear).


def test_state_persists_scan_offsets(tmp_path):
    """All five scan pointers survive a save/load round-trip."""
    from src import constants

    s = _recovery_scanner(tmp_path, "MTGA Log Start\n")
    s.search_offset = 1111
    s.pick_offset.position = 2222
    s.pack_offset.position = 3333
    s.pool_offset.position = 4444
    s.file_size = 5555
    s.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    s.taken_cards = ["1"]
    s._save_state()

    fresh = _recovery_scanner(tmp_path, "MTGA Log Start\n")
    assert fresh._load_state() is True
    assert fresh.search_offset == 1111
    assert fresh.pick_offset.position == 2222
    assert fresh.pack_offset.position == 3333
    assert fresh.pool_offset.position == 4444
    assert fresh.file_size == 5555


def test_reopen_does_not_wipe_restored_state_when_log_has_old_events(tmp_path):
    """The #1/#3 regression: a reopened mid-draft resumes from its saved search
    offset, so the OLD draft's EventJoin earlier in the log is never re-seen and
    the restored pool (which the signals are recomputed from) is preserved."""
    from src import constants

    old_event_join = (
        "[UnityCrossThreadLogger]==> Event_Join "
        '{"id":"txn_old","request":"{\\"EventName\\":\\"PremierDraft_MSH_20260731\\",'
        '\\"EntryCurrencyType\\":\\"Gem\\"}"}'
    )
    s = _recovery_scanner(tmp_path, old_event_join)
    log = tmp_path / "Player.log"
    log_size = log.stat().st_size

    # Restore a mid-draft state as if the app saved it before disconnecting.
    s.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    s.draft_sets = ["MSH"]
    s.draft_label = "PremierDraft"
    s.event_string = "PremierDraft_MSH_20260731"
    s.current_draft_id = "draft_B"
    s.current_transaction_id = "txn_B"
    s.taken_cards = [str(1000 + i) for i in range(17)]
    s.draft_history = [{"Pack": 1, "Pick": 1, "Cards": ["1000"]}] * 17
    s.current_pack = 2
    s.current_pick = 3
    s.search_offset = log_size
    s.pick_offset.position = log_size
    s.pack_offset.position = log_size
    s.pool_offset.position = log_size
    s.file_size = log_size
    s._save_state()

    fresh = _recovery_scanner(tmp_path, old_event_join)
    assert fresh._load_state() is True

    # Nothing new after the saved position → no re-registration, no wipe.
    assert fresh.draft_start_search() is False
    assert fresh.taken_cards == [str(1000 + i) for i in range(17)]
    assert len(fresh.draft_history) == 17
    assert fresh.event_string == "PremierDraft_MSH_20260731"
    assert fresh.draft_label == "PremierDraft"
    assert fresh.draft_sets == ["MSH"]


def test_reopened_scanner_detects_truncated_log_and_resets(tmp_path):
    """file_size is persisted so the truncation check in draft_start_search
    survives a restart: a recreated (shorter) Player.log must fully clear the
    stale restored state instead of resuming at an offset past the end."""
    from src import constants

    s = _recovery_scanner(tmp_path, "MTGA Log Start\n")
    # Pretend the previous session had scanned a much longer log.
    s.draft_type = constants.LIMITED_TYPE_DRAFT_QUICK
    s.taken_cards = [str(1000 + i) for i in range(17)]
    s.search_offset = 5000
    s.pick_offset.position = 5000
    s.pack_offset.position = 5000
    s.pool_offset.position = 5000
    s.file_size = 5000
    s._save_state()

    fresh = _recovery_scanner(tmp_path, "MTGA Log Start\n")
    assert fresh._load_state() is True
    assert fresh.taken_cards == [str(1000 + i) for i in range(17)]

    # The log shrank since the saved file_size → full clear + rescan from 0.
    fresh.draft_start_search()
    assert fresh.taken_cards == []
    assert fresh.search_offset < 5000  # stale offset past the end is gone
    assert fresh.draft_type == constants.LIMITED_TYPE_UNKNOWN


def test_new_event_after_completion_starts_fresh(scanner):
    """Keeping the recap identity after completion must not break next-draft
    detection: a new EventJoin for the same event with a different transaction
    id still wipes the finished pool and registers the new draft."""
    from src import constants

    scanner.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    scanner.event_string = "PremierDraft_MSH_20260731"
    scanner.current_transaction_id = "txn_finished"
    scanner.taken_cards = [str(1000 + i) for i in range(42)]
    scanner._save_state = MagicMock()

    scanner._mark_draft_complete()

    # __check_event receives the parsed payload (draft_start_search runs it
    # through process_json before dispatch).
    new_join = {
        "id": "txn_new",
        "request": {
            "EventName": "PremierDraft_MSH_20260731",
            "EntryCurrencyType": "Gem",
        },
    }
    update, _, _ = scanner._ArenaScanner__check_event(new_join)

    assert update is True
    assert scanner.current_transaction_id == "txn_new"
    assert scanner.event_string == "PremierDraft_MSH_20260731"
    assert scanner.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    assert scanner.taken_cards == []  # finished pool wiped, fresh draft begins


def test_recovery_mode_sets_draft_label(scanner):
    """Recovery (no EventJoin registered) still stamps the inferred draft type
    so the recap gate recognizes the event once the pool is finished."""
    from src import constants

    scanner.draft_type = constants.LIMITED_TYPE_UNKNOWN
    scanner._search_pack_notify = MagicMock(return_value=True)
    scanner._search_pick_human = MagicMock(return_value=False)
    scanner._search_pack_bot = MagicMock(return_value=False)
    scanner._search_pick_bot = MagicMock(return_value=False)
    scanner._search_card_pool = MagicMock(return_value=False)

    scanner._ArenaScanner__perform_search_logic()

    assert scanner.draft_label == constants.LIMITED_TYPE_STRING_DRAFT_PREMIER


# --- Explicit state machine (architecture-review issue 11) -------------------
# The docs/02 §7 diagram now has code counterparts: ScannerPhase symbols, a
# single TRANSITIONS table, and a phase property driven by the dispatch.
# These walkthroughs drive real log lines through the full
# draft_data_search/draft_start_search pipeline and assert the phase chain —
# deleting a TRANSITIONS row must make exactly these tests go red.

WALK_JOIN_PREMIER = (
    '[UnityCrossThreadLogger]==> Event_Join '
    '{"id":"11a8f74b-1afb-4d25-bb35-55d43674c808",'
    '"request":"{\\"EventName\\":\\"PremierDraft_OTJ_20240416\\",'
    '\\"EntryCurrencyType\\":\\"Gem\\"}"}'
)
WALK_PACK_P1P1 = (
    '[UnityCrossThreadLogger]Draft.Notify '
    '{"draftId":"87b408d1-43e0-4fb5-8c74-a1257fde087c","SelfPick":1,"SelfPack":1,'
    '"PackCards":"90734,90584,90631,90362,90440,90349,90486,90527,90406,'
    '90439,90488,90480,90388,90459"}'
)
WALK_PICK_P1P1 = (
    '[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick '
    '{"id":"a14a9a98-f408-4051-8799-50df13eb18ad",'
    '"request":"{\\"DraftId\\":\\"87b408d1-43e0-4fb5-8c74-a1257fde087c\\",'
    '\\"GrpId\\":90459,\\"Pack\\":1,\\"Pick\\":1}"}'
)
WALK_PACK_P1P2 = (
    '[UnityCrossThreadLogger]Draft.Notify '
    '{"draftId":"87b408d1-43e0-4fb5-8c74-a1257fde087c","SelfPick":2,"SelfPack":1,'
    '"PackCards":"90701,90416,90606,90524,90481,90588,90440,90418,90353,'
    '90494,90360,90609,90548"}'
)
WALK_JOIN_QUICK = (
    '[UnityCrossThreadLogger]==> BotDraft_DraftStatus '
    '{"id":"acd4c04b-fabcd-4c5c-ac1e-6dfb53a2df2f",'
    '"request":"{\\"EventName\\":\\"QuickDraft_OTJ_20240426\\"}"}'
)
WALK_PACK_BOT = (
    '{"CurrentModule":"BotDraft","Payload":"{\\"Result\\":\\"Success\\",'
    '\\"EventName\\":\\"QuickDraft_OTJ_20240426\\",\\"DraftStatus\\":\\"PickNext\\",'
    '\\"PackNumber\\":0,\\"PickNumber\\":0,'
    '\\"DraftPack\\":[\\"90711\\",\\"90504\\"],\\"PickedCards\\":[]}"}'
)
WALK_PICK_BOT = (
    '[UnityCrossThreadLogger]==> BotDraft_DraftPick '
    '{"id":"a14a9a98-f408-4051-8799-50df13eb18ad",'
    '"request":"{\\"CardIds\\":[\\"90428\\"],\\"PackNumber\\":0,\\"PickNumber\\":0}"}'
)
WALK_TERMINAL_BOT = (
    '{"CurrentModule":"DeckSelect","Payload":"{\\"Result\\":\\"Success\\",'
    '\\"EventName\\":\\"QuickDraft_OTJ_20240426\\",\\"DraftStatus\\":\\"Completed\\",'
    '\\"DraftPack\\":[],\\"PackNumber\\":2,\\"PickNumber\\":13}"}'
)


@pytest.fixture
def walkthrough_scanner(tmp_path):
    """A scanner on a real append-only log with a real set dictionary, driven
    through the full draft_data_search/draft_start_search pipeline."""
    from src.limited_sets import SetDictionary, SetInfo

    log = tmp_path / "Player.log"
    log.write_text("")
    s = ArenaScanner(
        str(log),
        SetDictionary(
            data={
                "OTJ": SetInfo(seventeenlands=["OTJ"], set_code="OTJ"),
                "DSK": SetInfo(seventeenlands=["DSK"], set_code="DSK"),
            }
        ),
        retrieve_unknown=False,
        state_file=str(tmp_path / "active_draft_state.json"),
    )
    s.log_enable(False)
    return s, log


def _append(log, *lines):
    with open(str(log), "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def test_phase_walkthrough_human_draft(walkthrough_scanner):
    """Idle →(EventJoin) WaitingForPack →(Draft.Notify) PackReview →(MakePick)
    PickMade →(next Draft.Notify) PackReview."""
    from src.scanner_state import ScannerPhase

    s, log = walkthrough_scanner
    assert s.phase == ScannerPhase.IDLE

    _append(log, WALK_JOIN_PREMIER)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_WAITING_FOR_PACK

    _append(log, WALK_PACK_P1P1)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_PACK_REVIEW
    assert (s.current_pack, s.current_pick) == (1, 1)

    _append(log, WALK_PICK_P1P1)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_PICK_MADE
    assert s.current_picked_pick == 1

    _append(log, WALK_PACK_P1P2)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_PACK_REVIEW
    assert s.current_pick == 2


def test_phase_walkthrough_bot_draft_to_done_and_next_draft(walkthrough_scanner):
    """Idle →(BotDraft join) WaitingForPack →(bot pack) PackReview
    →(terminal DeckSelect) Done →(new EventJoin) WaitingForPack."""
    from src import constants as c
    from src.scanner_state import ScannerPhase

    s, log = walkthrough_scanner

    _append(log, WALK_JOIN_QUICK)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_WAITING_FOR_PACK

    _append(log, WALK_PACK_BOT)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_PACK_REVIEW
    assert (s.current_pack, s.current_pick) == (1, 1)  # 0-indexed log → 1-indexed

    _append(log, WALK_PICK_BOT)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_PICK_MADE
    assert s.current_picked_pick == 1

    _append(log, WALK_TERMINAL_BOT)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DONE
    assert s.draft_type == c.LIMITED_TYPE_UNKNOWN
    assert s.current_pack == 0  # live pack retired, pool kept for recap

    _append(log, WALK_JOIN_PREMIER)
    s.draft_data_search()
    assert s.phase == ScannerPhase.DRAFTING_WAITING_FOR_PACK
    assert s.event_string == "PremierDraft_OTJ_20240416"  # recap wiped, fresh draft


def test_phase_walkthrough_sealed_recovery(walkthrough_scanner):
    """Cold boot with a CardPool dump: Idle → SealedStudio, pool adopted."""
    from src.scanner_state import ScannerPhase

    s, log = walkthrough_scanner
    _append(log, DSK_SEALED_DUMP)

    s.draft_data_search()

    assert s.phase == ScannerPhase.SEALED_STUDIO
    assert s.event_string == "Sealed_DSK_20240924"
    assert s.taken_cards == [str(2000 + i) for i in range(20)]


def test_illegal_transition_fails_loud(scanner, caplog):
    """An event with no TRANSITIONS row for the current phase must fail loud
    (logger.warning) instead of silently applying a return-value convention.

    Driven through the real recovery chain with the scan seams stubbed (the
    pattern of test_recovery_mode_sets_draft_label): a terminal DeckSelect
    firing from IDLE is the canonical illegal combo — IDLE has no
    DECK_SELECT_COMPLETED row. (End-to-end this path is cursor-shadowed —
    _search_pack_notify consumes pack_offset to EOF first — so the fail-loud
    branch is exercised exactly as a future event type added to a family
    without table rows will hit it.)"""
    from src.scanner_state import ScannerEvent, ScannerPhase

    scanner.draft_type = constants.LIMITED_TYPE_UNKNOWN
    scanner._search_pack_notify = MagicMock(return_value=False)
    scanner._search_pick_human = MagicMock(return_value=False)
    scanner._search_pack_bot = MagicMock(
        return_value=ScannerEvent.DECK_SELECT_COMPLETED
    )
    scanner._search_pick_bot = MagicMock(return_value=False)
    scanner._search_card_pool = MagicMock(return_value=False)

    with caplog.at_level(logging.WARNING):
        scanner._ArenaScanner__perform_search_logic()

    assert any(
        "no registered transition" in record.message.lower()
        for record in caplog.records
        if record.levelno == logging.WARNING
    )
    # The machine must not pretend a transition happened.
    assert scanner.phase == ScannerPhase.IDLE
    assert scanner.draft_type == constants.LIMITED_TYPE_UNKNOWN


# --- Typed scan cursors (architecture-review issue04) -------------------------
# The old offset_attr string reflection made _scan_log_for_events/_parse_events
# silently break on rename. Cursors are now explicit objects: renames fail with
# AttributeError at the call site, and the three cursors advance independently.


def _cursor_log(tmp_path):
    log = tmp_path / "draft.log"
    log.write_text(
        '[UnityCrossThreadLogger]==> {"Pack":1,"Pick":1}\n'
        "[UnityCrossThreadLogger]==> some noise\n"
        '[UnityCrossThreadLogger]==> {"Pack":1,"Pick":2}\n'
    )
    s = ArenaScanner(str(log), MagicMock(), retrieve_unknown=False)
    return s, log


def test_scan_log_events_advances_typed_cursor(tmp_path):
    """_scan_log_for_events reads from cursor.position and advances it, so a
    re-scan resumes where it left off instead of re-reading the whole log."""
    s, log = _cursor_log(tmp_path)
    cursor = s.pack_offset

    payloads = list(s._scan_log_for_events(cursor, ['{"Pack":']))
    assert len(payloads) == 2
    assert all("Pack" in p for p in payloads)
    assert cursor.position == os.path.getsize(str(log))


def test_scan_log_events_resumes_from_cursor_position(tmp_path):
    """The cursor sits at EOF after one pass; a second pass only yields lines
    appended since — the append-only Player.log model."""
    s, log = _cursor_log(tmp_path)
    cursor = s.pick_offset

    list(s._scan_log_for_events(cursor, ["noise"]))  # first pass consumes to EOF

    with open(str(log), "a", encoding="utf-8") as f:
        f.write('[UnityCrossThreadLogger]==> {"Pack":2,"Pick":1}\n')

    second = list(s._scan_log_for_events(cursor, ["Pack"]))
    assert len(second) == 1
    assert '"Pack":2' in second[0]


def test_scan_cursors_are_independent(tmp_path):
    """pack/pick/pool cursors advance separately; scanning one never touches the others."""
    s, _ = _cursor_log(tmp_path)

    list(s._scan_log_for_events(s.pack_offset, ["Pack"]))
    assert s.pack_offset.position > 0
    assert s.pick_offset.position == 0
    assert s.pool_offset.position == 0


def test_scan_log_events_rejects_legacy_string_cursor(tmp_path):
    """The offset_attr string form must be gone — passing a string now fails
    loudly (AttributeError) instead of silently reflecting an attribute name."""
    s, _ = _cursor_log(tmp_path)
    with pytest.raises(AttributeError):
        list(s._scan_log_for_events("pack_offset", ['{"Pack":']))

