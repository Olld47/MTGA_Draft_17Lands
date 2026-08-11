import pytest
from unittest.mock import MagicMock
from src.advisor.engine import DraftAdvisor
from src.advisor.schema import Recommendation


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking format_texture for VOR (Value Over Replacement) tests
    metrics.format_texture = {
        "R": {"2-drop": 1, "removal": 10},  # Extremely scarce red 2-drops
        "G": {"2-drop": 10, "removal": 1},  # Extremely scarce green removal
    }
    # get_metrics returns (mean, std)
    metrics.get_metrics.return_value = (55.0, 4.0)
    return metrics


def test_identify_main_colors(mock_metrics):
    pool = [
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 60.0}}},
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 60.0}}},
        {"colors": ["U"], "deck_colors": {"All Decks": {"gihwr": 55.0}}},
        {"colors": ["R"], "deck_colors": {"All Decks": {"gihwr": 40.0}}},
    ]
    advisor = DraftAdvisor(mock_metrics, pool)

    # Because White has high WR and multiple cards, it should be top
    assert "W" in advisor.main_colors


def test_analyze_pool(mock_metrics):
    # Establish a definitive "White Lane" by padding the pool > 15 cards
    pool = [
        {
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 60.0}},
        }
        for _ in range(15)
    ]

    # Add a black removal spell (not a bomb, just utility)
    pool.append(
        {
            "colors": ["B"],
            "tags": ["removal"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
    )

    # Add a green fixing bomb. Because we are definitively in White, this will trigger the splash logic.
    pool.append(
        {
            "colors": ["G"],
            "tags": ["fixing_ramp"],
            "cmc": 1,
            "deck_colors": {"All Decks": {"gihwr": 65.0}},
        }
    )

    advisor = DraftAdvisor(mock_metrics, pool)

    assert advisor.pool_metrics["early_plays"] == 15
    assert advisor.pool_metrics["hard_removal_count"] == 1
    assert advisor.pool_metrics["fixing_count"] == 1

    # 65.0 > 55.0 + (1.5 * 4.0) = 61.0, so 'G' triggers as a premium splash target
    assert "G" in advisor.pool_metrics["splash_targets"]


def test_calculate_castability_v5(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.pool_metrics = {"fixing_count": 0}

    # On lane card
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["W"]}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 1.0

    # Off lane card, double pip (uncastable)
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["B"], "mana_cost": "{B}{B}"}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 0.01

    # Splashable bomb
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["R"], "mana_cost": "{R}"}, pack=2, pick=1, z_score=2.0
    )

    # Without fixing in the pool, it's heavily penalized even if it's a bomb
    assert mult == 0.05


def test_check_relative_wheel(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    # Should wheel if ALSA is greater than the current pick
    mult, reason, pct = advisor._check_relative_wheel(
        {"deck_colors": {"All Decks": {"alsa": 10.0}}}, pick=2, rank_in_pack=5
    )

    assert pct > 0.0
    assert mult == 0.8
    assert "Wheels" in reason


def test_evaluate_pack_elite_detection(mock_metrics):
    # Establish a baseline pool
    pool = [
        {
            "name": "Grizzly Bears",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
    ] * 10
    advisor = DraftAdvisor(mock_metrics, pool)

    # Construct a pack with a massive outlier (Bomb) and filler
    pack = [
        {
            "name": "Bomb",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 75.0, "iwd": 5.0, "alsa": 2.0}},
        },
        {
            "name": "Filler1",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
        {
            "name": "Filler2",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
        {
            "name": "Filler3",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
    ]

    recs = advisor.evaluate_pack(pack, current_pick=1)

    assert len(recs) == 4
    assert recs[0].card_name == "Bomb"
    # Elite designation triggers because Z-score > 1.5, IWD > 4.5, and it is on-color
    assert recs[0].is_elite is True


def test_evaluate_value_over_replacement(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["R"]
    advisor.global_mean = 55.0
    advisor.global_std = 4.0

    # A playable red 2-drop. Because we defined Red 2-drops as incredibly scarce
    # in the mock_metrics fixture above, this card should trigger a VOR bonus!
    pack = [
        {
            "name": "Scarce Red 2-Drop",
            "colors": ["R"],
            "types": ["Creature"],
            "cmc": 2,
            "tags": ["evasion"],
            "deck_colors": {"All Decks": {"gihwr": 54.0}},
        }
    ]

    recs = advisor.evaluate_pack(pack, current_pick=1)

    assert len(recs) == 1
    assert any("High VOR: Scarce R 2-Drops" in reason for reason in recs[0].reasoning)


def test_composition_bonus_heuristics(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])

    # Setup pool metrics to trigger specific heuristic thresholds
    advisor.pool_metrics = {
        "heavy_drops": 4,
        "creature_count": 5,
        "artifacts": 4,
        "graveyard_enablers": 3,
        "counters_enablers": 3,
        "fixing_count": 0,
        "off_color_playables": 2,
        "splash_targets": ["U"],
        "hard_removal_count": 1,
        "early_plays": 2,
    }
    advisor.TOTAL_PICKS = 45
    advisor.pool = [1] * 20  # Simulate mid-draft (Pick 20)

    # 1. Heavy Drops Penalty
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 6, "types": ["Creature"]}, pack=2
    )
    assert mult == 0.7
    assert "Curve Too Heavy" in reason

    # 2. Creature Quota Bonus
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 3, "types": ["Creature"]}, pack=2
    )
    assert mult == 1.25
    assert "Critical: Needs Creatures" in reason

    # 3. Artifact Synergy
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 3, "tags": ["synergy_artifacts"]}, pack=2
    )
    assert mult == 1.2
    assert "Artifact Synergy" in reason

    # 4. Fixing Hunger (Because off_color_playables > fixing_count)
    mult, reason = advisor._calculate_composition_bonus({"types": ["Land"]}, pack=2)
    assert mult == 1.4
    assert "Critical: Needs Fixing" in reason

    # 5. Removal Hunger
    mult, reason = advisor._calculate_composition_bonus({"tags": ["removal"]}, pack=2)
    assert mult == 1.3
    assert "Critical: Needs Removal" in reason


# ---------------------------------------------------------------------------
# Coverage additions (candidate B): missing data, pack-3 behavior, castability
# edge paths, composition heuristics, and scoring baselines.
# ---------------------------------------------------------------------------


def test_evaluate_pack_empty_pack_returns_empty_list(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    assert advisor.evaluate_pack([], current_pick=1) == []


def test_evaluate_pack_missing_deck_colors_no_crash(mock_metrics):
    # A card with no deck_colors at all must not crash evaluate_pack;
    # it scores a flat 0 and reports base_win_rate 0.0.
    advisor = DraftAdvisor(mock_metrics, [])
    recs = advisor.evaluate_pack(
        [{"name": "Mystery", "colors": ["W"]}], current_pick=1
    )
    assert len(recs) == 1
    assert recs[0].card_name == "Mystery"
    assert recs[0].base_win_rate == 0.0
    assert recs[0].contextual_score == 0.0


def test_evaluate_pack_z_score_baseline(mock_metrics):
    # Two cards at 55 and 59 WR in the same pack: mean=57, pstdev=2,
    # so their Z-scores are exactly -1.0 and +1.0.
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {
            "name": "A",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        },
        {
            "name": "B",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 59.0}},
        },
    ]
    recs = advisor.evaluate_pack(pack, current_pick=1, current_pack=1)
    assert {r.card_name: r.z_score for r in recs} == {"B": 1.0, "A": -1.0}


def test_evaluate_pack_pack3_needs_playables_bonus(mock_metrics):
    # In pack 3 with fewer than 20 on-color cards drafted, on-lane cards get
    # a 1.3x base multiplier instead of the usual 1.1x.
    pool = (
        [
            {
                "name": "White Bear",
                "colors": ["W"],
                "types": ["Creature"],
                "cmc": 2,
                "deck_colors": {"All Decks": {"gihwr": 60.0}},
            }
        ]
        * 8
        + [
            {
                "name": "Blue Bear",
                "colors": ["U"],
                "types": ["Creature"],
                "cmc": 2,
                "deck_colors": {"All Decks": {"gihwr": 58.0}},
            }
        ]
        * 6
    )
    advisor = DraftAdvisor(mock_metrics, pool)
    assert len(advisor.main_colors) >= 2  # precondition for the 1.3x branch
    card = {
        "name": "White Bear",
        "colors": ["W"],
        "types": ["Creature"],
        "cmc": 2,
        "deck_colors": {"All Decks": {"gihwr": 60.0}},
    }
    score_p2 = advisor.evaluate_pack([card], current_pick=10, current_pack=2)[0]
    score_p3 = advisor.evaluate_pack([card], current_pick=10, current_pack=3)[0]
    # contextual_score is rounded to 1 decimal, so allow for rounding drift.
    assert score_p3.contextual_score == pytest.approx(
        score_p2.contextual_score * (1.3 / 1.1), rel=1e-2
    )


def test_calculate_castability_off_color_gold(mock_metrics):
    # Pack-1 double-pip card outside the lane triggers the "Off-Color Gold" reason.
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    mult, reason = advisor._calculate_castability_v5(
        {"colors": ["R", "G"], "mana_cost": "{R}{G}"}, pack=1, pick=1, z_score=0.0
    )
    assert mult == 0.8
    assert reason == "Off-Color Gold"


def test_calculate_castability_uncastable_double_pip(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.pool_metrics = {"fixing_count": 0}
    mult, reason = advisor._calculate_castability_v5(
        {"colors": ["B"], "mana_cost": "{B}{B}"}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 0.01
    assert reason == "Uncastable (Double Pip)"


def test_calculate_castability_bomb_splash(mock_metrics):
    # A high-Z off-lane single-pip card becomes a Bomb Splash once fixing exists.
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.pool_metrics = {"fixing_count": 3}
    mult, reason = advisor._calculate_castability_v5(
        {"colors": ["R"], "mana_cost": "{R}"}, pack=2, pick=1, z_score=1.5
    )
    assert mult == 0.45
    assert reason == "Bomb Splash"


def test_calculate_castability_splashable(mock_metrics):
    # Single off-lane pip with dedicated fixing sources splashes for 0.3.
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.fixing_map = {"W": 0, "U": 0, "B": 0, "R": 1, "G": 0}
    mult, reason = advisor._calculate_castability_v5(
        {"colors": ["R"], "mana_cost": "{R}"}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 0.3
    assert reason == "Splashable"


def test_composition_removal_saturated(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.pool_metrics = {
        "early_plays": 0,
        "hard_removal_count": 7,
        "fixing_count": 0,
        "splash_targets": [],
        "off_color_playables": 0,
        "creature_count": 5,
        "heavy_drops": 0,
        "artifacts": 0,
        "graveyard_enablers": 0,
        "counters_enablers": 0,
    }
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 3, "tags": ["removal"]}, pack=2
    )
    assert mult == 0.8
    assert reason == "Removal Saturated"


def test_composition_enables_bomb_splash(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.pool_metrics = {
        "early_plays": 0,
        "hard_removal_count": 0,
        "fixing_count": 0,
        "splash_targets": ["U"],
        "off_color_playables": 0,
        "creature_count": 5,
        "heavy_drops": 0,
        "artifacts": 0,
        "graveyard_enablers": 0,
        "counters_enablers": 0,
    }
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 0, "colors": ["U"], "types": ["Land"]}, pack=2
    )
    assert mult == 1.3
    assert reason == "Enables Bomb Splash"


def test_evaluate_pack_basic_land_skip(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {
            "name": "Plains",
            "types": ["Basic", "Land"],
            "colors": ["W"],
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        },
        {
            "name": "Creature",
            "types": ["Creature"],
            "colors": ["W"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 60.0}},
        },
    ]
    recs = advisor.evaluate_pack(pack, current_pick=1, current_pack=1)
    plains = next(r for r in recs if r.card_name == "Plains")
    assert plains.contextual_score == 0.0
    assert plains.reasoning == ["Basic Land (Skip)"]


def test_calculate_weighted_score_signal_tie_breaker(mock_metrics):
    # Signal strength > 10 across the card's colors boosts the base score 1.05x.
    card = {"colors": ["W", "U"], "deck_colors": {"All Decks": {"gihwr": 60.0}}}
    no_signal = DraftAdvisor(mock_metrics, [])
    with_signal = DraftAdvisor(mock_metrics, [], signals={"W": 6.0, "U": 6.0})
    base = no_signal._calculate_weighted_score(card, pick_number=10)
    boosted = with_signal._calculate_weighted_score(card, pick_number=10)
    assert boosted == pytest.approx(base * 1.05)
