"""
tests/test_bridge_sealed.py
Bridge-layer tests for the Sealed Studio port (mtga_bridge.sealed_session and
the shared mtga_bridge.deck_view builders). Exercises SealedStudioSession
against a real ArenaScanner with a mock sealed pool. No pytauri or tkinter.
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

from mtga_bridge.deck_view import build_stats, row_vm
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.sealed_session import SealedStudioSession
from mtga_bridge.viewmodels import SealedStateVM


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
        scanner.current_draft_id = "test_sealed"

    # Flat 48-card pool (8 copies of each of the 6 cards), as the scanner returns.
    prototypes = scanner.set_data.get_data_by_name([c[0] for c in _POOL_CARDS])
    pool = [dict(proto) for proto in prototypes for _ in range(8)]

    scanner.retrieve_taken_cards = lambda: pool
    scanner.retrieve_tier_data = lambda: {}

    runtime = AppRuntime(config=config, scanner=scanner)
    return {"runtime": runtime, "scanner": scanner, "config": config, "pool": pool}


def _session(env) -> SealedStudioSession:
    session = env["runtime"].sealed_session()
    session.ensure_pool()
    return session


# --- deck_view shared builders ----------------------------------------------


def test_build_stats_counts_and_basics():
    deck = [
        {"name": "White Knight", "cmc": 2, "types": ["Creature"], "colors": ["W"],
         "mana_cost": "{1}{W}", "count": 3},
        {"name": "Plains", "cmc": 0, "types": ["Land", "Basic"], "colors": [], "count": 5},
    ]
    stats = build_stats(deck)
    assert stats.total_cards == 8
    assert stats.creatures == 3
    assert stats.lands == 5
    assert stats.noncreatures == 0
    assert stats.avg_cmc == 2.0
    assert stats.basics["Plains"] == 5
    assert stats.curve["2"] == 3
    # one white pip per copy
    white = next(p for p in stats.pips if p.symbol == "W")
    assert white.count == 3


def test_build_stats_empty_returns_zeroes():
    stats = build_stats([])
    assert stats.total_cards == 0
    assert stats.pips == []


def test_row_vm_uses_active_filter_gihwr():
    card = {
        "name": "Blue Flyer", "cmc": 3, "types": ["Creature"], "colors": ["U"],
        "mana_cost": "{2}{U}", "count": 2,
        "deck_colors": {"All Decks": {"gihwr": 56.4}},
    }
    vm = row_vm(card, "All Decks")
    assert vm.name == "Blue Flyer"
    assert vm.count == 2
    assert vm.gihwr == 56.4
    # Unknown filter -> no gihwr
    assert row_vm(card, "WU").gihwr is None


# --- pool loading ------------------------------------------------------------


def test_ensure_pool_loads_and_defaults(env):
    session = _session(env)
    state = session.build_state()
    assert isinstance(state, SealedStateVM)
    assert state.has_pool is True
    assert state.pool_size == 48
    assert state.variants  # default "Build 1"
    assert state.active_variant


def test_no_pool_returns_empty_state(env):
    env["scanner"].retrieve_taken_cards = lambda: []
    session = env["runtime"].sealed_session()
    assert session.ensure_pool() is False
    state = session.build_state()
    assert state.has_pool is False
    assert state.pool_size == 0


# --- card movement -----------------------------------------------------------


def test_move_to_main_and_back(env):
    session = _session(env)
    res = session.move_card("White Knight", to_sideboard=False, count=2)
    assert res.ok
    assert res.state.main_count == 2
    assert res.state.deck[0].name == "White Knight"

    back = session.move_card("White Knight", to_sideboard=True, count=2)
    assert back.state.main_count == 0


def test_move_over_pool_limit_rejected(env):
    session = _session(env)
    res = session.move_card("White Knight", to_sideboard=False, count=100)
    assert res.ok is False
    assert "limit" in res.message.lower() or "pool" in res.message.lower()
    assert res.state.main_count == 0


def test_clear_deck(env):
    session = _session(env)
    session.move_card("White Knight", to_sideboard=False, count=3)
    cleared = session.clear_deck()
    assert cleared.ok
    assert cleared.state.main_count == 0


# --- variant management ------------------------------------------------------


def test_variant_create_rename_delete(env):
    session = _session(env)
    session.create_variant("Aggro")
    assert session.session.active_variant_name == "Aggro"

    renamed = session.rename_variant("Aggro", "Tempo")
    assert renamed.ok
    assert "Tempo" in session.session.variants

    count_before = len(session.session.variants)
    deleted = session.delete_variant("Tempo")
    assert deleted.ok
    assert len(session.session.variants) == count_before - 1


def test_cannot_delete_only_variant(env):
    session = _session(env)
    # Collapse to a single variant.
    for name in list(session.session.variants):
        if name != session.session.active_variant_name:
            session.session.delete_variant(name)
    only = session.session.active_variant_name
    res = session.delete_variant(only)
    assert res.ok is False
    assert only in session.session.variants


def test_select_variant(env):
    session = _session(env)
    session.create_variant("Second")
    res = session.select_variant(session.session.active_variant_name)
    assert res.ok


# --- shell generation --------------------------------------------------------


def test_auto_generate_builds_shells(env):
    session = _session(env)
    res = session.auto_generate()
    assert res.ok
    assert len(res.state.variants) >= 1


def test_auto_generate_rejects_small_pool(env):
    env["scanner"].retrieve_taken_cards = lambda: env["pool"][:10]
    session = env["runtime"].sealed_session()
    session.reload_pool()
    res = session.auto_generate()
    assert res.ok is False
    assert "40" in res.message


# --- import / export ---------------------------------------------------------


def test_import_deck_from_text(env):
    session = _session(env)
    res = session.import_deck("Deck\n4 White Knight\n3 Blue Flyer\n")
    assert res.ok
    assert res.state.main_count == 7


def test_import_deck_reports_missing(env):
    session = _session(env)
    res = session.import_deck("Deck\n2 White Knight\n2 Totally Fake Card\n")
    assert res.ok  # partial import still ok
    assert "Fake" in res.message or "skipped" in res.message.lower()


def test_import_deck_rejects_garbage(env):
    session = _session(env)
    res = session.import_deck("this is not a decklist")
    assert res.ok is False


def test_export_active_deck(env):
    session = _session(env)
    session.move_card("White Knight", to_sideboard=False, count=2)
    export = session.export()
    assert "Deck" in export.text
    assert "White Knight" in export.text


# --- auto-lands --------------------------------------------------------------


def test_apply_auto_lands_adds_basics(env):
    session = _session(env)
    # Put spells across two colors in main.
    for name in ["White Knight", "Blue Flyer", "WU Flex"]:
        session.move_card(name, to_sideboard=False, count=7)
    res = session.apply_auto_lands()
    assert res.ok
    basics = res.state.stats.basics
    added = sum(basics.values())
    # calculate_dynamic_mana_base returns exactly forced_count basics; the port
    # mirrors the tkinter handler's needed = 40 - len(spell_entries) - len(nonbasics).
    assert added > 0
    # White/Blue are the deck's colors, so those basics should dominate.
    assert basics["Plains"] > 0 and basics["Island"] > 0
    assert basics["Swamp"] == 0 and basics["Mountain"] == 0 and basics["Forest"] == 0


def test_apply_auto_lands_requires_spells(env):
    session = _session(env)
    res = session.apply_auto_lands()
    assert res.ok is False


# --- serialization -----------------------------------------------------------


def test_state_serializes_camel_case(env):
    session = _session(env)
    dumped = session.build_state().model_dump(by_alias=True)
    assert "hasPool" in dumped
    assert "poolSize" in dumped
    assert "mainCount" in dumped
    assert "activeVariant" in dumped
    assert "sideboardCount" in dumped
