"""
tests/test_compare_actions.py
Tests for the shared comparison-workspace action layer
(src.compare_actions), the single implementation the desktop bridge (mtga_bridge.compare_session)
and the pre-convergence panel delegate to — ticket 09 convergence. The
behaviors here are the ones the bridge port (`tests/test_bridge_compare.py`)
already pinned, re-expressed against the pure layer: no scanner, explicit card-map parameters.
"""

from unittest.mock import patch

import pytest

from src import constants
from src.compare_actions import (
    CompareActions,
    available_names,
    find_card,
    resolve_active_filter,
)

_CARDS = [
    ("White Knight", 2, ["Creature"], ["W"]),
    ("Blue Flyer", 3, ["Creature"], ["U"]),
    ("Black Removal", 2, ["Instant"], ["B"]),
    ("Red Burn", 1, ["Instant"], ["R"]),
    ("Green Beast", 4, ["Creature"], ["G"]),
    ("WU Flex", 3, ["Creature"], ["W", "U"]),
]


def _card_map():
    return {
        str(i): {"name": name, "cmc": cmc, "types": types, "colors": colors}
        for i, (name, cmc, types, colors) in enumerate(_CARDS)
    }


@pytest.fixture
def actions():
    return CompareActions()


# --- card database lookups ---------------------------------------------------


def test_available_names_sorted_unique():
    names = available_names(_card_map())

    assert names == sorted(names)
    assert "White Knight" in names
    assert len(names) == len(_CARDS)


def test_available_names_ignores_blank_names():
    card_map = _card_map()
    card_map["99"] = {"name": "", "cmc": 0}

    names = available_names(card_map)

    assert "" not in names


def test_find_card_is_case_insensitive_and_stripped():
    found = find_card(_card_map(), "  blue flyer  ")

    assert found is not None
    assert found["name"] == "Blue Flyer"


def test_find_card_returns_none_for_empty_or_unknown():
    assert find_card(_card_map(), "") is None
    assert find_card(_card_map(), "Not A Card") is None


# --- color resolution --------------------------------------------------------


def test_resolve_active_filter_uses_the_first_resolved_color():
    with patch("src.compare_actions.filter_options", return_value=["W", "U"]):
        assert resolve_active_filter([], "Auto", object(), object()) == "W"


def test_resolve_active_filter_falls_back_to_all_decks():
    with patch("src.compare_actions.filter_options", return_value=[]):
        assert (
            resolve_active_filter([], "Auto", object(), object())
            == constants.FILTER_OPTION_ALL_DECKS
        )


# --- mutations ---------------------------------------------------------------


def test_add_card_resolves_and_dedups(actions):
    assert actions.add_card(_card_map(), "White Knight") is True
    assert actions.add_card(_card_map(), "White Knight") is False
    assert len(actions.compare_list) == 1


def test_add_card_case_insensitive(actions):
    assert actions.add_card(_card_map(), "  blue flyer  ") is True
    assert actions.compare_list[0]["name"] == "Blue Flyer"


def test_add_unknown_card_rejected(actions):
    assert actions.add_card(_card_map(), "Black Lotus") is False
    assert actions.compare_list == []


def test_add_card_preserves_add_order(actions):
    for name in ("Green Beast", "Red Burn", "White Knight"):
        actions.add_card(_card_map(), name)

    assert [c["name"] for c in actions.compare_list] == [
        "Green Beast",
        "Red Burn",
        "White Knight",
    ]


def test_add_card_data_appends_and_dedups_by_name(actions):
    assert actions.add_card_data({"name": "Lightning Bolt"}) is True
    # Same name, different dict object (e.g. dataset reload) -> still a dup.
    assert actions.add_card_data({"name": "Lightning Bolt"}) is False
    assert len(actions.compare_list) == 1


def test_add_card_data_rejects_empty(actions):
    assert actions.add_card_data(None) is False
    assert actions.add_card_data({}) is False
    assert actions.compare_list == []


def test_remove_card(actions):
    actions.add_card(_card_map(), "White Knight")
    actions.add_card(_card_map(), "Blue Flyer")

    actions.remove_card("White Knight")

    assert [c["name"] for c in actions.compare_list] == ["Blue Flyer"]


def test_remove_card_ignores_unknown_name(actions):
    actions.add_card(_card_map(), "White Knight")

    actions.remove_card("Ghost")

    assert len(actions.compare_list) == 1


def test_clear(actions):
    actions.add_card(_card_map(), "White Knight")

    actions.clear()

    assert actions.compare_list == []
