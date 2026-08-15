"""
tests/test_recap_actions.py
Tests for the shared post-draft recap computation (src.recap_actions), the
single implementation the desktop bridge (mtga_bridge.recap) and the
pre-convergence screen delegate to — ticket 09 convergence. The behaviors here are the ones the bridge port
(`tests/test_bridge_recap.py`) already pinned, re-expressed against the pure
layer: no viewmodels, raw computed values in a RecapData dataclass.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.recap_actions import (
    RecapData,
    build_recap_data,
    fetch_draft_record,
)


@pytest.fixture
def metrics():
    """Global mean 55.0, std 4.0 — so a 60.0 top-23 average grades S (90/100)."""
    m = MagicMock()
    m.get_metrics.return_value = (55.0, 4.0)
    return m


def _card(name, gihwr=55.0, **kw):
    stats = {"gihwr": gihwr}
    for key in ("alsa", "ata"):
        if key in kw:
            stats[key] = kw.pop(key)
    card = {
        "name": name,
        "types": kw.pop("types", ["Creature"]),
        "rarity": kw.pop("rarity", "common"),
        "deck_colors": {"All Decks": stats},
    }
    card.update(kw)
    return card


def _basic(name="Plains"):
    return {"name": name, "types": ["Land", "Basic"], "deck_colors": {}}


def _pool(count=42, gihwr=55.0, **kw):
    return [_card(f"Card {i}", gihwr, **kw) for i in range(count)]


def _data(pool, metrics=None, draft_id="d1", event_type="PremierDraft") -> RecapData:
    return build_recap_data(pool, metrics, draft_id, event_type)


# --- has_data guard ----------------------------------------------------------


def test_a_pool_under_forty_cards_has_no_data(metrics):
    assert _data(_pool(39), metrics).has_data is False


def test_an_empty_pool_has_no_data(metrics):
    assert _data([], metrics).has_data is False
    assert _data(None, metrics).has_data is False


def test_a_pool_of_only_basics_has_no_data(metrics):
    assert _data([_basic() for _ in range(40)], metrics).has_data is False


def test_exactly_forty_cards_has_data(metrics):
    assert _data(_pool(40), metrics).has_data is True


# --- grade -------------------------------------------------------------------


def test_grade_is_the_top_23_z_score(metrics):
    """23 cards at 60.0 against mean 55.0 / std 4.0: z=1.25, 75+1.25*12 = 90."""
    pool = [_card(f"Great {i}", 60.0) for i in range(23)] + [_basic() for _ in range(17)]

    data = _data(pool, metrics)

    assert data.pool_power == 90.0
    assert data.grade == "S (God Tier)"
    assert data.grade_style == "success"
    assert data.top_23_avg == 60.0
    assert data.format_avg == 55.0


@pytest.mark.parametrize(
    "gihwr,grade,style",
    [
        (60.0, "S (God Tier)", "success"),
        (58.4, "A (Amazing)", "success"),
        (56.7, "B+ (Great)", "info"),
        (55.0, "B (Good)", "info"),
        (53.4, "C (Average)", "warning"),
        (50.0, "D (Below Average)", "danger"),
        (44.0, "F (Trainwreck)", "danger"),
    ],
)
def test_every_grade_band_is_reachable(metrics, gihwr, grade, style):
    pool = [_card(f"Card {i}", gihwr) for i in range(23)] + [_basic() for _ in range(17)]

    data = _data(pool, metrics)

    assert data.grade == grade
    assert data.grade_style == style


def test_pool_power_is_clamped_to_0_100(metrics):
    high = _data(_pool(40, gihwr=99.0), metrics)
    low = _data(_pool(40, gihwr=1.0), metrics)

    assert high.pool_power == 100.0
    assert low.pool_power == 0.0


def test_missing_metrics_fall_back_to_format_defaults():
    data = _data(_pool(40, gihwr=54.5), None)

    assert data.format_avg == 54.5
    assert data.pool_power == 75.0


def test_zero_metrics_fall_back_to_format_defaults(metrics):
    metrics.get_metrics.return_value = (0.0, 0.0)

    data = _data(_pool(40, gihwr=54.5), metrics)

    assert data.format_avg == 54.5
    assert data.pool_power == 75.0


def test_only_the_best_23_cards_set_the_grade(metrics):
    bombs = [_card(f"Bomb {i}", 60.0) for i in range(23)]
    duds = [_card(f"Dud {i}", 30.0) for i in range(20)]

    assert _data(bombs + duds, metrics).top_23_avg == 60.0


# --- steals & reaches --------------------------------------------------------


def test_a_late_pick_of_a_good_card_is_a_steal(metrics):
    """ALSA 3.0 taken at P1P13 in a 14-card pack: +10.0."""
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(12, _card("Massive Steal", 60.0, alsa=3.0))

    data = _data(pool, metrics)

    assert [(s[0], s[1], s[2], s[3], s[4]) for s in data.steals] == [
        ("Massive Steal", 1, 13, 3.0, 10.0)
    ]


def test_an_early_pick_of_a_weak_card_is_a_reach(metrics):
    """ATA 12.0 taken at P1P1, below the 54.0 win-rate bar."""
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(0, _card("Big Reach", 50.0, alsa=1.0, ata=12.0))

    data = _data(pool, metrics)

    assert [(r[0], r[1], r[2], r[3], r[4]) for r in data.reaches] == [
        ("Big Reach", 1, 1, 12.0, 11.0)
    ]


def test_a_late_pick_of_a_weak_card_is_not_a_steal(metrics):
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(12, _card("Wheeled Dud", 50.0, alsa=3.0))

    assert _data(pool, metrics).steals == []


def test_an_early_pick_of_a_strong_card_is_not_a_reach(metrics):
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(0, _card("First Pick Bomb", 60.0, alsa=1.0, ata=12.0))

    assert _data(pool, metrics).reaches == []


def test_steals_and_reaches_are_ranked_by_delta_and_capped_at_six(metrics):
    pool = _pool(45, gihwr=50.0, alsa=1.0, ata=1.0)
    for offset, index in enumerate(range(1, 15)):
        pool[index] = _card(f"Steal {offset}", 60.0, alsa=1.0)

    data = _data(pool, metrics)

    assert len(data.steals) == 6
    deltas = [s[4] for s in data.steals]
    assert deltas == sorted(deltas, reverse=True)


@pytest.mark.parametrize(
    "total,pick",
    [(45, 11), (42, 12), (40, 13)],
)
def test_pack_size_is_inferred_from_the_pool_size(metrics, total, pick):
    pool = _pool(total, gihwr=50.0, alsa=1.0)
    pool[25] = _card("Boundary", 60.0, alsa=1.0)

    steal = _data(pool, metrics).steals[0]

    assert (steal[1], steal[2]) == (2, pick)


def test_basics_do_not_shift_the_pick_numbering(metrics):
    pool = _pool(45, gihwr=50.0, alsa=1.0)
    pool[0] = _basic()
    pool[20] = _card("Late Steal", 60.0, alsa=1.0)

    steal = _data(pool, metrics).steals[0]

    assert (steal[1], steal[2]) == (2, 6)


def test_a_card_with_no_alsa_or_ata_is_neither(metrics):
    pool = _pool(45, gihwr=60.0, alsa=0.0, ata=0.0)

    data = _data(pool, metrics)

    assert data.steals == []
    assert data.reaches == []


# --- archetypes --------------------------------------------------------------


def test_archetypes_are_named_and_ranked_by_win_rate(metrics):
    metrics.get_metrics.side_effect = lambda color, field: {
        "All Decks": (55.0, 4.0),
        "WU": (58.0, 4.0),
    }.get(color, (52.0, 4.0))
    pool = [_card(f"White {i}", 60.0, colors=["W"]) for i in range(20)] + [
        _card(f"Blue {i}", 60.0, colors=["U"]) for i in range(22)
    ]

    data = _data(pool, metrics)

    assert data.archetypes[0] == ("Azorius", 58.0)
    win_rates = [w or 0.0 for _, w in data.archetypes]
    assert win_rates == sorted(win_rates, reverse=True)
    assert len(data.archetypes) <= 3


def test_an_archetype_lane_is_normalized_to_wubrg(metrics):
    with patch("src.recap_actions.identify_top_pairs", return_value=[["U", "W"]]):
        data = _data(_pool(40, gihwr=60.0), metrics)

    assert [name for name, _ in data.archetypes] == ["Azorius"]


def test_an_archetype_with_no_data_carries_zero_win_rate(metrics):
    """A lane at 0.0 means no stats — the adapters render it as 'no data',
    not as a real, terrible win rate."""
    metrics.get_metrics.side_effect = lambda color, field: (
        (55.0, 4.0) if color == "All Decks" else (0.0, 0.0)
    )

    data = _data(_pool(40, gihwr=60.0), metrics)

    assert all(w == 0.0 for _, w in data.archetypes)


# --- card lists --------------------------------------------------------------


def test_best_cards_are_the_top_six_by_win_rate(metrics):
    pool = [_card(f"Card {i}", 50.0 + i) for i in range(42)]

    best = _data(pool, metrics).best_cards

    assert [n for n, _ in best] == [f"Card {i}" for i in range(41, 35, -1)]
    assert best[0] == ("Card 41", 91.0)


def test_staples_are_high_win_rate_commons_and_uncommons(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Common Staple", 58.0, rarity="common"))
    pool.append(_card("Uncommon Staple", 59.0, rarity="uncommon"))
    pool.append(_card("Rare Bomb", 62.0, rarity="rare"))
    pool.append(_card("Weak Common", 56.0, rarity="common"))

    staples = _data(pool, metrics).staples

    assert [n for n, _ in staples] == ["Uncommon Staple", "Common Staple"]


def test_rares_and_mythics_are_listed_separately(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("The Mythic", 62.0, rarity="mythic"))
    pool.append(_card("The Rare", 61.0, rarity="rare"))

    rares = _data(pool, metrics).rares

    assert [n for n, _ in rares] == ["The Mythic", "The Rare"]


def test_rarity_is_matched_case_insensitively(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Shouty Rare", 61.0, rarity="RARE"))

    assert "Shouty Rare" in [n for n, _ in _data(pool, metrics).rares]


def test_non_basic_lands_are_listed_and_basics_are_not(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Dual Land", 60.0, types=["Land"]))
    pool.append(_basic("Snow-Covered Plains"))

    lands = _data(pool, metrics).non_basic_lands

    assert [n for n, _ in lands] == ["Dual Land"]


# --- tribes & roles ----------------------------------------------------------


def test_tribes_need_three_creatures_to_show(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Ninja One", 60.0, subtypes=["Ninja"]))
    pool.append(_card("Ninja Two", 60.0, subtypes=["Ninja"]))
    pool.append(_card("Ninja Three", 60.0, subtypes=["Ninja"]))
    pool.append(_card("Lone Wizard", 60.0, subtypes=["Wizard"]))

    tribes = _data(pool, metrics).tribes

    assert tribes == [("Ninja", 3)]


def test_only_creature_subtypes_count_as_tribes(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Aura One", 60.0, types=["Enchantment"], subtypes=["Aura"]))
    pool.append(_card("Aura Two", 60.0, types=["Enchantment"], subtypes=["Aura"]))
    pool.append(_card("Aura Three", 60.0, types=["Enchantment"], subtypes=["Aura"]))

    assert _data(pool, metrics).tribes == []


def test_roles_are_labelled_from_tag_visuals(metrics):
    pool = _pool(40, gihwr=50.0)
    for i in range(4):
        pool.append(_card(f"Removal {i}", 60.0, tags=["removal"]))

    roles = _data(pool, metrics).roles

    assert roles[0][1] == 4
    assert roles[0][0] != "removal"  # mapped, not the raw tag


def test_an_unmapped_tag_falls_back_to_its_capitalized_name(metrics):
    pool = _pool(40, gihwr=50.0)
    for i in range(3):
        pool.append(_card(f"Mystery {i}", 60.0, tags=["mystery"]))

    roles = _data(pool, metrics).roles

    assert ("Mystery", 3) in roles


def test_roles_are_ranked_and_capped_at_six(metrics):
    pool = _pool(40, gihwr=50.0)
    for i in range(7):
        pool.append(_card(f"Tag{i} A", 60.0, tags=[f"tag{i}"]))
        pool.append(_card(f"Tag{i} B", 60.0, tags=[f"tag{i}"]))

    counts = [c for _, c in _data(pool, metrics).roles]

    assert len(counts) == 6
    assert counts == sorted(counts, reverse=True)


# --- charts ------------------------------------------------------------------


def test_type_counts_exclude_basics_and_cover_every_bucket(metrics):
    pool = _pool(40, gihwr=50.0, types=["Creature"]) + [_basic() for _ in range(5)]

    counts = _data(pool, metrics).type_counts

    assert counts == {
        "Creature": 40,
        "Planeswalker": 0,
        "Battle": 0,
        "Instant": 0,
        "Sorcery": 0,
        "Enchantment": 0,
        "Artifact": 0,
        "Land": 0,
    }


def test_a_multi_type_card_counts_under_each_of_its_types(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Artifact Creature", 60.0, types=["Creature", "Artifact"]))

    counts = _data(pool, metrics).type_counts

    assert counts["Creature"] == 41
    assert counts["Artifact"] == 1


def test_cmc_distribution_has_eight_buckets_and_skips_lands(metrics):
    pool = [_card(f"Two {i}", 55.0, cmc=2) for i in range(40)]
    pool.append(_basic())

    dist = _data(pool, metrics).cmc_distribution

    assert len(dist) == 8
    assert sum(dist) == 40


# --- passthrough fields ------------------------------------------------------


def test_sealed_is_flagged_from_the_event_type(metrics):
    assert _data(_pool(40), metrics, event_type="Sealed").is_sealed is True
    assert _data(_pool(40), metrics, event_type=None).is_sealed is False


def test_draft_id_is_passed_through(metrics):
    assert _data(_pool(40), metrics, draft_id="abc-123").draft_id == "abc-123"
    assert _data(_pool(40), metrics, draft_id=None).draft_id == ""


# --- 17Lands draft record ----------------------------------------------------


def test_a_missing_draft_id_skips_the_network_call():
    with patch("src.seventeenlands.Seventeenlands") as client:
        assert fetch_draft_record("") is None
        assert fetch_draft_record(None) is None

    client.assert_not_called()


def test_a_found_record_carries_wins_losses_and_url():
    with patch("src.seventeenlands.Seventeenlands") as client:
        client.return_value.get_draft_record.return_value = {
            "wins": 7,
            "losses": 2,
            "url": "https://www.17lands.com/draft/abc",
        }

        record = fetch_draft_record("abc-123")

    assert record == (7, 2, "https://www.17lands.com/draft/abc")


def test_an_untracked_draft_reports_none():
    with patch("src.seventeenlands.Seventeenlands") as client:
        client.return_value.get_draft_record.return_value = {"wins": None}

        assert fetch_draft_record("abc-123") is None
