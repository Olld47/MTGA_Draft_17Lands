"""
tests/test_bridge_practice.py
Bridge-layer tests for the practice-pool port (mtga_bridge.practice): set
listing, random pack generation, MTGA decklist import, and the hand-off into
SealedStudioSession.load_external_pool. No pytauri or tkinter.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

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

from mtga_bridge import practice
from mtga_bridge.runtime import AppRuntime


# The dataset integrity check rejects files with fewer than 10 cards.
_CARDS = [
    ("Common A", "common"),
    ("Common B", "common"),
    ("Common C", "common"),
    ("Common D", "common"),
    ("Common E", "common"),
    ("Uncommon A", "uncommon"),
    ("Uncommon B", "uncommon"),
    ("Uncommon C", "uncommon"),
    ("Rare A", "rare"),
    ("Rare B", "rare"),
    ("Mythic A", "mythic"),
]


def _mock_dataset():
    ratings = {
        str(300 + i): {
            "name": name,
            "cmc": 2,
            "types": ["Creature"],
            "colors": ["W"],
            "rarity": rarity,
            "mana_cost": "{1}{W}",
            "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": 3.0}},
        }
        for i, (name, rarity) in enumerate(_CARDS)
    }
    ratings["999"] = {
        "name": "Plains",
        "cmc": 0,
        "types": ["Basic", "Land"],
        "colors": [],
        "rarity": "common",
        "mana_cost": "",
        "deck_colors": {"All Decks": {"gihwr": 0.0, "alsa": 0.0}},
    }
    return {"meta": {"version": 3.0, "game_count": 10000}, "card_ratings": ratings}


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
        latest_set="TEST",
        data={
            "Test Set": SetInfo(
                arena=["TEST"], seventeenlands=["TEST"], set_code="TEST"
            ),
            "Older Set": SetInfo(
                arena=["OLD"], seventeenlands=["OLD"], set_code="OLD"
            ),
        },
    )

    config = Configuration()
    config.settings.arena_log_location = str(log_file)

    with patch("src.dataset.check_file_integrity", return_value=(Result.VALID, data)):
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))

    scanner.retrieve_taken_cards = lambda: []
    scanner.retrieve_tier_data = lambda: {}

    runtime = AppRuntime(config=config, scanner=scanner)
    return {
        "runtime": runtime,
        "scanner": scanner,
        "config": config,
        "dataset_path": str(dataset_path),
    }


# --- Set listing --------------------------------------------------------------


def test_list_practice_sets_orders_active_first(env):
    with patch(
        "mtga_bridge.practice.read_local_manifest",
        return_value={"active_sets": ["OLD"]},
    ):
        vm = practice.list_practice_sets(env["scanner"])

    labels = [s.label for s in vm.sets]
    # OLD is manifest-active (rank 0); TEST is appended as latest_set (rank 1).
    assert labels == ["Older Set (OLD)", "Test Set (TEST)"]
    assert all(s.is_active for s in vm.sets)
    assert vm.default_code == "OLD"


def test_list_practice_sets_sorts_inactive_alphabetically(env):
    with patch("mtga_bridge.practice.read_local_manifest", return_value={}):
        env["scanner"].set_list.latest_set = ""
        vm = practice.list_practice_sets(env["scanner"])

    assert [s.label for s in vm.sets] == ["Older Set (OLD)", "Test Set (TEST)"]
    assert not any(s.is_active for s in vm.sets)


def test_list_practice_sets_without_set_list_is_empty():
    class _Bare:
        set_list = None

    vm = practice.list_practice_sets(_Bare())
    assert vm.sets == []
    assert vm.default_code == ""


# --- Random pool generation ---------------------------------------------------


def test_generate_random_pool_pack_composition(env):
    pool, error = practice.generate_random_pool(env["scanner"].set_data)
    assert error == ""
    # 6 packs * (1 rare + 3 uncommons + 10 commons)
    assert len(pool) == 84

    rarities = [c["rarity"] for c in pool]
    assert sum(r in ("rare", "mythic") for r in rarities) == 6
    assert rarities.count("uncommon") == 18
    assert rarities.count("common") == 60
    assert "Plains" not in [c["name"] for c in pool]


def test_generate_random_pool_returns_copies(env):
    pool, _ = practice.generate_random_pool(env["scanner"].set_data)
    pool[0]["name"] = "Mutated"
    ratings = env["scanner"].set_data.get_card_ratings()
    assert "Mutated" not in [c["name"] for c in ratings.values()]


def test_generate_random_pool_rejects_incomplete_dataset(env):
    class _CommonsOnly:
        @staticmethod
        def get_card_ratings():
            return {"1": {"name": "Common A", "rarity": "common", "types": []}}

    pool, error = practice.generate_random_pool(_CommonsOnly())
    assert pool == []
    assert "incomplete" in error


# --- MTGA decklist import -----------------------------------------------------


def test_parse_pool_text_expands_counts(env):
    text = "Deck\n2 Common A\n1 Rare A (TEST) 42\n\nSideboard\n3 Uncommon B"
    pool, error = practice.parse_pool_text(env["scanner"].set_data, text)
    assert error == ""
    names = [c["name"] for c in pool]
    assert names.count("Common A") == 2
    assert names.count("Rare A") == 1
    assert names.count("Uncommon B") == 3


def test_parse_pool_text_skips_unknown_cards(env):
    pool, error = practice.parse_pool_text(
        env["scanner"].set_data, "1 Common A\n4 Not In This Set"
    )
    assert error == ""
    assert [c["name"] for c in pool] == ["Common A"]


def test_parse_pool_text_rejects_garbage(env):
    pool, error = practice.parse_pool_text(
        env["scanner"].set_data, "This is just some random text."
    )
    assert pool == []
    assert "No valid MTGA format cards" in error


# --- start_practice -----------------------------------------------------------


@pytest.fixture
def started(env):
    """Patches the set-list scan so the fixture's dataset is the only match."""
    rows = [("TEST", "PremierDraft", "All", "", "", 0, env["dataset_path"], "")]
    with patch(
        "mtga_bridge.practice.retrieve_local_set_list", return_value=(rows, [])
    ):
        yield env


def test_start_practice_generates_and_loads_pool(started):
    session = started["runtime"].sealed_session()
    result = practice.start_practice(
        started["scanner"], started["config"], session, "TEST"
    )

    assert result.ok
    assert result.state.has_pool is True
    assert result.state.pool_size == 84
    assert result.state.session_id.startswith("practice_")
    # Everything starts in the pool, nothing in the main deck.
    assert result.state.main_count == 0
    assert result.state.sideboard_count == 84


def test_start_practice_imports_decklist(started):
    session = started["runtime"].sealed_session()
    result = practice.start_practice(
        started["scanner"],
        started["config"],
        session,
        "TEST",
        import_text="2 Common A\n1 Rare A",
    )

    assert result.ok
    assert result.state.pool_size == 3


def test_start_practice_replaces_a_previous_pool(started):
    session = started["runtime"].sealed_session()
    practice.start_practice(started["scanner"], started["config"], session, "TEST")
    first_id = session.session.session_id

    result = practice.start_practice(
        started["scanner"],
        started["config"],
        session,
        "TEST",
        import_text="1 Common A",
    )
    assert result.state.pool_size == 1
    assert session.session.session_id != first_id


def test_start_practice_prefers_the_sealed_dataset(env):
    """Sealed data outranks Premier/Traditional when several are downloaded."""
    rows = [
        ("TEST", "TradDraft", "All", "", "", 0, "/fake/trad.json", ""),
        ("TEST", "Sealed", "All", "", "", 0, env["dataset_path"], ""),
        ("TEST", "PremierDraft", "All", "", "", 0, "/fake/premier.json", ""),
    ]
    session = env["runtime"].sealed_session()
    with patch(
        "mtga_bridge.practice.retrieve_local_set_list", return_value=(rows, [])
    ), patch("mtga_bridge.practice.select_dataset_blocking", return_value=True) as sel:
        practice.start_practice(env["scanner"], env["config"], session, "TEST")

    assert sel.call_args[0][2] == env["dataset_path"]


def test_start_practice_without_dataset_fails_cleanly(env):
    session = env["runtime"].sealed_session()
    with patch("mtga_bridge.practice.retrieve_local_set_list", return_value=([], [])):
        result = practice.start_practice(
            env["scanner"], env["config"], session, "TEST"
        )

    assert result.ok is False
    assert "No downloaded dataset found" in result.message
    assert result.state.has_pool is False


def test_start_practice_requires_a_set_code(env):
    session = env["runtime"].sealed_session()
    result = practice.start_practice(env["scanner"], env["config"], session, "")
    assert result.ok is False
    assert "Select a set" in result.message


def test_start_practice_bad_import_leaves_pool_untouched(started):
    session = started["runtime"].sealed_session()
    practice.start_practice(started["scanner"], started["config"], session, "TEST")

    result = practice.start_practice(
        started["scanner"],
        started["config"],
        session,
        "TEST",
        import_text="nothing parseable here",
    )
    assert result.ok is False
    assert result.state.pool_size == 84


# --- SealedStudioSession.load_external_pool -----------------------------------


def test_load_external_pool_persists_under_its_own_id(env, tmp_path):
    session = env["runtime"].sealed_session()
    pool = [dict(c) for c in env["scanner"].set_data.get_data_by_name(["Common A"])]
    session.load_external_pool(pool, "practice_abc123")

    assert session.session.session_id == "practice_abc123"
    saved = tmp_path / "Temp" / "sealed_practice_abc123.json"
    assert saved.exists()
    assert json.loads(saved.read_text())["session_id"] == "practice_abc123"


def test_ensure_pool_keeps_an_external_pool(env):
    """A loaded practice pool must not be clobbered by the scanner's (empty)
    taken cards on the next ensure_pool call."""
    session = env["runtime"].sealed_session()
    pool = [dict(c) for c in env["scanner"].set_data.get_data_by_name(["Common A"])]
    session.load_external_pool(pool, "practice_keepme")

    assert session.ensure_pool() is True
    assert session.session.session_id == "practice_keepme"
