"""
tests/test_scanner_state.py
State machine tests for issue 11 — pins the explicit scanner state model in
src/scanner_state.py: every docs/02 §7 state has a ScannerPhase symbol, every
transition is a single TRANSITIONS table row, derive_scanner_phase is the one
place authoritative scanner fields map onto a phase, and each draft_type
protocol family scans a fixed ordered set of events.
"""

import pytest

import src.constants as constants
from src.scanner_state import (
    ScannerPhase,
    ScannerEvent,
    TRANSITIONS,
    FAMILY_SCANS,
    derive_scanner_phase,
)


# --- Diagram states have explicit symbols ------------------------------------

def test_every_diagram_state_has_a_phase_symbol():
    """docs/02 §7: Idle / Drafting{WaitingForPack → PackReview → PickMade} /
    Sealed{SealedStudio} / Done — each has an explicit ScannerPhase member."""
    assert ScannerPhase.IDLE.value == "Idle"
    assert ScannerPhase.DRAFTING_WAITING_FOR_PACK.value == "Drafting.WaitingForPack"
    assert ScannerPhase.DRAFTING_PACK_REVIEW.value == "Drafting.PackReview"
    assert ScannerPhase.DRAFTING_PICK_MADE.value == "Drafting.PickMade"
    assert ScannerPhase.SEALED_STUDIO.value == "Sealed.SealedStudio"
    assert ScannerPhase.DONE.value == "Done"


def test_no_game_phase():
    """Game is not a scanner state: it appears in no diagram edge, no event
    type, no scan family. AGENTS.md prose is being corrected to match."""
    assert "GAME" not in ScannerPhase.__members__


def test_event_catalog():
    """Every log signal the scanner dispatches on has a ScannerEvent symbol,
    including the bot terminal DeckSelect surfaced out of the pack payload."""
    assert {e.value for e in ScannerEvent} == {
        "EventJoin",
        "PackNotify",
        "PackBot",
        "PickHuman",
        "PickV1",
        "PickBot",
        "CardPool",
        "DeckSelectCompleted",
    }


# --- derive_scanner_phase: fields → phase, single source ---------------------

def test_derive_idle_when_unknown_and_no_recap_payload():
    assert (
        derive_scanner_phase(draft_type=constants.LIMITED_TYPE_UNKNOWN)
        == ScannerPhase.IDLE
    )


def test_derive_done_when_unknown_with_recap_payload():
    """_mark_draft_complete keeps draft_label/draft_sets/taken_cards for the
    recap — UNKNOWN + any payload is the Done phase, not cold Idle."""
    assert (
        derive_scanner_phase(
            draft_type=constants.LIMITED_TYPE_UNKNOWN, draft_label="PremierDraft"
        )
        == ScannerPhase.DONE
    )
    assert (
        derive_scanner_phase(
            draft_type=constants.LIMITED_TYPE_UNKNOWN, taken_cards=["1", "2"]
        )
        == ScannerPhase.DONE
    )
    assert (
        derive_scanner_phase(
            draft_type=constants.LIMITED_TYPE_UNKNOWN, draft_sets=["OTJ"]
        )
        == ScannerPhase.DONE
    )


def test_derive_sealed_studio_for_sealed_types():
    assert (
        derive_scanner_phase(draft_type=constants.LIMITED_TYPE_SEALED)
        == ScannerPhase.SEALED_STUDIO
    )
    assert (
        derive_scanner_phase(draft_type=constants.LIMITED_TYPE_SEALED_TRADITIONAL)
        == ScannerPhase.SEALED_STUDIO
    )


def test_derive_drafting_waiting_before_first_pack():
    assert (
        derive_scanner_phase(
            draft_type=constants.LIMITED_TYPE_DRAFT_PREMIER_V2, current_pick=0
        )
        == ScannerPhase.DRAFTING_WAITING_FOR_PACK
    )


def test_derive_drafting_review_when_offer_ahead_of_picks():
    """A pack offer at pick 3 with only pick 2 made → reviewing the open pack."""
    assert (
        derive_scanner_phase(
            draft_type=constants.LIMITED_TYPE_DRAFT_PREMIER_V2,
            current_pick=3,
            current_picked_pick=2,
        )
        == ScannerPhase.DRAFTING_PACK_REVIEW
    )


def test_derive_drafting_pick_made_when_offer_equals_last_pick():
    assert (
        derive_scanner_phase(
            draft_type=constants.LIMITED_TYPE_DRAFT_PREMIER_V2,
            current_pick=2,
            current_picked_pick=2,
        )
        == ScannerPhase.DRAFTING_PICK_MADE
    )


# --- TRANSITIONS: single-point transition table ------------------------------

def test_transition_table_has_no_duplicate_keys():
    assert len(TRANSITIONS) == len({key for key in TRANSITIONS})


def test_transition_handlers_exist_on_scanner():
    """Every table row names a real ArenaScanner method — a renamed handler
    fails here instead of silently at dispatch time."""
    from src.log_scanner import ArenaScanner

    for transition in TRANSITIONS.values():
        assert callable(getattr(ArenaScanner, transition.handler)), transition


def test_diagram_edges_are_table_rows():
    """The docs/02 §7 arrows map 1:1 onto TRANSITIONS rows."""
    def target(source, event):
        return TRANSITIONS[(source, event)].target

    # Idle → Drafting / Sealed
    assert (
        target(ScannerPhase.IDLE, ScannerEvent.EVENT_JOIN)
        == ScannerPhase.DRAFTING_WAITING_FOR_PACK
    )
    assert (
        target(ScannerPhase.IDLE, ScannerEvent.CARD_POOL)
        == ScannerPhase.SEALED_STUDIO
    )
    # WaitingForPack → PackReview
    assert (
        target(ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.PACK_NOTIFY)
        == ScannerPhase.DRAFTING_PACK_REVIEW
    )
    # PackReview → PickMade
    assert (
        target(ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.PICK_HUMAN)
        == ScannerPhase.DRAFTING_PICK_MADE
    )
    # PickMade → PackReview (next pack)
    assert (
        target(ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.PACK_NOTIFY)
        == ScannerPhase.DRAFTING_PACK_REVIEW
    )
    # PickMade → Done (terminal DeckSelect)
    assert (
        target(ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.DECK_SELECT_COMPLETED)
        == ScannerPhase.DONE
    )
    # Done → next draft
    assert (
        target(ScannerPhase.DONE, ScannerEvent.EVENT_JOIN)
        == ScannerPhase.DRAFTING_WAITING_FOR_PACK
    )


def test_recovery_rows_treat_unknown_events_as_drafting():
    """IDLE/DONE recovery: a stray pack/pick/pool event infers the draft type
    and lands in the drafting sub-phase the event implies."""
    assert (
        TRANSITIONS[(ScannerPhase.IDLE, ScannerEvent.PACK_NOTIFY)].target
        == ScannerPhase.DRAFTING_PACK_REVIEW
    )
    assert (
        TRANSITIONS[(ScannerPhase.IDLE, ScannerEvent.PICK_BOT)].target
        == ScannerPhase.DRAFTING_PICK_MADE
    )
    assert (
        TRANSITIONS[(ScannerPhase.DONE, ScannerEvent.PACK_BOT)].target
        == ScannerPhase.DRAFTING_PACK_REVIEW
    )


def test_pack_and_pick_events_legal_in_all_drafting_sub_phases():
    """Log order is not guaranteed (resume mid-pack, out-of-order replay) — a
    pack/pick in any drafting sub-phase is registered, never a false warning."""
    for phase in (
        ScannerPhase.DRAFTING_WAITING_FOR_PACK,
        ScannerPhase.DRAFTING_PACK_REVIEW,
        ScannerPhase.DRAFTING_PICK_MADE,
    ):
        assert (phase, ScannerEvent.PACK_NOTIFY) in TRANSITIONS
        assert (phase, ScannerEvent.PACK_BOT) in TRANSITIONS
        assert (phase, ScannerEvent.PICK_HUMAN) in TRANSITIONS
        assert (phase, ScannerEvent.PICK_V1) in TRANSITIONS
        assert (phase, ScannerEvent.PICK_BOT) in TRANSITIONS


def test_sealed_events_are_illegal_in_sealed_studio():
    """A pack/pick signal while sealed has no registered transition — the
    dispatch must fail loud (logger.warning) instead of silently applying it."""
    for event in (
        ScannerEvent.PACK_NOTIFY,
        ScannerEvent.PACK_BOT,
        ScannerEvent.PICK_HUMAN,
        ScannerEvent.PICK_V1,
        ScannerEvent.PICK_BOT,
        ScannerEvent.DECK_SELECT_COMPLETED,
    ):
        assert (ScannerPhase.SEALED_STUDIO, event) not in TRANSITIONS


def test_deck_select_without_draft_is_illegal():
    """A terminal DeckSelect with no draft registered (cold log replay) is an
    illegal transition — warning, never a silent state change."""
    assert (ScannerPhase.IDLE, ScannerEvent.DECK_SELECT_COMPLETED) not in TRANSITIONS
    assert (ScannerPhase.DONE, ScannerEvent.DECK_SELECT_COMPLETED) not in TRANSITIONS


# --- FAMILY_SCANS: draft_type protocol → ordered event scan set ---------------

HUMAN_FAMILY = (
    (ScannerEvent.PICK_HUMAN, "_search_pick_human"),
    (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
    (ScannerEvent.CARD_POOL, "_search_card_pool"),
)
BOT_FAMILY = (
    (ScannerEvent.PICK_BOT, "_search_pick_bot"),
    (ScannerEvent.PACK_BOT, "_search_pack_bot"),
    (ScannerEvent.CARD_POOL, "_search_card_pool"),
)
SEALED_FAMILY = ((ScannerEvent.CARD_POOL, "_search_card_pool"),)


def test_family_scan_order_preserved():
    """The pre-refactor per-draft_type scan order (and which events each
    protocol family scans) must survive the table extraction verbatim."""
    assert FAMILY_SCANS[constants.LIMITED_TYPE_DRAFT_PREMIER_V1] == (
        (ScannerEvent.PICK_V1, "_search_pick_v1"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    )
    for t in (
        constants.LIMITED_TYPE_DRAFT_PREMIER_V2,
        constants.LIMITED_TYPE_DRAFT_TRADITIONAL,
        constants.LIMITED_TYPE_DRAFT_PICK_TWO,
        constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
        constants.LIMITED_TYPE_DRAFT_CONTENDER,
    ):
        assert FAMILY_SCANS[t] == HUMAN_FAMILY
    for t in (
        constants.LIMITED_TYPE_DRAFT_QUICK,
        constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
    ):
        assert FAMILY_SCANS[t] == BOT_FAMILY
    for t in (
        constants.LIMITED_TYPE_SEALED,
        constants.LIMITED_TYPE_SEALED_TRADITIONAL,
    ):
        assert FAMILY_SCANS[t] == SEALED_FAMILY


def test_every_draft_type_has_a_family():
    for value in range(1, 11):
        assert value in FAMILY_SCANS, f"no scan family for LIMITED_TYPE {value}"
