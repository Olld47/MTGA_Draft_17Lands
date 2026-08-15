"""
src/scanner_state.py

Explicit state machine model for ArenaScanner (architecture-review issue 11).

docs/02-log-parsing-rules.md §7 draws a state diagram (Idle → Drafting
{WaitingForPack → PackReview → PickMade} / Sealed{SealedStudio} / Done) that
previously had no code counterpart: transitions were scattered across the
if/elif dispatch in __perform_search_logic and the bool-return conventions of
the _search_* handlers. This module is that counterpart:

- ScannerPhase: one symbol per diagram state (no Game — it is not in the
  diagram and the scanner tracks no game events).
- ScannerEvent: one symbol per log signal the scanner dispatches on.
- derive_scanner_phase(): the single place authoritative scanner fields map
  onto a phase. Fields stay the source of truth; the phase is a view.
- TRANSITIONS: the single-point (phase, event) → (target, handler) table.
  Dispatch consults it; combos with no row fail loud in the scanner
  (logger.warning) instead of silently applying a return-value convention.
- FAMILY_SCANS: draft_type protocol family → ordered set of events scanned
  each pass (preserves the pre-refactor scan order verbatim).

This module is internal to the scanner: it imports only src.constants, so it
passes the 02 layering lint (no tkinter / ttkbootstrap / src.ui).
"""

from dataclasses import dataclass
from enum import Enum

import src.constants as constants


class ScannerPhase(Enum):
    """One explicit symbol per state of the docs/02 §7 state diagram."""

    IDLE = "Idle"
    DRAFTING_WAITING_FOR_PACK = "Drafting.WaitingForPack"
    DRAFTING_PACK_REVIEW = "Drafting.PackReview"
    DRAFTING_PICK_MADE = "Drafting.PickMade"
    SEALED_STUDIO = "Sealed.SealedStudio"
    DONE = "Done"


class ScannerEvent(Enum):
    """One symbol per log signal the scanner dispatches on."""

    EVENT_JOIN = "EventJoin"  # draft_start_search / __check_event
    PACK_NOTIFY = "PackNotify"  # Draft.Notify
    PACK_BOT = "PackBot"  # BotDraft DraftPack (DraftStatus PickNext)
    PICK_HUMAN = "PickHuman"  # Event_PlayerDraftMakePick
    PICK_V1 = "PickV1"  # Draft.MakeHumanDraftPick (legacy protocol)
    PICK_BOT = "PickBot"  # BotDraft_DraftPick
    CARD_POOL = "CardPool"  # Sealed pool / deck-recovery dump
    DECK_SELECT_COMPLETED = "DeckSelectCompleted"  # terminal bot DeckSelect


@dataclass(frozen=True)
class Transition:
    """One registered (phase, event) → (target phase, handler) transition."""

    source: ScannerPhase
    event: ScannerEvent
    target: ScannerPhase
    handler: str  # ArenaScanner method name; resolved at dispatch time


# --- State derivation ---------------------------------------------------------
# Fields are the single source of truth. This is the ONLY place authoritative
# scanner state maps onto a phase — no duplicate derivation anywhere else.

def derive_scanner_phase(
    *,
    draft_type: int,
    draft_label: str = "",
    draft_sets=None,
    taken_cards=None,
    current_pick: int = 0,
    current_picked_pick: int = 0,
) -> ScannerPhase:
    """Map authoritative scanner fields onto a ScannerPhase.

    UNKNOWN with a preserved recap payload (draft_label/draft_sets/taken_cards
    kept by _mark_draft_complete) is Done, not cold Idle. Drafting sub-phases
    come from the pack/pick watermarks: no pack yet → WaitingForPack; the
    current offer equals the last made pick → PickMade; an offer ahead of the
    picks → PackReview.
    """
    if draft_type == constants.LIMITED_TYPE_UNKNOWN:
        has_recap = bool(draft_label or draft_sets or taken_cards)
        return ScannerPhase.DONE if has_recap else ScannerPhase.IDLE
    if draft_type in (
        constants.LIMITED_TYPE_SEALED,
        constants.LIMITED_TYPE_SEALED_TRADITIONAL,
    ):
        return ScannerPhase.SEALED_STUDIO
    if current_pick == 0:
        return ScannerPhase.DRAFTING_WAITING_FOR_PACK
    if current_pick == current_picked_pick:
        return ScannerPhase.DRAFTING_PICK_MADE
    return ScannerPhase.DRAFTING_PACK_REVIEW


# --- Transition table ---------------------------------------------------------
# Single-point declaration of every legal (phase, event) combination. The
# dispatch in log_scanner.py looks here; anything not listed fails loud.
#
# EVENT_JOIN rows document the Idle/Done → Drafting edge: the transition is
# applied inside draft_start_search/__check_event via derive_scanner_phase
# (the target depends on whether the joined event is a draft or sealed).

def _transition(source, event, target, handler):
    return (source, event), Transition(source, event, target, handler)


TRANSITIONS: dict = dict(
    [
        # Idle → first draft / sealed (recovery infers the type)
        _transition(
            ScannerPhase.IDLE, ScannerEvent.EVENT_JOIN,
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, "draft_start_search",
        ),
        _transition(
            ScannerPhase.IDLE, ScannerEvent.PACK_NOTIFY,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_notify",
        ),
        _transition(
            ScannerPhase.IDLE, ScannerEvent.PACK_BOT,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.IDLE, ScannerEvent.PICK_HUMAN,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_human",
        ),
        _transition(
            ScannerPhase.IDLE, ScannerEvent.PICK_V1,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_v1",
        ),
        _transition(
            ScannerPhase.IDLE, ScannerEvent.PICK_BOT,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_bot",
        ),
        _transition(
            ScannerPhase.IDLE, ScannerEvent.CARD_POOL,
            ScannerPhase.SEALED_STUDIO, "_search_card_pool",
        ),
        # Done (recap retained) → next draft
        _transition(
            ScannerPhase.DONE, ScannerEvent.EVENT_JOIN,
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, "draft_start_search",
        ),
        _transition(
            ScannerPhase.DONE, ScannerEvent.PACK_NOTIFY,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_notify",
        ),
        _transition(
            ScannerPhase.DONE, ScannerEvent.PACK_BOT,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.DONE, ScannerEvent.PICK_HUMAN,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_human",
        ),
        _transition(
            ScannerPhase.DONE, ScannerEvent.PICK_V1,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_v1",
        ),
        _transition(
            ScannerPhase.DONE, ScannerEvent.PICK_BOT,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_bot",
        ),
        _transition(
            ScannerPhase.DONE, ScannerEvent.CARD_POOL,
            ScannerPhase.SEALED_STUDIO, "_search_card_pool",
        ),
        # Drafting sub-phases: pack/pick events are legal in every sub-phase
        # (log order is not guaranteed — resume mid-pack, out-of-order replay).
        # Repeated/duplicate signals land on the same phase (dedupe is inside
        # the handlers and unchanged).
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.PACK_NOTIFY,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_notify",
        ),
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.PACK_BOT,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.PICK_HUMAN,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_human",
        ),
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.PICK_V1,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_v1",
        ),
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.PICK_BOT,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, ScannerEvent.CARD_POOL,
            ScannerPhase.DRAFTING_WAITING_FOR_PACK, "_search_card_pool",
        ),
        _transition(
            ScannerPhase.DRAFTING_WAITING_FOR_PACK,
            ScannerEvent.DECK_SELECT_COMPLETED,
            ScannerPhase.DONE, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.PACK_NOTIFY,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_notify",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.PACK_BOT,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.PICK_HUMAN,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_human",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.PICK_V1,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_v1",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.PICK_BOT,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.CARD_POOL,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_card_pool",
        ),
        _transition(
            ScannerPhase.DRAFTING_PACK_REVIEW, ScannerEvent.DECK_SELECT_COMPLETED,
            ScannerPhase.DONE, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.PACK_NOTIFY,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_notify",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.PACK_BOT,
            ScannerPhase.DRAFTING_PACK_REVIEW, "_search_pack_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.PICK_HUMAN,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_human",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.PICK_V1,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_v1",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.PICK_BOT,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_pick_bot",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.CARD_POOL,
            ScannerPhase.DRAFTING_PICK_MADE, "_search_card_pool",
        ),
        _transition(
            ScannerPhase.DRAFTING_PICK_MADE, ScannerEvent.DECK_SELECT_COMPLETED,
            ScannerPhase.DONE, "_search_pack_bot",
        ),
        # Sealed: only pool events (and a new sealed EventJoin, applied via
        # draft_start_search). Pack/pick signals here are illegal → fail loud.
        _transition(
            ScannerPhase.SEALED_STUDIO, ScannerEvent.EVENT_JOIN,
            ScannerPhase.SEALED_STUDIO, "draft_start_search",
        ),
        _transition(
            ScannerPhase.SEALED_STUDIO, ScannerEvent.CARD_POOL,
            ScannerPhase.SEALED_STUDIO, "_search_card_pool",
        ),
    ]
)


# --- Protocol families --------------------------------------------------------
# draft_type selects which events each pass scans, and in which order. This
# preserves the pre-refactor dispatch order exactly (V1 scans its legacy pick
# first; human/bot families scan pick before pack; sealed scans pool only).

def _family(*events):
    return tuple(events)


FAMILY_SCANS: dict = {
    constants.LIMITED_TYPE_DRAFT_PREMIER_V1: _family(
        (ScannerEvent.PICK_V1, "_search_pick_v1"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_PREMIER_V2: _family(
        (ScannerEvent.PICK_HUMAN, "_search_pick_human"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_TRADITIONAL: _family(
        (ScannerEvent.PICK_HUMAN, "_search_pick_human"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_PICK_TWO: _family(
        (ScannerEvent.PICK_HUMAN, "_search_pick_human"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD: _family(
        (ScannerEvent.PICK_HUMAN, "_search_pick_human"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_CONTENDER: _family(
        (ScannerEvent.PICK_HUMAN, "_search_pick_human"),
        (ScannerEvent.PACK_NOTIFY, "_search_pack_notify"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_QUICK: _family(
        (ScannerEvent.PICK_BOT, "_search_pick_bot"),
        (ScannerEvent.PACK_BOT, "_search_pack_bot"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK: _family(
        (ScannerEvent.PICK_BOT, "_search_pick_bot"),
        (ScannerEvent.PACK_BOT, "_search_pack_bot"),
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_SEALED: _family(
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
    constants.LIMITED_TYPE_SEALED_TRADITIONAL: _family(
        (ScannerEvent.CARD_POOL, "_search_card_pool"),
    ),
}
