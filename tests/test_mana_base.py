"""
tests/test_mana_base.py
Challenges the status quo of Mana Base generation and Monte Carlo simulations.
"""

import pytest
from collections import Counter
from src.card_logic import build_variant_greedy, simulate_deck
from src.advisor.mana_base import calculate_dynamic_mana_base
from unittest.mock import MagicMock


def _spell(name, color, cmc=2, tags=None, text=""):
    return {
        "name": name,
        "types": ["Creature"],
        "colors": [color],
        "cmc": cmc,
        "mana_cost": f"{{{cmc - 1}}}{{{color}}}",
        "tags": tags or [],
        "oracle_text": text,
        "deck_colors": {"All Decks": {"gihwr": 56.0}},
    }


def test_treasure_spells_do_not_replace_basic_lands():
    """Regression: one-shot Treasure makers were credited as full permanent
    any-color sources, zeroing the basics for secondary colors (a real MSH
    pool produced 13 Forest / 1 Island under five blue spells)."""
    spells = (
        [_spell(f"G Bear {i}", "G") for i in range(12)]
        + [_spell(f"U Flyer {i}", "U") for i in range(5)]
        + [
            _spell(
                f"G Treasure Maker {i}",
                "G",
                tags=["fixing_ramp"],
                text="When this enters, create a Treasure token.",
            )
            for i in range(6)
        ]
    )

    basics = calculate_dynamic_mana_base(spells, [], ["G", "U"], forced_count=17)
    counts = Counter(c["name"] for c in basics)

    assert sum(counts.values()) == 17
    # 5 hard blue pips demand real blue sources, treasures notwithstanding
    assert counts["Island"] >= 4, f"Blue starved: {dict(counts)}"
    assert counts["Forest"] >= 8, f"Green starved: {dict(counts)}"


def test_every_pipped_color_gets_a_source():
    """Regression: a 5-color soup deck received basics for only 2 of its 5
    pipped colors (12 Forest / 2 Swamp), leaving W/U/R spells with zero
    sources of any kind."""
    spells = (
        [_spell(f"G Bear {i}", "G") for i in range(10)]
        + [_spell(f"U Card {i}", "U", cmc=3) for i in range(4)]
        + [_spell(f"B Card {i}", "B", cmc=4) for i in range(3)]
        + [_spell("W Card", "W", cmc=2)]
        + [_spell("R Card", "R", cmc=2)]
        + [
            _spell(
                f"Fixer {i}",
                "G",
                tags=["fixing_ramp"],
                text="Create a Treasure token.",
            )
            for i in range(5)
        ]
    )

    basics = calculate_dynamic_mana_base(
        spells, [], ["W", "U", "B", "R", "G"], forced_count=17
    )
    counts = Counter(c["colors"][0] for c in basics)

    assert sum(counts.values()) == 17
    for color in ["W", "U", "B", "R", "G"]:
        assert counts.get(color, 0) >= 1, (
            f"{color} has pips but zero sources: {dict(counts)}"
        )


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    metrics.get_metrics.return_value = (55.0, 3.0)
    return metrics


def test_greedy_double_pip_bomb_splash(mock_metrics):
    """
    Simulates a WB deck attempting to splash a 3UU Bomb.
    Without fixing, the builder should reject it.
    With heavy fixing (Treasures/Duals), the builder should allow it and the MC should pass.
    """
    # Base WB Pool
    pool = [
        {
            "name": f"White 2-Drop {i}",
            "types": ["Creature"],
            "colors": ["W"],
            "cmc": 2,
            "mana_cost": "{1}{W}",
            "deck_colors": {"All Decks": {"gihwr": 57.0}},
        }
        for i in range(10)
    ] + [
        {
            "name": f"Black 3-Drop {i}",
            "types": ["Creature"],
            "colors": ["B"],
            "cmc": 3,
            "mana_cost": "{2}{B}",
            "deck_colors": {"All Decks": {"gihwr": 57.0}},
        }
        for i in range(10)
    ]

    # The 3UU Bomb (Huge Z-Score)
    pool.append(
        {
            "name": "Dream Trawler Level Bomb",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 6,
            "mana_cost": "{4}{U}{U}",
            "deck_colors": {"All Decks": {"gihwr": 68.0}},
        }
    )

    # SCENARIO 1: No Fixing. The builder should REJECT the double-pip splash.
    greedy_deck_nofix, splash_color_nofix = build_variant_greedy(
        pool, ["W", "B"], mock_metrics
    )
    assert splash_color_nofix != "U", "Should reject 3UU splash without fixing."

    # SCENARIO 2: Abundant Fixing. Add 3 duals and a treasure maker.
    pool.extend(
        [
            {
                "name": "WB Dual",
                "types": ["Land"],
                "colors": ["W", "B"],
                "deck_colors": {"All Decks": {"gihwr": 54.0}},
            },
            {
                "name": "WU Dual",
                "types": ["Land"],
                "colors": ["W", "U"],
                "deck_colors": {"All Decks": {"gihwr": 54.0}},
            },
            {
                "name": "BU Dual",
                "types": ["Land"],
                "colors": ["B", "U"],
                "deck_colors": {"All Decks": {"gihwr": 54.0}},
            },
            {
                "name": "Treasure Dork",
                "types": ["Creature"],
                "colors": ["W"],
                "cmc": 2,
                "mana_cost": "{1}{W}",
                "tags": ["fixing_ramp"],
                "oracle_text": "Create a treasure",
                "deck_colors": {"All Decks": {"gihwr": 55.0}},
            },
        ]
    )

    greedy_deck_fix, splash_color_fix = build_variant_greedy(
        pool, ["W", "B"], mock_metrics
    )

    assert splash_color_fix == "U", (
        "Should actively embrace the 3UU bomb when fixing is heavy."
    )

    # Verify the Monte Carlo actually accepts the treasure dork as a valid mana source
    stats = simulate_deck(greedy_deck_fix, iterations=500)

    # Because we have duals and treasure dorks, our cast_t2 and cast_t3 rates for the core WB deck should remain relatively high despite the U splash!
    assert stats["cast_t2"] > 40.0, (
        "Core WB velocity destroyed by splash! Auto-Lands allocated basics poorly."
    )
