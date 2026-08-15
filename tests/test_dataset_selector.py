"""
tests/test_dataset_selector.py
Dataset-selection extraction tests (issue 11 Phase 2) — pins the behavior of
src/dataset_selector.py: the local-file catalog scan and the event-type/group
ranking that ArenaScanner used to inline. Scanner-facing proxies keep the
retrieve_* contract; this module is the extraction's own test surface.
"""

import pytest

import src.constants as constants
from src.dataset_selector import (
    DatasetSelector,
    _dataset_event_type_rank,
    _best_dataset_by_rank,
)
from src.utils import LocalSetInfo


def _info(
    set_name="MSH",
    event_type="QuickDraft",
    user_group="All",
    end_date="2026-08-06",
    collection_date="2026-08-06",
    location="/all.json",
):
    return LocalSetInfo(
        set_name=set_name,
        event_type=event_type,
        user_group=user_group,
        start_date="2026-08-01",
        end_date=end_date,
        game_count=100,
        file_location=location,
        collection_date=collection_date,
    )


# --- Event-type rank (moved verbatim from src.log_scanner) -------------------

def test_dataset_event_type_rank_exact_section():
    """An exact event-name section match ranks highest (rank 0)."""
    assert _dataset_event_type_rank("QuickDraft", "QuickDraft_MSH_20260806") == 0
    assert _dataset_event_type_rank("PremierDraft", "PremierDraft_MSH_20260806") == 0


def test_dataset_event_type_rank_containment_fallback():
    """Pick-two variants still resolve via containment (rank 1)."""
    assert _dataset_event_type_rank("QuickDraft", "PickTwoQuickDraft_MSH_20260806") == 1
    assert (
        _dataset_event_type_rank("QuickDraft", "PhantomPickTwoQuickDraft_MSH_20260806")
        == 1
    )


def test_dataset_event_type_rank_mismatch():
    """An unrelated dataset type is rejected outright (None)."""
    assert _dataset_event_type_rank("PremierDraft", "QuickDraft_MSH_20260806") is None


def test_dataset_event_type_rank_unknown_event_matches_all():
    """An unparseable/empty event name matches every dataset type — the caller
    falls back to any source for the set."""
    assert _dataset_event_type_rank("QuickDraft", "") == 0


# --- retrieve_data_sources: local-file catalog scan --------------------------

def test_retrieve_data_sources_builds_label_to_path_map(monkeypatch):
    from src import dataset_selector

    monkeypatch.setattr(
        dataset_selector,
        "retrieve_local_set_list",
        lambda: (
            [
                _info(event_type="PremierDraft", location="/premier.json"),
                _info(event_type="QuickDraft", location="/quick.json"),
            ],
            [],
        ),
    )
    selector = DatasetSelector()

    catalog = selector.retrieve_data_sources()

    assert catalog == {
        "[MSH] PremierDraft (All)": "/premier.json",
        "[MSH] QuickDraft (All)": "/quick.json",
    }


def test_retrieve_data_sources_year_prefix_uses_six_char_bracket(monkeypatch):
    """Y-prefixed set codes (e.g. Y26Q3) get a 6-char bracket, not the bare code."""
    from src import dataset_selector

    monkeypatch.setattr(
        dataset_selector,
        "retrieve_local_set_list",
        lambda: ([_info(set_name="Y26Q3", location="/y26.json")], []),
    )
    catalog = DatasetSelector().retrieve_data_sources()

    assert catalog == {"[Y26Q3] QuickDraft (All)": "/y26.json"}


def test_retrieve_data_sources_empty_returns_sentinel(monkeypatch):
    from src import dataset_selector

    monkeypatch.setattr(
        dataset_selector, "retrieve_local_set_list", lambda: ([], [])
    )
    assert DatasetSelector().retrieve_data_sources() == constants.DATA_SOURCES_NONE


def test_retrieve_data_sources_draft_type_reorders_collection_tie(monkeypatch):
    """An active draft_type reorders the catalog on collection-date ties.

    Preserved verbatim from the pre-extraction code: the event-type sort uses
    reverse=True, so on a collection-date tie the NON-matching event type ends
    up first (a quirk, not a preference — kept byte-for-byte). The assertion
    pins that draft_type actually drives ordering, which is why the scan takes
    it as a parameter instead of being pure."""
    from src import dataset_selector

    monkeypatch.setattr(
        dataset_selector,
        "retrieve_local_set_list",
        lambda: (
            [
                _info(event_type="QuickDraft", location="/quick.json"),
                _info(event_type="PremierDraft", location="/premier.json"),
            ],
            [],
        ),
    )
    catalog = DatasetSelector().retrieve_data_sources(
        draft_type=constants.LIMITED_TYPE_DRAFT_QUICK
    )

    labels = list(catalog)
    # Insertion order was [Quick, Premier]; the draft_type sort flipped it.
    assert labels[0] == "[MSH] PremierDraft (All)"
    assert labels[1] == "[MSH] QuickDraft (All)"


# --- select_best_dataset: pure ranking over a catalog ------------------------

def test_select_best_dataset_prefers_exact_type_then_all_group():
    """QuickDraft event → the QuickDraft dataset, and "All" over "Top"."""
    catalog = {
        "[MSH] QuickDraft (Top)": "/top.json",
        "[MSH] QuickDraft (All)": "/all.json",
        "[MSH] PickTwoQuickDraft (All)": "/picktwo.json",
        "[MSH] PremierDraft (All)": "/premier.json",
    }
    assert DatasetSelector().select_best_dataset(
        catalog, "MSH", "QuickDraft_MSH_20260806"
    ) == "/all.json"


def test_select_best_dataset_pick_two_event_resolves_to_quick_draft():
    """A PickTwoQuickDraft event has no exact dataset, so containment picks the
    QuickDraft source over an unrelated PremierDraft, preferring "All"."""
    catalog = {
        "[MSH] QuickDraft (Top)": "/top.json",
        "[MSH] QuickDraft (All)": "/all.json",
        "[MSH] PremierDraft (All)": "/premier.json",
    }
    assert DatasetSelector().select_best_dataset(
        catalog, "MSH", "PickTwoQuickDraft_MSH_20260806"
    ) == "/all.json"


def test_select_best_dataset_unknown_event_falls_back_to_any_source():
    """An event type the set has no dataset for still resolves to a set source
    (preferring "All") instead of returning nothing."""
    catalog = {
        "[MSH] QuickDraft (Top)": "/top.json",
        "[MSH] QuickDraft (All)": "/all.json",
    }
    assert DatasetSelector().select_best_dataset(
        catalog, "MSH", "MysteryFormat_MSH_20260806"
    ) == "/all.json"


def test_select_best_dataset_no_source_for_set_returns_empty():
    catalog = {"[OTJ] PremierDraft (All)": "/otj.json"}
    assert DatasetSelector().select_best_dataset(
        catalog, "MSH", "QuickDraft_MSH_20260806"
    ) == ""


def test_best_dataset_by_rank_all_beats_top():
    """The broad "All" sample outranks "Top" within the same event rank."""
    sources = {
        "[MSH] QuickDraft (Top)": "/top.json",
        "[MSH] QuickDraft (All)": "/all.json",
    }
    best = _best_dataset_by_rank(sources, "[MSH]", lambda _label: 1)
    assert best == ((1, 0, "[MSH] QuickDraft (All)"), "/all.json")
