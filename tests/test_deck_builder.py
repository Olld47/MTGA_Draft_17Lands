"""
tests/test_deck_builder.py
High-impact test targeting the V4 Deck Suggester and Holistic Scoring engine.
"""

import pytest
from unittest.mock import MagicMock
from src.card_logic import suggest_deck, calculate_dynamic_mana_base, count_fixing
from src.configuration import Configuration


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking the global average to 55.0% and Standard Deviation to 3.0
    metrics.get_metrics.return_value = (55.0, 3.0)
    return metrics


@pytest.fixture
def sample_pool():
    pool = []
    # 1. Add 15 solid On-Color (Green/Red) Spells
    for i in range(15):
        pool.append(
            {
                "name": f"Gruul Beater {i}",
                "types": ["Creature"],
                "colors": ["R", "G"],
                "cmc": 4,
                "mana_cost": "{2}{R}{G}",
                "deck_colors": {"All Decks": {"gihwr": 59.0}},
            }
        )
    # 2. Add 1 Off-Color Elite Bomb (Blue) for the Splash builder to find
    pool.append(
        {
            "name": "Dream Trawler",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 6,
            "mana_cost": "{4}{U}{U}",
            "deck_colors": {"All Decks": {"gihwr": 65.0}},  # Very high win rate
        }
    )
    # 3. Add 15 low-CMC Aggro cards for the Tempo builder
    for i in range(15):
        pool.append(
            {
                "name": f"Goblin {i}",
                "types": ["Creature"],
                "colors": ["R"],
                "cmc": 1,
                "mana_cost": "{R}",
                "deck_colors": {"All Decks": {"gihwr": 56.0}},
            }
        )
    # 4. Add Fixing to satisfy the Alien Gold/Splash protection
    for i in range(3):
        pool.append(
            {
                "name": f"Evolving Wilds {i}",
                "types": ["Land"],
                "colors": [],
                "text": "search your library for a basic land",
                "deck_colors": {"All Decks": {"gihwr": 55.0}},
            }
        )
    return pool


def test_full_deck_suggestion_pipeline(sample_pool, mock_metrics):
    """
    Passes a simulated draft pool into the engine to trigger the creation of
    Consistency, Greedy, and Tempo deck variants.
    """
    config = Configuration()

    # Run the massive function
    results = suggest_deck(sample_pool, mock_metrics, config, event_type="PremierDraft")

    # Assertions
    assert len(results) > 0, "Deck builder failed to generate any archetypes."

    labels = list(results.keys())

    # Ensure it generated different variants
    assert any("Safe Core" in label for label in labels) or any(
        "Consistent" in label for label in labels
    ), "Failed to build Safe Core/Consistency variant"

    assert any("Safe Tempo" in label for label in labels) or any(
        "Tempo" in label for label in labels
    ), "Failed to build Safe Tempo/Tempo variant"

    assert any("Splash" in label for label in labels), "Failed to build Splash variant"


def test_dynamic_mana_base_math():
    """Verify the proportional land allocation guarantees minimums."""
    # Simulate a deck heavily skewed to Red, with a light Green splash
    spells = [{"mana_cost": "{R}"} for _ in range(15)] + [
        {"mana_cost": "{G}"} for _ in range(2)
    ]

    lands = calculate_dynamic_mana_base(spells, [], ["R", "G"], forced_count=17)

    # Count the generated basic lands
    forests = sum(1 for c in lands if c["name"] == "Forest")
    mountains = sum(1 for c in lands if c["name"] == "Mountain")

    assert len(lands) == 17
    assert forests >= 3, "Light splash should have a hard floor of 3 sources"
    assert mountains >= 6, "Primary color should have a hard floor of 6 sources"


def test_hybrid_mana_does_not_force_unneeded_lands():
    spells = [{"mana_cost": "{U}"} for _ in range(15)] + [
        {"mana_cost": "{W/U}"} for _ in range(2)
    ]
    lands = calculate_dynamic_mana_base(spells, [], ["U", "W"], forced_count=17)

    plains = sum(1 for c in lands if c["name"] == "Plains")
    islands = sum(1 for c in lands if c["name"] == "Island")

    assert plains == 0
    assert islands == 17


def test_proportional_mana_base_fixes_starvation():
    """Verify that a 3-color pool distributes lands using Frank Karsten targets and caps splash basics."""
    spells = (
        [{"mana_cost": "{U}"} for _ in range(8)]
        + [{"mana_cost": "{B}"} for _ in range(3)]
        + [{"mana_cost": "{G}"} for _ in range(7)]
    )

    lands = calculate_dynamic_mana_base(spells, [], ["U", "B", "G"], forced_count=17)

    islands = sum(1 for c in lands if c["name"] == "Island")
    swamps = sum(1 for c in lands if c["name"] == "Swamp")
    forests = sum(1 for c in lands if c["name"] == "Forest")

    assert islands == 8
    assert swamps == 2
    assert forests == 7


def test_mana_source_analyzer():
    """Verify the fixing counter correctly identifies fetch lands and duals."""
    pool = [
        {"name": "Forest", "types": ["Land", "Basic"]},  # Should be ignored
        {"name": "Jungle Hollow", "types": ["Land"], "colors": ["B", "G"]},  # Dual
        {
            "name": "Unknown Shores",
            "types": ["Land"],
            "text": "add one mana of any color",
        },  # Any
    ]

    fixing = count_fixing(pool)

    assert fixing["G"] == 2
    assert fixing["B"] == 2
    assert fixing["R"] == 1


def _variant(label, rating, colors, breakdown=""):
    return (
        label,
        {
            "rating": rating,
            "colors": colors,
            "breakdown": breakdown,
            "deck_cards": [],
        },
    )


def test_safe_deck_gating_rejects_incomplete_and_weak():
    """Regression: a Power-12, Est 0-3, land-padded incomplete deck was crowned
    'Safe Core' and promoted to slot 2 purely for having <=2 colors."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 83.0, ["G", "B", "U", "W", "R"]),
        _variant("UG Splash W", 82.0, ["G", "U", "W"]),
        _variant(
            "G Splash W",
            12.0,
            ["G", "W"],
            breakdown="Incomplete Deck (-20.0) | Flood Risk (-50.7)",
        ),
    ]
    assert select_safe_deck_index(final_list) == -1


def test_safe_deck_gating_accepts_reasonable_two_color():
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 83.0, ["G", "B", "U", "W", "R"]),
        _variant("UG Consistent", 65.0, ["G", "U"], breakdown="Solid"),
    ]
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_gating_rejects_far_behind_decks():
    """A 2-color deck massively behind the best option is not 'safe' advice."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 90.0, ["G", "B", "U"]),
        _variant("UG Consistent", 40.0, ["G", "U"], breakdown="Solid"),
    ]
    assert select_safe_deck_index(final_list) == -1


def _greedy_pool(main_g, main_b, splash_u):
    """Pool with castable GB main spells, strong mono-U splash candidates, and
    one GU dual so the splash is mechanically enabled."""
    pool = [
        {
            "name": f"G Bear {i}",
            "types": ["Creature"],
            "colors": ["G"],
            "cmc": 2,
            "mana_cost": "{1}{G}",
            "deck_colors": {"All Decks": {"gihwr": 56.0}},
        }
        for i in range(main_g)
    ]
    pool += [
        {
            "name": f"B Bruiser {i}",
            "types": ["Creature"],
            "colors": ["B"],
            "cmc": 3,
            "mana_cost": "{2}{B}",
            "deck_colors": {"All Decks": {"gihwr": 56.0}},
        }
        for i in range(main_b)
    ]
    pool += [
        {
            "name": f"U Bomb {i}",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 3,
            "mana_cost": "{2}{U}",
            "deck_colors": {"All Decks": {"gihwr": 62.0}},
        }
        for i in range(splash_u)
    ]
    pool.append(
        {
            "name": "GU Dual",
            "types": ["Land"],
            "colors": ["G", "U"],
            "deck_colors": {"All Decks": {"gihwr": 54.0}},
        }
    )
    return pool


def test_greedy_splash_is_capped(mock_metrics):
    """Regression: with thin main colors the greedy builder filled the deck
    with every splash candidate (6 'splash' cards on 2 sources)."""
    from src.card_logic import build_variant_greedy

    pool = _greedy_pool(main_g=9, main_b=9, splash_u=6)
    deck, splash_col = build_variant_greedy(pool, ["B", "G"], mock_metrics)

    assert deck is not None
    assert splash_col == "U"
    u_spells = sum(
        c.get("count", 1)
        for c in deck
        if c.get("colors") == ["U"] and "Land" not in c.get("types", [])
    )
    assert u_spells <= 2, f"Splash not capped: {u_spells} blue spells"


def test_greedy_skips_unsupported_pair_instead_of_over_splashing(mock_metrics):
    """If the main colors can't reach ~20 spells even with a capped splash,
    the pair isn't a real deck — skip it rather than over-splash."""
    from src.card_logic import build_variant_greedy

    pool = _greedy_pool(main_g=7, main_b=7, splash_u=6)
    deck, splash_col = build_variant_greedy(pool, ["B", "G"], mock_metrics)

    assert deck is None
