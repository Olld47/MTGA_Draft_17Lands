"""
tests/test_deck_builder.py
High-impact test targeting the V4 Deck Suggester and Holistic Scoring engine.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.advisor.deck_builder import suggest_deck
from src.advisor.mana_base import calculate_dynamic_mana_base, count_fixing
from src.configuration import Configuration


def _planning_card(name="Card", color="G"):
    return {
        "name": name,
        "types": ["Creature"],
        "colors": [color],
        "mana_cost": f"{{{color}}}",
        "deck_colors": {"All Decks": {"gihwr": 55.0}},
    }


def _planning_deck(name, color="G"):
    return [_planning_card(name, color) | {"count": 40}]


def _patch_planning_variants(monkeypatch, consistency, curve=None, soup=None):
    from src.advisor import deck_builder

    monkeypatch.setattr(
        deck_builder, "build_variant_consistency", lambda *args: consistency
    )
    monkeypatch.setattr(
        deck_builder,
        "build_variant_curve",
        lambda *args: curve if curve is not None else consistency,
    )
    monkeypatch.setattr(
        deck_builder, "build_variant_greedy", lambda *args: (None, None)
    )
    monkeypatch.setattr(
        deck_builder,
        "build_variant_soup",
        lambda *args: soup if soup is not None else (None, []),
    )
    monkeypatch.setattr(deck_builder, "get_sideboard", lambda pool, deck: [])
    monkeypatch.setattr(
        deck_builder, "identify_top_pairs", lambda *args: [["G", "R"]]
    )


def _planning_two_color_deck(name, first="G", second="R"):
    return [
        _planning_card(f"{name} {first}", first) | {"count": 20},
        _planning_card(f"{name} {second}", second) | {"count": 20},
    ]


def _planning_stats():
    return {
        "color_screw_t3": 0.0,
        "screw_t3": 0.0,
        "flood_t5": 0.0,
    }



def test_suggest_deck_caches_ordered_results_and_reports_progress(
    mock_metrics, monkeypatch
):
    """The planning interface caches a result without changing its output order."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    candidate = _planning_two_color_deck("Core")
    _patch_planning_variants(monkeypatch, candidate)
    monkeypatch.setattr(
        deck_builder,
        "simulate_deck",
        lambda *args, **kwargs: _planning_stats(),
    )
    monkeypatch.setattr(
        deck_builder,
        "calculate_holistic_score",
        lambda *args: (70.0, "Stable core"),
    )

    first_progress = []
    first = suggest_deck(
        pool,
        mock_metrics,
        Configuration(),
        progress_callback=first_progress.append,
    )
    second_progress = []
    second = suggest_deck(
        pool,
        mock_metrics,
        Configuration(),
        progress_callback=second_progress.append,
    )

    assert list(second) == list(first)
    assert first_progress
    assert second_progress == [{"status": "Loaded optimized decks from cache."}]


def test_suggest_deck_applies_mana_risk_penalties_to_public_rating(
    mock_metrics, monkeypatch
):
    """The returned recommendation rating includes all three mana-risk penalties."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    _patch_planning_variants(monkeypatch, _planning_two_color_deck("Risky"))
    monkeypatch.setattr(
        deck_builder,
        "simulate_deck",
        lambda *args, **kwargs: {
            "color_screw_t3": 12.0,
            "screw_t3": 24.0,
            "flood_t5": 29.0,
        },
    )
    monkeypatch.setattr(
        deck_builder,
        "calculate_holistic_score",
        lambda *args: (70.0, "Base score"),
    )

    result = suggest_deck(pool, mock_metrics, Configuration())

    recommendation = next(iter(result.values()))
    assert recommendation["rating"] == 59.0
    assert "Color Screw (-5.0)" in recommendation["breakdown"]
    assert "Mana Screw (-3.0)" in recommendation["breakdown"]
    assert "Flood Risk (-3.0)" in recommendation["breakdown"]

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
                "oracle_text": "search your library for a basic land",
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
            "oracle_text": "add one mana of any color",
        },  # Any
    ]

    fixing = count_fixing(pool)

    assert fixing["G"] == 2
    assert fixing["B"] == 2
    assert fixing["R"] == 1


def _variant(label, rating, colors, breakdown="", identity_colors=None):
    return (
        label,
        {
            "rating": rating,
            "colors": colors,
            "identity_colors": (
                identity_colors if identity_colors is not None else colors
            ),
            "breakdown": breakdown,
            "deck_cards": [],
        },
    )


def test_safe_deck_prefers_best_two_color():
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 83.0, ["G", "B", "U", "W", "R"]),
        _variant("UG Consistent", 65.0, ["G", "U"], breakdown="Solid"),
    ]
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_uses_identity_colors_ignoring_incidental_splash():
    """A deck labeled 3-color only because one gold card adds a single off-color
    pip (identity_colors == 2) still counts as the safe 2-color option."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant(
            "BG Good Stuff",
            83.0,
            ["G", "B", "U", "W", "R"],
            identity_colors=["G", "B", "U"],
        ),
        _variant(
            "BG Splash W",
            79.0,
            ["G", "B", "W"],
            breakdown="Solid",
            identity_colors=["G", "B"],
        ),
    ]
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_prefers_complete_over_incomplete():
    """A complete 2-color deck beats a higher-rated but incomplete one."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("Soup", 83.0, ["G", "B", "U"]),
        _variant(
            "GU Incomplete", 50.0, ["G", "U"], breakdown="Incomplete Deck (-20.0)"
        ),
        _variant("GB Complete", 45.0, ["G", "B"], breakdown="Solid"),
    ]
    assert select_safe_deck_index(final_list) == 2


def test_safe_deck_surfaces_incomplete_two_color_when_only_option():
    """User always wants at least one <=2-color deck: an incomplete, weak, or
    far-behind 2-color deck is still surfaced when it's the only non-soupy option."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 83.0, ["G", "B", "U", "W", "R"]),
        _variant("UG Splash W", 82.0, ["G", "U", "W"]),
        _variant(
            "G Splash W",
            14.0,
            ["G", "W"],
            breakdown="Incomplete Deck (-20.0) | Flood Risk (-50.7)",
            identity_colors=["G"],
        ),
    ]
    assert select_safe_deck_index(final_list) == 2


def test_safe_deck_tiebreak_prefers_tighter_mana():
    """Two near-equal 2-color-identity decks: prefer the one with fewer actual
    colors (fewer incidental splashes) so 'Safe' has the tightest mana."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant(
            "BG Splash WU",
            82.0,
            ["G", "B", "W", "U"],
            breakdown="Solid",
            identity_colors=["G", "B"],
        ),
        _variant(
            "UG Splash W",
            82.0,
            ["G", "U", "W"],
            breakdown="Solid",
            identity_colors=["G", "U"],
        ),
    ]
    # Same rounded rating; UG has fewer displayed colors -> tighter -> chosen.
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_none_when_all_soupy():
    """Only returns -1 when the pool genuinely can't form any <=2-color deck."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("Soup A", 83.0, ["G", "B", "U"]),
        _variant("Soup B", 80.0, ["W", "U", "R"]),
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
    from src.advisor.deck_builder import build_variant_greedy

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
    from src.advisor.deck_builder import build_variant_greedy

    pool = _greedy_pool(main_g=7, main_b=7, splash_u=6)
    deck, splash_col = build_variant_greedy(pool, ["B", "G"], mock_metrics)

    assert deck is None


def test_suggest_deck_rejects_pool_with_fewer_than_fifteen_playable_spells(
    mock_metrics, monkeypatch
):
    """The public planning interface returns no recommendations below the guard."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Playable {index}") for index in range(14)]
    _patch_planning_variants(monkeypatch, _planning_two_color_deck("Core"))
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(
        deck_builder,
        "calculate_holistic_score",
        lambda *args: (70.0, "Stable core"),
    )

    assert suggest_deck(pool, mock_metrics, Configuration()) == {}


def test_suggest_deck_keeps_a_non_soupy_option_when_soup_scores_higher(
    mock_metrics, monkeypatch
):
    """The public result always includes a two-color identity when available."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    safe = _planning_two_color_deck("Safe")
    soup = [
        _planning_card("Soup G", "G") | {"count": 14},
        _planning_card("Soup R", "R") | {"count": 13},
        _planning_card("Soup U", "U") | {"count": 13},
    ]
    _patch_planning_variants(monkeypatch, safe, soup=(soup, ["G", "R", "U"]))
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(
        deck_builder,
        "calculate_holistic_score",
        lambda deck, *args: (90.0 if any(c["name"] == "Soup G" for c in deck) else 70.0, "score"),
    )

    result = suggest_deck(pool, mock_metrics, Configuration())

    assert any(len(data["identity_colors"]) <= 2 for data in result.values())


def test_suggest_deck_filters_near_duplicate_public_recommendations(
    mock_metrics, monkeypatch
):
    """Recommendations sharing almost every card do not multiply the result list."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    first = _planning_two_color_deck("First")
    second = _planning_two_color_deck("First")
    _patch_planning_variants(monkeypatch, first, curve=second)
    monkeypatch.setattr(
        deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats()
    )
    monkeypatch.setattr(
        deck_builder, "calculate_holistic_score", lambda *args: (70.0, "score")
    )

    result = suggest_deck(pool, mock_metrics, Configuration())

    assert len(result) == 1



def test_suggest_deck_promotes_nearby_safe_deck_and_preserves_two_color_identity(
    mock_metrics, monkeypatch
):
    """A near-best deck with one incidental splash is publicly Safe and first."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    safe_with_incidental_splash = [
        _planning_card("Safe G", "G") | {"count": 19},
        _planning_card("Safe R", "R") | {"count": 20},
        _planning_card("Safe W", "W") | {"count": 1},
    ]
    soup = [
        _planning_card("Soup G", "G") | {"count": 14},
        _planning_card("Soup R", "R") | {"count": 13},
        _planning_card("Soup U", "U") | {"count": 13},
    ]
    _patch_planning_variants(
        monkeypatch, safe_with_incidental_splash, soup=(soup, ["G", "R", "U"])
    )
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(
        deck_builder,
        "calculate_holistic_score",
        lambda deck, *args: (90.0 if any(c["name"] == "Soup G" for c in deck) else 85.0, "score"),
    )

    label, recommendation = next(iter(suggest_deck(pool, mock_metrics, Configuration()).items()))

    assert "Safe Core" in label
    assert recommendation["identity_colors"] == ["R", "G"]



def test_suggest_deck_exposes_complete_and_incomplete_variants(
    mock_metrics, monkeypatch
):
    """The public mapping retains both classes when fewer than three variants exist."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    complete = _planning_two_color_deck("Complete")
    incomplete = _planning_two_color_deck("Incomplete")
    _patch_planning_variants(monkeypatch, complete, curve=incomplete)
    monkeypatch.setattr(
        deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats()
    )
    monkeypatch.setattr(
        deck_builder,
        "calculate_holistic_score",
        lambda deck, *args: (
            70.0,
            "Incomplete Deck (-20.0)"
            if any(c["name"] == "Incomplete G" for c in deck)
            else "Stable core",
        ),
    )

    results = suggest_deck(pool, mock_metrics, Configuration())

    decks = list(results.values())
    assert any(data["deck_cards"][0]["name"] == "Complete G" for data in decks)
    assert any("Incomplete Deck" in data["breakdown"] for data in decks)


def test_suggest_deck_reports_all_public_result_categories(
    mock_metrics, monkeypatch
):
    """Progress reports status and variant results through the public interface."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    _patch_planning_variants(monkeypatch, _planning_two_color_deck("Core"))
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(deck_builder, "calculate_holistic_score", lambda *args: (70.0, "score"))
    progress = []

    result = suggest_deck(pool, mock_metrics, Configuration(), progress_callback=progress.append)

    assert result
    assert any("status" in message for message in progress)
    assert any("variant_label" in message for message in progress)



def test_suggest_deck_uses_one_planner_owned_cache_for_public_adapter(
    mock_metrics, monkeypatch
):
    """The public adapter retains cache behavior after orchestration moves inside the module."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    _patch_planning_variants(monkeypatch, _planning_two_color_deck("Core"))
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(deck_builder, "calculate_holistic_score", lambda *args: (70.0, "score"))
    suggest_deck(pool, mock_metrics, Configuration())
    messages = []

    suggest_deck(pool, mock_metrics, Configuration(), progress_callback=messages.append)

    assert messages == [{"status": "Loaded optimized decks from cache."}]


def test_clearing_public_planner_cache_recomputes_recommendation(
    mock_metrics, monkeypatch
):
    """Clearing the public cache invalidates the next planning request."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    _patch_planning_variants(monkeypatch, _planning_two_color_deck("Core"))
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(deck_builder, "calculate_holistic_score", lambda *args: (70.0, "score"))
    first_messages = []
    suggest_deck(pool, mock_metrics, Configuration(), progress_callback=first_messages.append)
    deck_builder.clear_deck_cache()
    second_messages = []

    suggest_deck(pool, mock_metrics, Configuration(), progress_callback=second_messages.append)

    assert any("Analyzing" in message.get("status", "") for message in second_messages)
    assert second_messages != [{"status": "Loaded optimized decks from cache."}]


def test_public_suggest_deck_adapter_preserves_keyword_contract(
    mock_metrics, monkeypatch
):
    """The stable planner interface accepts event and progress options by keyword."""
    from src.advisor import deck_builder

    deck_builder.clear_deck_cache()
    pool = [_planning_card(f"Pool {index}") for index in range(15)]
    _patch_planning_variants(monkeypatch, _planning_two_color_deck("Core"))
    monkeypatch.setattr(deck_builder, "simulate_deck", lambda *args, **kwargs: _planning_stats())
    monkeypatch.setattr(deck_builder, "calculate_holistic_score", lambda *args: (70.0, "score"))

    result = suggest_deck(
        pool,
        mock_metrics,
        Configuration(),
        event_type="TradDraft",
        progress_callback=lambda message: None,
        dataset_name="baseline",
    )

    assert result
