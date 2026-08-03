"""
tests/test_bridge_deck.py
Bridge-layer tests for the custom-deck port (mtga_bridge.deck_session).
Exercises DeckSession against a real ArenaScanner with a mock pool — the
tkinter panel it replaces is covered by tests/test_custom_deck.py, but that
coverage did not carry over when the logic moved into the bridge.
No pytauri, no tkinter.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

# Make the bridge package importable from the root test run
BRIDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "desktop",
    "src-tauri",
    "src-python",
)
if BRIDGE_PATH not in sys.path:
    sys.path.insert(0, BRIDGE_PATH)

from src import constants
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src.log_scanner import ArenaScanner
from src.utils import Result

from mtga_bridge.deck_session import DeckSession
from mtga_bridge.runtime import AppRuntime


# --- Fixtures ----------------------------------------------------------------


_POOL_CARDS = [
    ("White Knight", 2, ["Creature"], ["W"], "{1}{W}", 58.0),
    ("Blue Flyer", 3, ["Creature"], ["U"], "{2}{U}", 56.0),
    ("Black Removal", 2, ["Instant"], ["B"], "{1}{B}", 60.0),
    ("Green Beast", 4, ["Creature"], ["G"], "{2}{G}{G}", 59.0),
]


def _mock_dataset():
    return {
        "meta": {"version": 3.0, "game_count": 10000},
        "card_ratings": {
            str(300 + i): {
                "name": name,
                "cmc": cmc,
                "types": types,
                "colors": colors,
                "rarity": "common",
                "mana_cost": cost,
                "deck_colors": {"All Decks": {"gihwr": gihwr, "alsa": 3.0}},
            }
            for i, (name, cmc, types, colors, cost, gihwr) in enumerate(_POOL_CARDS)
        },
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    sets_dir = tmp_path / "Sets"
    sets_dir.mkdir()
    temp_dir = tmp_path / "Temp"
    temp_dir.mkdir()

    monkeypatch.setattr("src.constants.SETS_FOLDER", str(sets_dir))
    monkeypatch.setattr("src.constants.TEMP_FOLDER", str(temp_dir))

    log_file = tmp_path / "Player.log"
    log_file.write_text("MTGA Log Start\n")

    dataset_path = sets_dir / "TEST_PremierDraft_All_Data.json"
    data = _mock_dataset()
    dataset_path.write_text(json.dumps(data))

    mock_sets = SetDictionary(
        data={"Test Set": SetInfo(arena=["TEST"], seventeenlands=["TEST"], set_code="TEST")}
    )

    config = Configuration()
    config.settings.arena_log_location = str(log_file)

    with patch("src.dataset.check_file_integrity", return_value=(Result.VALID, data)):
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))

    prototypes = scanner.set_data.get_data_by_name([c[0] for c in _POOL_CARDS])
    pool = [dict(proto) for proto in prototypes for _ in range(6)]
    scanner.retrieve_taken_cards = lambda: pool
    scanner.retrieve_tier_data = lambda: {}

    runtime = AppRuntime(config=config, scanner=scanner)
    return {"runtime": runtime, "scanner": scanner, "config": config, "pool": pool}


def _card(name, count=1, cmc=2, types=None, colors=None):
    return {
        "name": name,
        "cmc": cmc,
        "types": types or ["Creature"],
        "colors": colors if colors is not None else ["W"],
        "mana_cost": "{1}{W}",
        "count": count,
    }


def _session(env) -> DeckSession:
    return DeckSession(env["scanner"], env["config"])


# --- runtime wiring ----------------------------------------------------------


def test_runtime_reuses_one_deck_session(env):
    """The session is stateful — a new instance per command would drop the
    user's deck on every mutation."""
    runtime = env["runtime"]
    assert runtime.deck_session() is runtime.deck_session()


# --- import / refresh --------------------------------------------------------


def test_import_deck_deep_copies(env):
    """Mutating the imported list must not write back through the caller's
    dicts — the suggest page hands over cards it still owns."""
    session = _session(env)
    source = [_card("White Knight", 2)]
    session.import_deck(source, [])

    session.move_card("White Knight", to_sideboard=True)

    assert source[0]["count"] == 2
    assert session.known_pool_size == len(env["pool"])


def test_refresh_pool_appends_only_new_cards(env):
    session = _session(env)
    session.import_deck([], [])
    before = sum(c["count"] for c in session.sb_list)

    session.refresh_pool()

    assert sum(c["count"] for c in session.sb_list) == before


def test_refresh_pool_moves_newly_drafted_cards_to_the_sideboard(env):
    session = _session(env)
    session.import_deck([], [])
    session.sb_list = []
    session.known_pool_size = 0

    session.refresh_pool()

    assert sum(c["count"] for c in session.sb_list) == len(env["pool"])
    assert session.known_pool_size == len(env["pool"])


def test_refresh_pool_resets_when_the_pool_is_gone(env):
    """A new draft empties the pool; the previous deck must not survive it."""
    session = _session(env)
    session.import_deck([_card("White Knight")], [])
    env["scanner"].retrieve_taken_cards = lambda: []

    session.refresh_pool()

    assert session.deck_list == []
    assert session.sb_list == []
    assert session.known_pool_size == 0


# --- mutations ---------------------------------------------------------------


def test_move_card_decrements_source_and_increments_destination(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 2)], [])

    session.move_card("White Knight", to_sideboard=True)

    assert session.deck_list[0]["count"] == 1
    assert session.sb_list[0]["count"] == 1


def test_move_card_removes_the_row_at_zero(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 1)], [])

    session.move_card("White Knight", to_sideboard=True)

    assert session.deck_list == []
    assert session.sb_list[0]["count"] == 1


def test_move_card_back_from_the_sideboard(env):
    session = _session(env)
    session.import_deck([], [_card("Blue Flyer", 1)])

    session.move_card("Blue Flyer", to_sideboard=False)

    assert session.sb_list == []
    assert session.deck_list[0]["count"] == 1


def test_move_card_ignores_an_unknown_name(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 1)], [])

    session.move_card("Not In Pool", to_sideboard=True)

    assert session.deck_list[0]["count"] == 1
    assert session.sb_list == []


def test_clear_deck_returns_spells_but_discards_basics(env):
    """Basics are generated, not drafted, so returning them to the sideboard
    would invent pool cards the player never had."""
    session = _session(env)
    session.import_deck(
        [_card("White Knight", 2), _card("Plains", 5, 0, ["Land", "Basic"], [])], []
    )

    session.clear_deck()

    assert session.deck_list == []
    assert [c["name"] for c in session.sb_list] == ["White Knight"]
    assert session.sb_list[0]["count"] == 2


def test_clear_deck_merges_into_an_existing_sideboard_row(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 2)], [_card("White Knight", 1)])

    session.clear_deck()

    assert len(session.sb_list) == 1
    assert session.sb_list[0]["count"] == 3


def test_add_and_remove_basic(env):
    session = _session(env)
    session.import_deck([], [])

    session.add_basic("Plains")
    session.add_basic("Plains")

    plains = next(c for c in session.deck_list if c["name"] == "Plains")
    assert plains["count"] == 2
    assert plains["colors"] == ["W"]
    assert "Basic" in plains["types"]

    session.remove_basic("Plains")
    assert plains["count"] == 1
    session.remove_basic("Plains")
    assert session.deck_list == []


def test_remove_basic_ignores_a_land_not_in_the_deck(env):
    session = _session(env)
    session.import_deck([], [])

    session.remove_basic("Island")

    assert session.deck_list == []


# --- serialization -----------------------------------------------------------


def test_build_state_sorts_and_counts(env):
    session = _session(env)
    session.import_deck(
        [_card("Green Beast", 2, 4), _card("White Knight", 3, 2)],
        [_card("Blue Flyer", 1, 3)],
    )

    state = session.build_state()

    assert [row.name for row in state.deck] == ["White Knight", "Green Beast"]
    assert state.main_count == 5
    assert state.sideboard_count == 1
    assert state.stats.total_cards == 5


def test_build_state_resolves_auto_to_all_decks(env):
    """Card stats are looked up by archetype key; "Auto" is not one, so it must
    be resolved before it reaches the dataset."""
    env["config"].settings.deck_filter = constants.FILTER_OPTION_AUTO
    session = _session(env)
    session.import_deck([_card("White Knight", 1)], [])

    assert session.build_state().active_filter == "All Decks"


def test_build_state_serializes_camel_case(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 1)], [])

    dumped = session.build_state().model_dump()

    assert "mainCount" in dumped
    assert "main_count" not in dumped


def test_export_emits_an_mtga_decklist(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 2)], [_card("Blue Flyer", 1)])

    text = session.export().text

    assert "White Knight" in text
    assert "Blue Flyer" in text


# --- engine operations -------------------------------------------------------


def test_run_simulation_rejects_an_incomplete_deck(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 1)], [])

    result = session.run_simulation()

    assert not result.ok
    assert "40 cards" in result.message
    assert result.stats is None


def test_auto_optimize_rejects_a_deck_that_is_not_forty(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 39)], [])

    result = session.auto_optimize()

    assert not result.ok
    assert "currently 39" in result.message


def test_apply_auto_lands_requires_spells(env):
    session = _session(env)
    session.import_deck([_card("Plains", 5, 0, ["Land", "Basic"], [])], [])

    result = session.apply_auto_lands()

    assert not result.ok
    assert "spells" in result.message.lower()


def test_apply_auto_lands_fills_to_forty(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 23, 2, ["Creature"], ["W"])], [])

    result = session.apply_auto_lands()

    assert result.ok
    basics = [c for c in session.deck_list if c["name"] in constants.BASIC_LANDS]
    assert sum(c["count"] for c in basics) == 17


def test_apply_auto_lands_replaces_previous_basics(env):
    """Re-running must not stack a second mana base on top of the first."""
    session = _session(env)
    session.import_deck(
        [
            _card("White Knight", 23, 2, ["Creature"], ["W"]),
            _card("Island", 9, 0, ["Land", "Basic"], ["U"]),
        ],
        [],
    )

    session.apply_auto_lands()

    basics = [c for c in session.deck_list if c["name"] in constants.BASIC_LANDS]
    assert sum(c["count"] for c in basics) == 17
    assert not any(c["name"] == "Island" for c in basics)


def test_apply_auto_lands_counts_copies_not_rows(env):
    """The land count is `40 - spells`, and deck_list is *stacked* — each row
    can be several cards. Counting rows overshot by one land per duplicate, so
    a pool with any repeats produced a deck larger than 40. The tkinter handler
    (custom_deck.py:1186) still has the row-counting form.
    """
    session = _session(env)
    session.import_deck(
        [
            _card("White Knight", 4, 2, ["Creature"], ["W"]),
            _card("Blue Flyer", 4, 3, ["Creature"], ["W"]),
            _card("Black Removal", 15, 2, ["Instant"], ["W"]),
        ],
        [],
    )

    result = session.apply_auto_lands()

    assert result.ok
    assert sum(c["count"] for c in session.deck_list) == 40


def test_sample_hand_draws_seven(env):
    session = _session(env)
    session.import_deck([_card("White Knight", 40)], [])

    hand = session.sample_hand()

    assert len(hand.cards) == 7
