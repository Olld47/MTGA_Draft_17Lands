"""
tests/test_deck_actions.py
Tests for the shared custom-deck action layer (src.deck_actions.DeckActions),
the single implementation the desktop bridge (mtga_bridge.deck_session)
and the pre-convergence panel delegate to — ticket 09 convergence. The behaviors here are the ones the bridge port
(`tests/test_bridge_deck.py`) already pinned, re-expressed against the pure
layer: no scanner, explicit parameters.
"""

from unittest.mock import patch

import pytest

from src import constants
from src.deck_actions import DeckActions


@pytest.fixture
def actions():
    return DeckActions()


def _card(name, count=1, cmc=2, types=None, colors=None):
    return {
        "name": name,
        "count": count,
        "cmc": cmc,
        "types": list(types) if types else ["Creature"],
        "colors": list(colors) if colors else [],
    }


def _basic(name, count=1):
    return _card(name, count, 0, ["Land", "Basic"], [])


# --- inbound ----------------------------------------------------------------


def test_import_deck_deep_copies_and_records_pool_size(actions):
    deck = [_card("White Knight", 2)]
    actions.import_deck(deck, [], pool_size=12)

    deck[0]["count"] = 99  # mutating the caller's list must not write back

    assert actions.deck_list[0]["count"] == 2
    assert actions.known_pool_size == 12


def test_refresh_pool_appends_only_new_cards(actions):
    actions.import_deck([_card("White Knight", 2)], [_card("Blue Flyer", 1)], pool_size=3)

    # Pool grew: 3 White Knights drafted total (2 already in the deck).
    pool = [_card("White Knight") for _ in range(3)] + [_card("Blue Flyer")]
    actions.refresh_pool(pool)

    assert actions.known_pool_size == 4
    assert next(c for c in actions.sb_list if c["name"] == "White Knight")["count"] == 1
    assert next(c for c in actions.sb_list if c["name"] == "Blue Flyer")["count"] == 1


def test_refresh_pool_moves_newly_drafted_cards_to_the_sideboard(actions):
    actions.import_deck([_card("White Knight", 1)], [], pool_size=1)

    actions.refresh_pool([_card("White Knight"), _card("Green Beast")])

    assert actions.known_pool_size == 2
    assert next(c for c in actions.sb_list if c["name"] == "Green Beast")["count"] == 1


def test_refresh_pool_resets_when_the_pool_is_gone(actions):
    """A new draft empties the pool; the previous deck must not survive it."""
    actions.import_deck([_card("White Knight", 1)], [_card("Blue Flyer", 1)], pool_size=6)

    actions.refresh_pool([])

    assert actions.deck_list == []
    assert actions.sb_list == []
    assert actions.known_pool_size == 0


def test_refresh_pool_is_a_noop_when_the_pool_has_not_grown(actions):
    actions.import_deck([_card("White Knight", 1)], [_card("Blue Flyer", 2)], pool_size=2)

    actions.refresh_pool([_card("White Knight"), _card("Blue Flyer")])

    assert actions.deck_list[0]["count"] == 1
    assert actions.sb_list[0]["count"] == 2


# --- mutations ---------------------------------------------------------------


def test_move_card_decrements_source_and_increments_destination(actions):
    actions.import_deck([_card("White Knight", 2)], [_card("Blue Flyer", 1)], pool_size=0)

    actions.move_card("White Knight", to_sideboard=True)

    assert actions.deck_list[0]["count"] == 1
    assert next(c for c in actions.sb_list if c["name"] == "White Knight")["count"] == 1


def test_move_card_removes_the_row_at_zero(actions):
    actions.import_deck([_card("White Knight", 1)], [], pool_size=0)

    actions.move_card("White Knight", to_sideboard=True)

    assert actions.deck_list == []
    assert next(c for c in actions.sb_list if c["name"] == "White Knight")["count"] == 1


def test_move_card_back_from_the_sideboard(actions):
    actions.import_deck([], [_card("Blue Flyer", 1)], pool_size=0)

    actions.move_card("Blue Flyer", to_sideboard=False)

    assert actions.sb_list == []
    assert actions.deck_list[0]["name"] == "Blue Flyer"


def test_move_card_ignores_an_unknown_name(actions):
    actions.import_deck([_card("White Knight", 1)], [], pool_size=0)

    actions.move_card("Ghost", to_sideboard=True)

    assert actions.sb_list == []
    assert actions.deck_list[0]["count"] == 1


def test_clear_deck_returns_spells_but_discards_basics(actions):
    """Basics are generated, not drafted, so returning them to the sideboard
    would pollute the pool."""
    actions.import_deck(
        [_card("White Knight", 1), _basic("Plains", 2)],
        [_card("Blue Flyer", 1)],
        pool_size=0,
    )

    actions.clear_deck()

    assert actions.deck_list == []
    assert next(c for c in actions.sb_list if c["name"] == "White Knight")["count"] == 1
    assert next(c for c in actions.sb_list if c["name"] == "Blue Flyer")["count"] == 1
    assert not any(c["name"] == "Plains" for c in actions.sb_list)


def test_clear_deck_merges_into_an_existing_sideboard_row(actions):
    actions.import_deck([_card("White Knight", 2)], [_card("White Knight", 1)], pool_size=0)

    actions.clear_deck()

    assert next(c for c in actions.sb_list if c["name"] == "White Knight")["count"] == 3


def test_add_basic_creates_a_row_with_wubrg_color_metadata(actions):
    actions.add_basic("Plains")

    assert actions.deck_list == [
        {"name": "Plains", "cmc": 0, "types": ["Land", "Basic"], "colors": ["W"], "count": 1}
    ]


def test_add_basic_increments_an_existing_row(actions):
    actions.add_basic("Island")
    actions.add_basic("Island")

    assert actions.deck_list[0]["count"] == 2


def test_remove_basic_decrements_and_removes_the_row_at_zero(actions):
    actions.add_basic("Swamp")
    actions.remove_basic("Swamp")

    assert actions.deck_list == []


def test_remove_basic_ignores_a_land_not_in_the_deck(actions):
    actions.remove_basic("Forest")

    assert actions.deck_list == []


# --- engine operations -------------------------------------------------------


def test_run_simulation_rejects_an_incomplete_deck(actions):
    actions.import_deck([_card("White Knight", 1)], [], pool_size=0)

    ok, message, stats, note = actions.run_simulation()

    assert ok is False
    assert "40 cards" in message
    assert stats is None


def test_run_simulation_returns_stats_for_a_complete_deck(actions):
    with patch("src.advisor.simulator.simulate_deck", return_value={"win_rate": 55.0}):
        actions.import_deck([_card("White Knight", 40)], [], pool_size=0)
        ok, message, stats, note = actions.run_simulation()

    assert ok is True
    assert stats == {"win_rate": 55.0}


def test_auto_optimize_rejects_a_deck_that_is_not_forty(actions):
    actions.import_deck([_card("White Knight", 39)], [], pool_size=0)

    ok, message, stats, note = actions.auto_optimize()

    assert ok is False
    assert "currently 39" in message
    assert stats is None


def test_auto_optimize_mutates_and_sorts_the_deck(actions):
    with patch(
        "src.advisor.deck_builder.optimize_deck",
        return_value=(
            [_card("Zephyr", 1, 3), _card("Aegis", 1, 1)],  # deliberately unsorted
            [],
            {"win_rate": 58.0},
            "18 Lands",
        ),
    ):
        actions.import_deck([_card("White Knight", 40)], [], pool_size=0)
        ok, message, stats, note = actions.auto_optimize()

    assert ok is True
    assert [c["name"] for c in actions.deck_list] == ["Aegis", "Zephyr"]
    assert stats == {"win_rate": 58.0}
    assert note == "18 Lands"


def test_auto_optimize_reports_a_failed_optimization(actions):
    with patch("src.advisor.deck_builder.optimize_deck", return_value=([], [], {}, "")):
        actions.import_deck([_card("White Knight", 40)], [], pool_size=0)
        ok, message, stats, note = actions.auto_optimize()

    assert ok is False
    assert message == "Failed to optimize."


def test_apply_auto_lands_requires_spells(actions):
    actions.import_deck([_basic("Plains", 5)], [], pool_size=0)

    ok, message, stats, note = actions.apply_auto_lands()

    assert ok is False
    assert "spells" in message.lower()


def test_apply_auto_lands_fills_to_forty(actions):
    with patch(
        "src.deck_actions.brute_force_mana_base",
        return_value=[_basic("Plains") for _ in range(17)],
    ), patch("src.advisor.simulator.simulate_deck", return_value={"win_rate": 50.0}):
        actions.import_deck([_card("White Knight", 23, 2, ["Creature"], ["W"])], [], pool_size=0)
        ok, message, stats, note = actions.apply_auto_lands()

    assert ok is True
    assert sum(c["count"] for c in actions.deck_list) == 40
    assert sum(c["count"] for c in actions.deck_list if c["name"] in constants.BASIC_LANDS) == 17
    assert stats == {"win_rate": 50.0}


def test_apply_auto_lands_replaces_previous_basics(actions):
    """Re-running must not stack a second mana base on top of the first."""
    with patch(
        "src.deck_actions.brute_force_mana_base",
        return_value=[_basic("Plains") for _ in range(17)],
    ), patch("src.advisor.simulator.simulate_deck", return_value={"win_rate": 50.0}):
        actions.import_deck(
            [
                _card("White Knight", 23, 2, ["Creature"], ["W"]),
                _basic("Island", 9),
            ],
            [],
            pool_size=0,
        )
        ok, message, stats, note = actions.apply_auto_lands()

    assert ok is True
    basics = [c for c in actions.deck_list if c["name"] in constants.BASIC_LANDS]
    assert sum(c["count"] for c in basics) == 17
    assert not any(c["name"] == "Island" for c in basics)


def test_apply_auto_lands_counts_copies_not_rows(actions):
    """The land count is `40 - spells`, and deck_list is *stacked* — each row
    can be several cards. Counting rows overshot by one land per duplicate
    spell and produced decks larger than 40."""
    with patch(
        "src.deck_actions.brute_force_mana_base",
        return_value=[_basic("Plains") for _ in range(17)],
    ) as mock_bf, patch("src.advisor.simulator.simulate_deck", return_value={"win_rate": 50.0}):
        actions.import_deck(
            [
                _card("White Knight", 4, 2, ["Creature"], ["W"]),
                _card("Blue Flyer", 4, 3, ["Creature"], ["W"]),
                _card("Black Removal", 15, 2, ["Instant"], ["W"]),
            ],
            [],
            pool_size=0,
        )
        ok, message, stats, note = actions.apply_auto_lands()

    assert ok is True
    assert sum(c["count"] for c in actions.deck_list) == 40
    assert mock_bf.call_args.kwargs["forced_count"] == 17


# --- export ------------------------------------------------------------------


def test_export_text_emits_an_mtga_decklist(actions):
    actions.import_deck([_card("White Knight", 2)], [_card("Blue Flyer", 1)], pool_size=0)

    text = actions.export_text()

    assert "White Knight" in text
    assert "Blue Flyer" in text
