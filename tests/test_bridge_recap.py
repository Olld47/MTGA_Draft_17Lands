"""
tests/test_bridge_recap.py
Bridge-layer tests for the post-draft recap port (mtga_bridge.recap).
`build_recap` is pure — it takes the four values snapshot_recap_inputs returns
and needs no scanner — so these exercise it directly against hand-built pools.
The tkinter screen it replaces is covered by tests/test_dashboard_recap.py, but
that coverage did not carry over when the logic moved into the bridge.
No pytauri, no tkinter.
"""

import os
import sys
from unittest.mock import MagicMock, patch

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

from src import constants

from mtga_bridge.recap import build_recap, fetch_draft_record


# --- Fixtures ----------------------------------------------------------------


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


# --- has_data guard ----------------------------------------------------------


def test_a_pool_under_forty_cards_has_no_recap(metrics):
    """The recap describes a finished draft; a live one has nothing to grade."""
    assert build_recap(_pool(39), metrics, "d1", "PremierDraft").has_data is False


def test_an_empty_pool_has_no_recap(metrics):
    assert build_recap([], metrics, "d1", "PremierDraft").has_data is False
    assert build_recap(None, metrics, "d1", "PremierDraft").has_data is False


def test_a_pool_of_only_basics_has_no_recap(metrics):
    """Forty Plains clears the length check but leaves nothing to average."""
    recap = build_recap([_basic() for _ in range(40)], metrics, "d1", "PremierDraft")
    assert recap.has_data is False


def test_exactly_forty_cards_is_enough(metrics):
    assert build_recap(_pool(40), metrics, "d1", "PremierDraft").has_data is True


# --- grade -------------------------------------------------------------------


def test_grade_is_the_top_23_z_score(metrics):
    """23 cards at 60.0 against mean 55.0 / std 4.0: z=1.25, 75+1.25*12 = 90."""
    pool = [_card(f"Great {i}", 60.0) for i in range(23)]
    pool += [_basic() for _ in range(17)]

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert recap.pool_power == 90
    assert recap.grade == "S (God Tier)"
    assert recap.grade_style == "success"
    assert recap.top_23_avg == 60.0
    assert recap.format_avg == 55.0


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

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert recap.grade == grade
    assert recap.grade_style == style


def test_pool_power_is_clamped_to_0_100(metrics):
    """Without the clamp an absurd pool would render a >100 progress bar."""
    high = build_recap(_pool(40, gihwr=99.0), metrics, "d1", "PremierDraft")
    low = build_recap(_pool(40, gihwr=1.0), metrics, "d1", "PremierDraft")

    assert high.pool_power == 100
    assert low.pool_power == 0


def test_missing_metrics_fall_back_to_format_defaults():
    """A set with no 17Lands data yet still grades, against 54.5 / 3.5."""
    recap = build_recap(_pool(40, gihwr=54.5), None, "d1", "PremierDraft")

    assert recap.format_avg == 54.5
    assert recap.pool_power == 75


def test_zero_metrics_fall_back_to_format_defaults(metrics):
    """get_metrics returns (0, 0) for a field it has no data for; dividing by a
    zero std would raise."""
    metrics.get_metrics.return_value = (0.0, 0.0)

    recap = build_recap(_pool(40, gihwr=54.5), metrics, "d1", "PremierDraft")

    assert recap.format_avg == 54.5
    assert recap.pool_power == 75


def test_only_the_best_23_cards_set_the_grade(metrics):
    """23 bombs plus 20 duds must grade the same as the 23 bombs alone."""
    bombs = [_card(f"Bomb {i}", 60.0) for i in range(23)]
    duds = [_card(f"Dud {i}", 30.0) for i in range(20)]

    assert build_recap(bombs + duds, metrics, "d1", "X").top_23_avg == 60.0


# --- steals & reaches --------------------------------------------------------


def test_a_late_pick_of_a_good_card_is_a_steal(metrics):
    """ALSA 3.0 taken at P1P13 in a 14-card pack: +10.0."""
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(12, _card("Massive Steal", 60.0, alsa=3.0))

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert [s.name for s in recap.steals] == ["Massive Steal"]
    steal = recap.steals[0]
    assert (steal.pack, steal.pick) == (1, 13)
    assert steal.reference == 3.0
    assert steal.delta == 10.0


def test_an_early_pick_of_a_weak_card_is_a_reach(metrics):
    """ATA 12.0 taken at P1P1, below the 54.0 win-rate bar."""
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(0, _card("Big Reach", 50.0, alsa=1.0, ata=12.0))

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert [r.name for r in recap.reaches] == ["Big Reach"]
    reach = recap.reaches[0]
    assert (reach.pack, reach.pick) == (1, 1)
    assert reach.reference == 12.0
    assert reach.delta == 11.0


def test_a_late_pick_of_a_weak_card_is_not_a_steal(metrics):
    """The 55.0 GIHWR floor is what separates a steal from a card that wheeled
    because nobody wanted it."""
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(12, _card("Wheeled Dud", 50.0, alsa=3.0))

    assert build_recap(pool, metrics, "d1", "PremierDraft").steals == []


def test_an_early_pick_of_a_strong_card_is_not_a_reach(metrics):
    """A P1P1 bomb has a high ATA delta but a win rate that justifies it."""
    pool = _pool(41, gihwr=50.0, alsa=1.0, ata=1.0)
    pool.insert(0, _card("First Pick Bomb", 60.0, alsa=1.0, ata=12.0))

    assert build_recap(pool, metrics, "d1", "PremierDraft").reaches == []


def test_steals_and_reaches_are_ranked_by_delta_and_capped_at_six(metrics):
    pool = _pool(45, gihwr=50.0, alsa=1.0, ata=1.0)
    # Later index → later pick → bigger delta against the same ALSA.
    for offset, index in enumerate(range(1, 15)):
        pool[index] = _card(f"Steal {offset}", 60.0, alsa=1.0)

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert len(recap.steals) == 6
    deltas = [s.delta for s in recap.steals]
    assert deltas == sorted(deltas, reverse=True)


@pytest.mark.parametrize(
    "total,pick",
    [(45, 11), (42, 12), (40, 13)],
)
def test_pack_size_is_inferred_from_the_pool_size(metrics, total, pick):
    """Pack size is 15 / 14 / total//3 by pool size, so the same index reports a
    different pick number in each — 25 is pack 2 in all three."""
    pool = _pool(total, gihwr=50.0, alsa=1.0)
    pool[25] = _card("Boundary", 60.0, alsa=1.0)

    steal = build_recap(pool, metrics, "d1", "PremierDraft").steals[0]

    assert (steal.pack, steal.pick) == (2, pick)


def test_basics_do_not_shift_the_pick_numbering(metrics):
    """Basics are skipped, not removed — index, and therefore pack/pick, is
    still counted over the whole pool."""
    pool = _pool(45, gihwr=50.0, alsa=1.0)
    pool[0] = _basic()
    pool[20] = _card("Late Steal", 60.0, alsa=1.0)

    steal = build_recap(pool, metrics, "d1", "PremierDraft").steals[0]

    assert (steal.pack, steal.pick) == (2, 6)


def test_a_card_with_no_alsa_or_ata_is_neither(metrics):
    """A zero stat means 'no 17Lands data', not 'picked first'."""
    pool = _pool(45, gihwr=60.0, alsa=0.0, ata=0.0)

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert recap.steals == []
    assert recap.reaches == []


# --- archetypes --------------------------------------------------------------


def test_archetypes_are_named_and_ranked_by_win_rate(metrics):
    """identify_top_pairs returns colour pairs; each is resolved to its guild
    name and sorted by the lane's win rate."""
    metrics.get_metrics.side_effect = lambda color, field: {
        "All Decks": (55.0, 4.0),
        "WU": (58.0, 4.0),
    }.get(color, (52.0, 4.0))
    pool = [
        _card(f"White {i}", 60.0, colors=["W"]) for i in range(20)
    ] + [_card(f"Blue {i}", 60.0, colors=["U"]) for i in range(22)]

    recap = build_recap(pool, metrics, "d1", "PremierDraft")

    assert recap.archetypes[0].name == "Azorius"
    assert recap.archetypes[0].win_rate == 58.0
    win_rates = [a.win_rate or 0.0 for a in recap.archetypes]
    assert win_rates == sorted(win_rates, reverse=True)
    assert len(recap.archetypes) <= 3


def test_an_archetype_lane_is_normalized_to_wubrg(metrics):
    """identify_top_pairs can hand back ('U', 'W'); COLOR_NAMES_DICT is keyed
    WUBRG, so an unsorted lane would fall through to the raw string."""
    metrics.get_metrics.return_value = (55.0, 4.0)
    with patch(
        "mtga_bridge.recap.identify_top_pairs", return_value=[["U", "W"]]
    ):
        recap = build_recap(_pool(40, gihwr=60.0), metrics, "d1", "PremierDraft")

    assert [a.name for a in recap.archetypes] == ["Azorius"]


def test_an_archetype_with_no_data_carries_no_win_rate(metrics):
    """A lane at 0.0 means the set has no stats for it — rendering '0.0%' would
    read as a real, terrible win rate."""
    metrics.get_metrics.side_effect = lambda color, field: (
        (55.0, 4.0) if color == "All Decks" else (0.0, 0.0)
    )

    recap = build_recap(_pool(40, gihwr=60.0), metrics, "d1", "PremierDraft")

    assert all(a.win_rate is None for a in recap.archetypes)


# --- card lists --------------------------------------------------------------


def test_best_cards_are_the_top_six_by_win_rate(metrics):
    pool = [_card(f"Card {i}", 50.0 + i) for i in range(42)]

    best = build_recap(pool, metrics, "d1", "PremierDraft").best_cards

    assert [c.name for c in best] == [f"Card {i}" for i in range(41, 35, -1)]
    assert best[0].win_rate == 91.0


def test_staples_are_high_win_rate_commons_and_uncommons(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Common Staple", 58.0, rarity="common"))
    pool.append(_card("Uncommon Staple", 59.0, rarity="uncommon"))
    pool.append(_card("Rare Bomb", 62.0, rarity="rare"))
    pool.append(_card("Weak Common", 56.0, rarity="common"))

    staples = build_recap(pool, metrics, "d1", "PremierDraft").staples

    assert [c.name for c in staples] == ["Uncommon Staple", "Common Staple"]


def test_rares_and_mythics_are_listed_separately(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("The Mythic", 62.0, rarity="mythic"))
    pool.append(_card("The Rare", 61.0, rarity="rare"))

    rares = build_recap(pool, metrics, "d1", "PremierDraft").rares

    assert [c.name for c in rares] == ["The Mythic", "The Rare"]


def test_rarity_is_matched_case_insensitively(metrics):
    """Scryfall and 17Lands do not agree on casing."""
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Shouty Rare", 61.0, rarity="Rare"))

    assert "Shouty Rare" in [c.name for c in build_recap(pool, metrics, "d", "X").rares]


def test_non_basic_lands_are_listed_and_basics_are_not(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Dual Land", 56.0, types=["Land"]))
    pool.append(_basic("Island"))
    pool.append({"name": "Wastes", "types": ["Land", "Basic"], "deck_colors": {}})

    lands = build_recap(pool, metrics, "d1", "PremierDraft").non_basic_lands

    assert [c.name for c in lands] == ["Dual Land"]


def test_a_snow_covered_basic_is_still_a_basic(metrics):
    """Snow basics carry no 'Basic' type in some datasets; BASIC_LANDS is what
    catches them."""
    assert "Snow-Covered Island" in constants.BASIC_LANDS
    pool = _pool(40, gihwr=50.0)
    pool.append(
        {"name": "Snow-Covered Island", "types": ["Land"], "deck_colors": {}}
    )

    lands = build_recap(pool, metrics, "d1", "PremierDraft").non_basic_lands

    assert lands == []


# --- tribes & roles ----------------------------------------------------------


def test_tribes_need_three_creatures_to_show(metrics):
    pool = _pool(40, gihwr=50.0)
    pool += [_card(f"Ninja {i}", 55.0, subtypes=["Ninja"]) for i in range(3)]
    pool += [_card(f"Wizard {i}", 55.0, subtypes=["Wizard"]) for i in range(2)]

    tribes = build_recap(pool, metrics, "d1", "PremierDraft").tribes

    assert [(t.label, t.count) for t in tribes] == [("Ninja", 3)]


def test_only_creature_subtypes_count_as_tribes(metrics):
    """An Aura's 'Aura' subtype is not a tribe."""
    pool = _pool(40, gihwr=50.0)
    pool += [
        _card(f"Aura {i}", 55.0, types=["Enchantment"], subtypes=["Aura"])
        for i in range(4)
    ]

    assert build_recap(pool, metrics, "d1", "PremierDraft").tribes == []


def test_roles_are_labelled_from_tag_visuals(metrics):
    pool = _pool(40, gihwr=50.0)
    pool += [_card(f"Kill {i}", 55.0, tags=["removal"]) for i in range(4)]

    roles = build_recap(pool, metrics, "d1", "PremierDraft").roles

    assert roles[0].label == constants.TAG_VISUALS["removal"]
    assert roles[0].count == 4


def test_an_unmapped_tag_falls_back_to_its_capitalized_name(metrics):
    pool = _pool(40, gihwr=50.0)
    pool += [_card(f"Odd {i}", 55.0, tags=["mystery"]) for i in range(3)]

    roles = build_recap(pool, metrics, "d1", "PremierDraft").roles

    assert ("Mystery", 3) in [(r.label, r.count) for r in roles]


def test_roles_are_ranked_and_capped_at_six(metrics):
    pool = _pool(40, gihwr=50.0)
    for n, tag in enumerate(
        ["removal", "evasion", "lifegain", "hate", "protection", "fixing", "combat_trick"]
    ):
        pool += [_card(f"{tag} {i}", 55.0, tags=[tag]) for i in range(n + 1)]

    roles = build_recap(pool, metrics, "d1", "PremierDraft").roles

    assert len(roles) == 6
    counts = [r.count for r in roles]
    assert counts == sorted(counts, reverse=True)


# --- charts ------------------------------------------------------------------


def test_type_counts_exclude_basics_and_cover_every_bucket(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Bolt", 55.0, types=["Instant"]))
    pool.append(_card("Idol", 55.0, types=["Artifact"]))
    pool += [_basic() for _ in range(3)]

    counts = build_recap(pool, metrics, "d1", "PremierDraft").type_counts

    assert counts["Creature"] == 40
    assert counts["Instant"] == 1
    assert counts["Artifact"] == 1
    assert counts["Land"] == 0
    assert set(counts) == {
        "Creature",
        "Planeswalker",
        "Battle",
        "Instant",
        "Sorcery",
        "Enchantment",
        "Artifact",
        "Land",
    }


def test_a_multi_type_card_counts_under_each_of_its_types(metrics):
    pool = _pool(40, gihwr=50.0)
    pool.append(_card("Creature Land", 55.0, types=["Artifact", "Creature"]))

    counts = build_recap(pool, metrics, "d1", "PremierDraft").type_counts

    assert counts["Artifact"] == 1
    assert counts["Creature"] == 41


def test_cmc_distribution_has_eight_buckets_and_skips_lands(metrics):
    pool = [_card(f"Two {i}", 55.0, cmc=2) for i in range(40)]
    pool.append(_card("Dual Land", 55.0, cmc=0, types=["Land"]))

    dist = build_recap(pool, metrics, "d1", "PremierDraft").cmc_distribution

    assert len(dist) == 8
    assert dist[2] == 40
    assert sum(dist) == 40


# --- passthrough fields ------------------------------------------------------


def test_sealed_is_flagged_from_the_event_type(metrics):
    """The page relabels its steals column for Sealed, where there is no pack
    order to have been late in."""
    assert build_recap(_pool(40), metrics, "d1", "SealedEvent").is_sealed is True
    assert build_recap(_pool(40), metrics, "d1", "PremierDraft").is_sealed is False
    assert build_recap(_pool(40), metrics, "d1", None).is_sealed is False


def test_draft_id_is_passed_through_for_the_record_lookup(metrics):
    """RecapPage only calls get_draft_record when draftId is non-empty."""
    assert build_recap(_pool(40), metrics, "abc-123", "X").draft_id == "abc-123"
    assert build_recap(_pool(40), metrics, None, "X").draft_id == ""


def test_the_recap_serializes_as_camel_case(metrics):
    """Every IPC payload ships aliases; a snake_case key here is the v0.6
    blank-window bug."""
    dumped = build_recap(_pool(40), metrics, "d1", "PremierDraft").model_dump()

    assert "poolPower" in dumped
    assert "nonBasicLands" in dumped
    assert not [k for k in dumped if "_" in k]


# --- 17Lands draft record ----------------------------------------------------


def test_a_missing_draft_id_skips_the_network_call():
    with patch("src.seventeenlands.Seventeenlands") as client:
        record = fetch_draft_record("")

    assert record.found is False
    client.assert_not_called()


def test_a_found_record_carries_the_wins_losses_and_url():
    with patch("src.seventeenlands.Seventeenlands") as client:
        client.return_value.get_draft_record.return_value = {
            "wins": 7,
            "losses": 2,
            "url": "https://www.17lands.com/draft/abc",
        }
        record = fetch_draft_record("abc-123")

    assert (record.found, record.wins, record.losses) == (True, 7, 2)
    assert record.url == "https://www.17lands.com/draft/abc"


def test_an_untracked_draft_reports_not_found():
    """17Lands returns a payload without 'wins' for a draft it never saw."""
    with patch("src.seventeenlands.Seventeenlands") as client:
        client.return_value.get_draft_record.return_value = {"wins": None}
        assert fetch_draft_record("abc-123").found is False

        client.return_value.get_draft_record.return_value = None
        assert fetch_draft_record("abc-123").found is False
