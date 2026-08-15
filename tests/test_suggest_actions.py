"""
tests/test_suggest_actions.py
Tests for the shared AI-deck-builder action layer (src.suggest_actions).
Ticket 09 convergence: the build pipeline (spell-count guard, engine call,
error/empty settling, snap-to-strongest, stale tracking) previously lived
twice — verbatim in mtga_bridge.suggest_session and in the tkinter
SuggestDeckPanel — and drifted. SuggestActions is the single implementation
both adapters delegate to; these tests pin its observable behavior at that
seam. src.advisor.deck_builder.suggest_deck is stubbed so no Monte Carlo runs.
"""

from unittest.mock import patch

import pytest

from src.suggest_actions import SuggestActions, playable_spell_message


@pytest.fixture
def actions():
    return SuggestActions()


def _card(name, types=("Creature",), count=1):
    return {"name": name, "types": list(types), "count": count}


def _pool(n_spells=23, spell_name="Bolt"):
    """A pool with `n_spells` playable spells, all copies of one name."""
    return [_card(spell_name) for _ in range(n_spells)]


class _FakeConfig:
    class _CardData:
        latest_dataset = "TEST_PremierDraft_All_Data.json"

    card_data = _CardData()


def _suggestion(deck_cards, **overrides):
    data = {
        "label_prefix": "Consistent",
        "type": "Deck",
        "rating": 72.4,
        "record": "5-2",
        "deck_cards": deck_cards,
        "sideboard_cards": [],
        "colors": ["W", "U"],
        "identity_colors": ["W", "U"],
        "breakdown": "Strong curve",
        "stats": {},
        "optimization_note": "",
    }
    data.update(overrides)
    return data


# --- build pipeline ----------------------------------------------------------


def test_calculate_thin_pool_sets_status_and_clears(actions):
    ok, message = actions.calculate(_pool(n_spells=5), {}, "PremierDraft", _FakeConfig())
    assert ok is False
    assert "Not enough spells drafted yet" in message
    assert "Have 5" in message
    assert actions.suggestions == {}
    assert actions.selected == ""
    assert actions.status == message
    assert actions.is_building is False


def test_calculate_empty_result_sets_on_color_message(actions):
    with patch("src.advisor.deck_builder.suggest_deck", return_value={}):
        ok, message = actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert ok is False
    assert "Not enough on-color playables" in message
    assert "40-card deck" in message
    assert actions.suggestions == {}


def test_calculate_swallows_engine_error(actions):
    with patch(
        "src.advisor.deck_builder.suggest_deck", side_effect=RuntimeError("boom")
    ):
        ok, message = actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert ok is False
    assert message == "Builder error — see the log for details."
    assert actions.status == message
    assert actions.suggestions == {}
    assert actions.is_building is False


def test_calculate_success_snaps_to_strongest_first(actions):
    results = {
        "WU Consistent (Power: 72)": _suggestion([_card("WU Flex")]),
        "BR Tempo (Power: 60)": _suggestion([_card("Red Burn")]),
    }
    with patch("src.advisor.deck_builder.suggest_deck", return_value=results):
        ok, message = actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert ok is True
    assert message == ""
    assert actions.suggestions == results
    assert actions.selected == "WU Consistent (Power: 72)"
    assert actions.status == ""
    assert actions.is_building is False


def test_calculate_resets_building_flag_on_every_path(actions):
    """is_building must clear on empty and error paths — the adapters render
    the flag as the spinner state."""
    with patch("src.advisor.deck_builder.suggest_deck", return_value={}):
        actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert actions.is_building is False

    with patch(
        "src.advisor.deck_builder.suggest_deck", side_effect=RuntimeError("boom")
    ):
        actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert actions.is_building is False


def test_calculate_runs_engine_even_if_flag_preset(actions):
    """The panel declares 'building' up front (synchronous double-submit
    guard) before the worker calls calculate — the flag must not make the
    pipeline bail; the engine still runs and the flag is reset after."""
    actions.is_building = True
    with patch(
        "src.advisor.deck_builder.suggest_deck",
        return_value={"A": _suggestion([_card("WU Flex")])},
    ):
        ok, _ = actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert ok is True
    assert actions.is_building is False


# --- progress streaming -------------------------------------------------------


def test_calculate_forwards_raw_engine_messages(actions):
    seen = []

    def fake_suggest(pool, metrics, configuration, event_type, callback, dataset_name):
        callback({"status": "Analyzing WU Archetypes..."})
        callback(
            {
                "variant_label": "WU Consistent",
                "variant_data": _suggestion([_card("WU Flex")]),
            }
        )
        return {"WU Consistent": _suggestion([_card("WU Flex")])}

    with patch("src.advisor.deck_builder.suggest_deck", side_effect=fake_suggest):
        actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig(), progress=seen.append)

    assert seen[0] == {"status": "Analyzing WU Archetypes..."}
    assert seen[1]["variant_label"] == "WU Consistent"
    assert seen[1]["variant_data"]["rating"] == 72.4


# --- selection / accessors ----------------------------------------------------


def test_select_switches_and_ignores_unknown(actions):
    actions.suggestions = {"A": _suggestion([_card("WU Flex")])}
    actions.select("A")
    assert actions.selected == "A"
    actions.select("Nonexistent")
    assert actions.selected == "A"


def test_active_lists_return_empty_without_selection(actions):
    assert actions.active_lists() == ([], [])


def test_export_text_renders_mtga_format(actions):
    actions.suggestions = {
        "A": _suggestion(
            [_card("WU Flex", count=2)], sideboard_cards=[_card("Red Burn")]
        )
    }
    actions.selected = "A"
    text = actions.export_text()
    assert "2 WU Flex" in text
    assert "Red Burn" in text


def test_deck_lists_are_copies(actions):
    actions.suggestions = {"A": _suggestion([_card("WU Flex", count=4)])}
    actions.selected = "A"
    deck, _ = actions.deck_lists()
    deck[0]["count"] = 99
    assert actions.suggestions["A"]["deck_cards"][0]["count"] == 4


# --- stale tracking -----------------------------------------------------------


def test_stale_true_before_any_build(actions):
    assert actions.is_stale(_pool()) is True


def test_stale_clears_after_successful_build(actions):
    with patch(
        "src.advisor.deck_builder.suggest_deck",
        return_value={"A": _suggestion([_card("WU Flex")])},
    ):
        actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert actions.is_stale(_pool()) is False


def test_stale_rearms_on_pool_change(actions):
    with patch(
        "src.advisor.deck_builder.suggest_deck",
        return_value={"A": _suggestion([_card("WU Flex")])},
    ):
        actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert actions.is_stale(_pool(n_spells=24)) is True


def test_stale_ignores_row_layout_of_same_pool(actions):
    """Two pools with the same cards in the same quantities — one row per copy
    vs stacked rows — are the same pool, not a stale trigger."""
    with patch(
        "src.advisor.deck_builder.suggest_deck",
        return_value={"A": _suggestion([_card("WU Flex")])},
    ):
        actions.calculate(_pool(n_spells=2, spell_name="WU Flex"), {}, "PremierDraft", _FakeConfig())
    stacked = [{"name": "WU Flex", "types": ["Creature"], "count": 2}]
    assert actions.is_stale(stacked) is False


def test_stale_records_key_on_thin_pool(actions):
    """The thin-pool path settles on the pool it saw, so stale only re-arms
    once the pool actually clears the spell guard."""
    thin = _pool(n_spells=5)
    actions.calculate(thin, {}, "PremierDraft", _FakeConfig())
    assert actions.is_stale(thin) is False
    assert actions.is_stale(_pool(n_spells=23)) is True


def test_stale_stays_true_after_engine_error(actions):
    """A failed build leaves stale=True so the frontend retries instead of
    pinning the error message to a finished pool."""
    with patch(
        "src.advisor.deck_builder.suggest_deck", side_effect=RuntimeError("boom")
    ):
        actions.calculate(_pool(), {}, "PremierDraft", _FakeConfig())
    assert actions.is_stale(_pool()) is True


# --- guard helper -------------------------------------------------------------


def test_playable_spell_message_threshold():
    assert playable_spell_message(_pool(n_spells=21)) is not None
    assert playable_spell_message(_pool(n_spells=22)) is None
    assert playable_spell_message(_pool(n_spells=23)) is None


def test_playable_spell_message_ignores_lands():
    pool = [_card("Bolt") for _ in range(22)] + [
        _card("Plains", types=("Land", "Basic"))
    ]
    assert playable_spell_message(pool) is None


@pytest.fixture
def actions():
    return SuggestActions()
