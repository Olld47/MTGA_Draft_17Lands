"""
tests/test_snapshot_actions.py
Tests for the shared draft-state computation (src.snapshot_actions), the
single implementation the desktop bridge (mtga_bridge.snapshot) and the
pre-convergence controller/dashboard delegate to — ticket 09 convergence. The behaviors here are
the ones the bridge port (`tests/test_bridge_snapshot.py`) already pinned,
re-expressed against the pure layer: no scanner, explicit parameters.
"""

from unittest.mock import patch

import pytest

from src import constants
from src.snapshot_actions import (
    build_filter_label,
    compute_signals,
    evaluate_pack,
    expected_pool_size,
    is_draft_complete,
    is_draft_event,
    merge_taken_cards,
    resolve_colors,
)


class _FakeMetrics:
    def __init__(self, baseline=55.0, std=4.0):
        self.baseline = baseline
        self.std = std

    def get_metrics(self, color, field):
        return (self.baseline, self.std)


class _FakeSetData:
    def __init__(self, cards):
        self._cards = {c["id"]: c for c in cards}

    def get_data_by_id(self, ids):
        return [self._cards[i] for i in ids if i in self._cards]


def _card(cid, name, gihwr, ata, colors):
    return {
        "id": cid,
        "name": name,
        "colors": list(colors),
        "deck_colors": {"All Decks": {"gihwr": gihwr, "ata": ata}},
    }


def _history(*entries):
    return [dict(e) for e in entries]


# --- signals -----------------------------------------------------------------


def test_signals_start_at_zero_for_every_color():
    scores = compute_signals(_FakeMetrics(), [], _FakeSetData([]))

    assert set(scores.values()) == {0.0}
    assert set(scores) == set(constants.CARD_COLORS)


def test_signals_score_a_good_card_seen_late(metrics=None):
    # Baseline 55.0; a 68.0 GIHWR red card at ata 1.5 seen at pick 7:
    # lateness 5.5 x diff 13.0 -> 71.5 to Red.
    set_data = _FakeSetData([_card("102", "Red Bomb", 68.0, 1.5, ["R"])])
    history = _history({"Pack": 1, "Pick": 7, "Cards": ["102"]})

    scores = compute_signals(_FakeMetrics(), history, set_data)

    assert scores["R"] == pytest.approx(71.5)
    assert scores["G"] == 0.0


def test_signals_skip_pack_two():
    set_data = _FakeSetData([_card("102", "Red Bomb", 68.0, 1.5, ["R"])])
    history = _history({"Pack": 2, "Pick": 7, "Cards": ["102"]})

    scores = compute_signals(_FakeMetrics(), history, set_data)

    assert set(scores.values()) == {0.0}


def test_signals_accumulate_across_packs():
    set_data = _FakeSetData([_card("102", "Red Bomb", 68.0, 1.5, ["R"])])
    history = _history(
        {"Pack": 1, "Pick": 7, "Cards": ["102"]},
        {"Pack": 3, "Pick": 7, "Cards": ["102"]},
    )

    scores = compute_signals(_FakeMetrics(), history, set_data)

    assert scores["R"] == pytest.approx(71.5 * 2)


def test_signals_ignore_a_card_seen_before_its_average_pick():
    """Lateness is pick - ata; a card taken earlier than average has passed
    nobody, so it scores nothing."""
    set_data = _FakeSetData([_card("102", "Red Bomb", 68.0, 5.0, ["R"])])
    history = _history({"Pack": 1, "Pick": 3, "Cards": ["102"]})

    scores = compute_signals(_FakeMetrics(), history, set_data)

    assert scores["R"] == 0.0


# --- advisor evaluation ------------------------------------------------------


def test_evaluate_pack_runs_the_advisor_with_the_given_signals():
    taken = [{"name": "A"}]
    pack = [{"name": "B"}]
    metrics = _FakeMetrics()
    with patch("src.snapshot_actions.DraftAdvisor") as advisor_cls:
        advisor_cls.return_value.evaluate_pack.return_value = ["rec1"]
        recs = evaluate_pack(metrics, taken, {"R": 2.0}, pack, 5, 1)

    advisor_cls.assert_called_once_with(metrics, taken, signals={"R": 2.0})
    advisor_cls.return_value.evaluate_pack.assert_called_once_with(pack, 5, current_pack=1)
    assert recs == ["rec1"]


# --- color resolution --------------------------------------------------------


def test_resolve_colors_passes_through_filter_options():
    with patch("src.snapshot_actions.filter_options", return_value=["W", "U"]):
        assert resolve_colors([], "Auto", object(), object()) == ["W", "U"]


# --- draft completion gates --------------------------------------------------


def test_is_draft_event_recognizes_draft_types_only():
    assert is_draft_event(constants.LIMITED_TYPE_STRING_DRAFT_PREMIER) is True
    assert is_draft_event(constants.LIMITED_TYPE_STRING_DRAFT_QUICK) is True
    assert is_draft_event(constants.LIMITED_TYPE_STRING_DRAFT_BOT) is True
    assert is_draft_event(constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO) is True
    assert is_draft_event(constants.LIMITED_TYPE_STRING_SEALED) is False
    assert is_draft_event("") is False
    assert is_draft_event(None) is False


def test_expected_pool_size_defaults_to_42():
    assert expected_pool_size([]) == 42


def test_expected_pool_size_scales_with_the_largest_pack():
    # Pick 1 of a 13-card pack: 1 + 13 - 1 = 13 -> 39 total.
    assert expected_pool_size(_history({"Pack": 1, "Pick": 1, "Cards": list(range(13))})) == 39
    # 14-card packs keep the flat 42 default.
    assert expected_pool_size(_history({"Pack": 1, "Pick": 1, "Cards": list(range(14))})) == 42
    # Oversized packs scale linearly.
    assert expected_pool_size(_history({"Pack": 1, "Pick": 1, "Cards": list(range(15))})) == 45


def test_is_draft_complete_requires_the_full_pool():
    assert is_draft_complete("PremierDraft", 41, 42) is False
    assert is_draft_complete("PremierDraft", 42, 42) is True


def test_is_draft_complete_sealed_reaches_forty():
    assert is_draft_complete("Sealed", 39, 42) is False
    assert is_draft_complete("Sealed", 40, 42) is True


def test_is_draft_complete_ignores_unknown_event_types():
    assert is_draft_complete("SomeEvent", 42, 42) is False
    assert is_draft_complete(None, 42, 42) is False


# --- taken-card merging ------------------------------------------------------


def test_merge_taken_cards_dedups_by_name_keeping_first_row():
    a1 = {"name": "Card A", "cmc": 1}
    a2 = {"name": "Card A", "cmc": 2}  # later duplicate row, must be dropped
    b = {"name": "Card B", "cmc": 3}

    merged, counts = merge_taken_cards([a1, a2, b])

    assert merged == [a1, b]
    assert counts == {"Card A": 2, "Card B": 1}


def test_merge_taken_cards_handles_an_empty_pool():
    assert merge_taken_cards([]) == ([], {})
    assert merge_taken_cards(None) == ([], {})


# --- filter label ------------------------------------------------------------


def test_build_filter_label_auto_form_combines_name_and_rate():
    with patch("src.snapshot_actions.filter_display_name", return_value="All Decks"), patch(
        "src.snapshot_actions.filter_win_rate", return_value=54.0
    ):
        label = build_filter_label("All Decks", "names", {}, is_auto=True)

    assert label == "Auto (All Decks 54.0%)"


def test_build_filter_label_without_auto_omits_the_prefix():
    with patch("src.snapshot_actions.filter_display_name", return_value="Azorius"), patch(
        "src.snapshot_actions.filter_win_rate", return_value=56.3
    ):
        label = build_filter_label("WU", "names", {}, is_auto=False)

    assert label == "Azorius (56.3%)"


def test_build_filter_label_omits_a_missing_rate():
    with patch("src.snapshot_actions.filter_display_name", return_value="Azorius"), patch(
        "src.snapshot_actions.filter_win_rate", return_value=None
    ):
        assert build_filter_label("WU", "names", {}, is_auto=False) == "Azorius"
        assert build_filter_label("WU", "names", {}, is_auto=True) == "Auto (Azorius)"
