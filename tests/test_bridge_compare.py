"""
tests/test_bridge_compare.py
Bridge-layer tests for the Compare workspace port (mtga_bridge.compare_session).
Exercises CompareSession against a real ArenaScanner with a mock card database.
No pytauri or tkinter.
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

from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src.log_scanner import ArenaScanner
from src.utils import Result

from mtga_bridge.compare_session import CompareSession
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import CompareStateVM


# --- Fixtures ----------------------------------------------------------------


_POOL_CARDS = [
    ("White Knight", 2, ["Creature"], ["W"], "{1}{W}", 58.0),
    ("Blue Flyer", 3, ["Creature"], ["U"], "{2}{U}", 56.0),
    ("Black Removal", 2, ["Instant"], ["B"], "{1}{B}", 60.0),
    ("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0),
    ("Green Beast", 4, ["Creature"], ["G"], "{2}{G}{G}", 59.0),
    ("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0),
]


def _mock_dataset():
    return {
        "meta": {"version": 3.0, "game_count": 10000},
        "card_ratings": {
            str(200 + i): {
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
        data={
            "Test Set": SetInfo(arena=["TEST"], seventeenlands=["TEST"], set_code="TEST")
        }
    )

    config = Configuration()
    config.settings.arena_log_location = str(log_file)

    with patch(
        "src.dataset.check_file_integrity", return_value=(Result.VALID, data)
    ):
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))
        scanner.current_draft_id = "test_draft"

    # No pool needed for compare — the filter resolves to All Decks with []
    scanner.retrieve_taken_cards = lambda: []
    scanner.retrieve_tier_data = lambda: {}

    runtime = AppRuntime(config=config, scanner=scanner)
    return {"runtime": runtime, "scanner": scanner, "config": config}


def _session(env) -> CompareSession:
    return env["runtime"].compare_session()


# --- available names ---------------------------------------------------------


def test_available_names_sorted_unique(env):
    names = _session(env).available_names()
    assert names == sorted(names)
    assert "White Knight" in names
    assert "" not in names
    assert len(names) == len(_POOL_CARDS)


# --- add / dedup -------------------------------------------------------------


def test_add_card_resolves_and_dedups(env):
    session = _session(env)
    assert session.add_card("White Knight") is True
    # Already present -> rejected, list unchanged
    assert session.add_card("White Knight") is False
    assert len(session.compare_list) == 1


def test_add_card_case_insensitive(env):
    session = _session(env)
    assert session.add_card("  blue flyer  ") is True
    assert session.compare_list[0]["name"] == "Blue Flyer"


def test_add_unknown_card_rejected(env):
    session = _session(env)
    assert session.add_card("Totally Fake Card") is False
    assert session.add_card("") is False
    assert session.compare_list == []


# --- state build -------------------------------------------------------------


def test_build_state_renders_cards_with_stats(env):
    session = _session(env)
    session.add_card("WU Flex")
    state = session.build_state()
    assert isinstance(state, CompareStateVM)
    assert state.active_filter == "All Decks"
    assert len(state.cards) == 1
    card = state.cards[0]
    assert card.name == "WU Flex"
    assert card.stats.gihwr == 61.0
    assert card.colors == ["W", "U"]


def test_build_state_preserves_add_order(env):
    session = _session(env)
    for name in ["Green Beast", "Red Burn", "White Knight"]:
        session.add_card(name)
    state = session.build_state()
    assert [c.name for c in state.cards] == ["Green Beast", "Red Burn", "White Knight"]


# --- remove / clear ----------------------------------------------------------


def test_remove_card(env):
    session = _session(env)
    session.add_card("White Knight")
    session.add_card("Blue Flyer")
    session.remove_card("White Knight")
    names = [c.name for c in session.build_state().cards]
    assert names == ["Blue Flyer"]


def test_clear(env):
    session = _session(env)
    session.add_card("White Knight")
    session.add_card("Blue Flyer")
    session.clear()
    assert session.build_state().cards == []


# --- serialization -----------------------------------------------------------


def test_state_serializes_camel_case(env):
    session = _session(env)
    session.add_card("White Knight")
    dumped = session.build_state().model_dump(by_alias=True)
    assert "activeFilter" in dumped
    assert "availableNames" in dumped
    assert "cards" in dumped
