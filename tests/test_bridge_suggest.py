"""
tests/test_bridge_suggest.py
Bridge-layer tests for the Suggest Deck port (mtga_bridge.suggest_session) and
the shared simulation/advice builders extracted into mtga_bridge.deck_view.
Exercises SuggestSession against a real ArenaScanner with a mock pool, with
src.card_logic.suggest_deck stubbed so tests don't run 10k-game Monte Carlo.
No pytauri or tkinter.
"""

import json
import os
import sys
import threading
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

from mtga_bridge.deck_view import build_advice, build_sample_hand, build_sim_result
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.suggest_session import SuggestSession
from mtga_bridge.viewmodels import SuggestStateVM


# --- Fixtures ----------------------------------------------------------------

_POOL_CARDS = [
    ("White Knight", 2, ["Creature"], ["W"], "{1}{W}", 58.0),
    ("Blue Flyer", 3, ["Creature"], ["U"], "{2}{U}", 56.0),
    ("Black Removal", 2, ["Instant"], ["B"], "{1}{B}", 60.0),
    ("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0),
    ("Green Beast", 4, ["Creature"], ["G"], "{2}{G}{G}", 59.0),
    ("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0),
]

_SIM_STATS = {
    "mulligans": 12.0,
    "screw_t3": 14.0,
    "screw_t4": 20.0,
    "flood_t5": 18.0,
    "cast_t2": 68.0,
    "cast_t3": 70.0,
    "cast_t4": 60.0,
    "curve_out": 30.0,
    "removal_t4": 62.0,
    "color_screw_t3": 4.0,
    "avg_hand_size": 6.9,
}


def _card(name, cmc, types, colors, cost, gihwr, count=1):
    return {
        "name": name,
        "cmc": cmc,
        "types": types,
        "colors": colors,
        "mana_cost": cost,
        "count": count,
        "deck_colors": {"All Decks": {"gihwr": gihwr, "alsa": 3.0}},
    }


def _pool(count_each=5):
    """A pool with enough spells to clear the 22-spell minimum."""
    return [
        _card(f"{name} {i}", cmc, types, colors, cost, gihwr)
        for name, cmc, types, colors, cost, gihwr in _POOL_CARDS
        for i in range(count_each)
    ]


def _suggestion(deck_cards, sideboard_cards=None, **overrides):
    data = {
        "label_prefix": "Consistent",
        "type": "Deck",
        "rating": 72.4,
        "record": "5-2",
        "deck_cards": deck_cards,
        "sideboard_cards": sideboard_cards or [],
        "colors": ["W", "U"],
        "identity_colors": ["W", "U"],
        "breakdown": "Strong curve",
        "stats": dict(_SIM_STATS),
        "optimization_note": "",
    }
    data.update(overrides)
    return data


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

    with patch("src.dataset.check_file_integrity", return_value=(Result.VALID, data)):
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))
        scanner.current_draft_id = "test_draft"

    scanner.retrieve_taken_cards = lambda: _pool()
    scanner.retrieve_tier_data = lambda: {}
    scanner.retrieve_set_metrics = lambda *a, **k: {}
    scanner.retrieve_current_limited_event = lambda: ("TEST", "PremierDraft")

    runtime = AppRuntime(config=config, scanner=scanner)
    return {"runtime": runtime, "scanner": scanner, "config": config}


def _session(env) -> SuggestSession:
    return env["runtime"].suggest_session()


# --- build guards ------------------------------------------------------------


def test_calculate_rejects_thin_pool(env):
    env["scanner"].retrieve_taken_cards = lambda: _pool(count_each=1)  # 6 spells
    session = _session(env)
    session.calculate()
    assert "Not enough spells" in session.status
    assert session.suggestions == {}
    assert session.build_state().deck == []


def test_calculate_reports_empty_result(env):
    session = _session(env)
    with patch("src.card_logic.suggest_deck", return_value={}):
        session.calculate()
    assert "Not enough on-color playables" in session.status
    assert session.suggestions == {}


def test_calculate_swallows_builder_error(env):
    session = _session(env)
    with patch("src.card_logic.suggest_deck", side_effect=RuntimeError("boom")):
        session.calculate()
    assert session.status == "Builder error — see the log for details."
    assert session.is_building is False


def test_calculate_selects_strongest_deck_first(env):
    session = _session(env)
    results = {
        "WU Consistent (Power: 72)": _suggestion([_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=4)]),
        "BR Tempo (Power: 60)": _suggestion([_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0)]),
    }
    with patch("src.card_logic.suggest_deck", return_value=results):
        session.calculate()
    assert session.status == ""
    assert session.selected == "WU Consistent (Power: 72)"


def test_calculate_releases_lock_during_engine_run(env):
    """The engine run takes seconds of Monte Carlo; holding the scanner lock
    across it would stall the log-scanning thread. Probed from another thread
    because the lock is reentrant for the calling one."""
    session = _session(env)
    lock = env["scanner"].lock
    acquired_by_other_thread = []

    def probe():
        got = lock.acquire(blocking=False)
        acquired_by_other_thread.append(got)
        if got:
            lock.release()

    def fake_suggest(*args, **kwargs):
        t = threading.Thread(target=probe)
        t.start()
        t.join()
        return {"A": _suggestion([_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0)])}

    with patch("src.card_logic.suggest_deck", side_effect=fake_suggest):
        session.calculate()

    assert acquired_by_other_thread == [True]


# --- progress streaming ------------------------------------------------------


def test_calculate_forwards_progress_events(env):
    session = _session(env)
    events = []

    def fake_suggest(pool, metrics, config, event_type, callback, dataset_name):
        callback({"status": "Analyzing WU Archetypes..."})
        callback(
            {
                "variant_label": "WU Consistent",
                "variant_data": _suggestion([_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0)]),
            }
        )
        return {"WU Consistent": _suggestion([_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0)])}

    with patch("src.card_logic.suggest_deck", side_effect=fake_suggest):
        session.calculate(progress=lambda kind, payload: events.append((kind, payload)))

    assert events[0][0] == "status"
    assert events[0][1]["text"] == "Analyzing WU Archetypes..."
    assert events[1][0] == "variant"
    archetype = events[1][1]["archetype"]
    assert archetype.label == "WU Consistent"
    assert archetype.record == "5-2"


# --- selection / state build --------------------------------------------------


def _built(env, results):
    session = _session(env)
    with patch("src.card_logic.suggest_deck", return_value=results):
        session.calculate()
    return session


def test_select_switches_active_deck(env):
    deck_a = [_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=4)]
    deck_b = [_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0, count=2)]
    session = _built(env, {"A": _suggestion(deck_a), "B": _suggestion(deck_b)})

    session.select("B")
    state = session.build_state()
    assert state.selected == "B"
    assert [r.name for r in state.deck] == ["Red Burn"]
    assert state.main_count == 2


def test_select_ignores_unknown_label(env):
    session = _built(env, {"A": _suggestion([_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0)])})
    session.select("Nonexistent")
    assert session.selected == "A"


def test_build_state_exposes_archetypes_and_sim(env):
    deck = [
        _card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=4),
        _card("Plains", 0, ["Land", "Basic"], ["W"], "", 0.0, count=8),
    ]
    sb = [_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0)]
    session = _built(env, {"WU Consistent": _suggestion(deck, sb)})
    state = session.build_state()

    assert isinstance(state, SuggestStateVM)
    assert len(state.archetypes) == 1
    arch = state.archetypes[0]
    assert arch.rating == 72.4
    assert arch.identity_colors == ["W", "U"]
    assert arch.main_count == 12

    assert state.breakdown == "Strong curve"
    assert state.main_count == 12
    assert state.sideboard_count == 1
    assert state.stats.lands == 8
    assert state.stats.creatures == 4
    assert state.sim is not None
    assert state.sim.stats.cast_t2 == 68.0


def test_build_state_sorts_by_cmc_then_name(env):
    deck = [
        _card("Green Beast", 4, ["Creature"], ["G"], "{2}{G}{G}", 59.0),
        _card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0),
        _card("Blue Flyer", 3, ["Creature"], ["U"], "{2}{U}", 56.0),
    ]
    session = _built(env, {"A": _suggestion(deck)})
    assert [r.name for r in session.build_state().deck] == [
        "Red Burn",
        "Blue Flyer",
        "Green Beast",
    ]


def test_build_state_without_suggestions(env):
    state = _session(env).build_state()
    assert state.archetypes == []
    assert state.selected == ""
    assert state.sim is None


def test_build_state_omits_sim_when_stats_missing(env):
    session = _built(
        env,
        {"A": _suggestion([_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0)], stats=None)},
    )
    assert session.build_state().sim is None


# --- deck hand-off / export ---------------------------------------------------


def test_deck_lists_are_copies(env):
    deck = [_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=4)]
    session = _built(env, {"A": _suggestion(deck)})

    copied_deck, _ = session.deck_lists()
    copied_deck[0]["count"] = 99
    assert session.suggestions["A"]["deck_cards"][0]["count"] == 4


def test_export_renders_mtga_text(env):
    deck = [_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=2)]
    sb = [_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0)]
    session = _built(env, {"A": _suggestion(deck, sb)})
    text = session.export().text
    assert "2 WU Flex" in text
    assert "Red Burn" in text


def test_export_empty_without_selection(env):
    assert _session(env).export().text.strip() in ("", "Deck", "Deck\n\nSideboard")


# --- sample hand --------------------------------------------------------------


def test_sample_hand_draws_seven_sorted(env):
    deck = [
        _card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=10),
        _card("Plains", 0, ["Land", "Basic"], ["W"], "", 0.0, count=10),
    ]
    session = _built(env, {"A": _suggestion(deck)})
    hand = session.sample_hand()
    assert len(hand.cards) == 7
    # Basic lands sort ahead of spells
    lands = [i for i, c in enumerate(hand.cards) if "Land" in c.types]
    spells = [i for i, c in enumerate(hand.cards) if "Land" not in c.types]
    assert not lands or not spells or max(lands) < min(spells)


def test_sample_hand_without_deck(env):
    assert _session(env).sample_hand().message == "Generate a deck first."


def test_sample_hand_short_deck(env):
    session = _built(
        env, {"A": _suggestion([_card("Red Burn", 1, ["Instant"], ["R"], "{R}", 55.0)])}
    )
    assert session.sample_hand().message == "Deck has fewer than 7 cards."


# --- shared deck_view builders ------------------------------------------------


def test_build_sample_hand_exposes_image_urls():
    deck = [dict(_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=10))]
    deck[0]["image"] = ["https://cards.scryfall.io/normal/front/a/b/abc.jpg"]
    hand = build_sample_hand(deck, "All Decks")
    assert hand.cards[0].image == ["https://cards.scryfall.io/normal/front/a/b/abc.jpg"]


def test_build_advice_flags_weak_early_game():
    stats = dict(_SIM_STATS, cast_t2=40.0, removal_t4=30.0)
    advice = build_advice([], [], stats, "")
    assert any("2-drops" in a for a in advice)
    assert any("cheap removal" in a for a in advice)


def test_build_advice_respects_optimization_note():
    stats = dict(_SIM_STATS, screw_t3=30.0, flood_t5=35.0)
    with_note = build_advice([], [], stats, "Optimized: 16 Lands")
    assert not any("extra land" in a for a in with_note)
    without_note = build_advice([], [], stats, "")
    assert any("extra land" in a for a in without_note)


def test_build_advice_warns_on_three_colors():
    deck = [
        _card("W Card", 1, ["Creature"], ["W"], "{W}", 55.0),
        _card("U Card", 1, ["Creature"], ["U"], "{U}", 55.0),
        _card("B Card", 1, ["Creature"], ["B"], "{B}", 55.0),
    ]
    advice = build_advice(deck, [], dict(_SIM_STATS), "")
    assert any("3+ colors" in a for a in advice)


def test_build_sim_result_rounds_stats():
    result = build_sim_result([], [], dict(_SIM_STATS, mulligans=12.3456), "")
    assert result.ok is True
    assert result.stats.mulligans == 12.35


# --- serialization ------------------------------------------------------------


def test_state_serializes_camel_case(env):
    deck = [_card("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}", 61.0, count=4)]
    session = _built(env, {"A": _suggestion(deck)})
    dumped = session.build_state().model_dump(by_alias=True)
    assert "isBuilding" in dumped
    assert "mainCount" in dumped
    assert "activeFilter" in dumped
    assert "identityColors" in dumped["archetypes"][0]
    assert "rowTag" in dumped["deck"][0]
