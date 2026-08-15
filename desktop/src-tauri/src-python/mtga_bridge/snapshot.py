"""
mtga_bridge.snapshot
Draft-state adapter for the desktop bridge. Snapshots scanner state under its
lock, delegates the signal/advisor/filter math to the shared
src.snapshot_actions (the single implementation both this bridge and the
legacy tkinter controller/dashboard consume — ticket 09 convergence), and
serializes everything into IPC view-models.

This module deliberately avoids importing pytauri so it can be unit-tested
from the root poetry environment.
"""

import logging
import os
from typing import Dict, List, Optional

from src import constants
from src.card_data import CardData
from src.advisor.schema import Recommendation
from src.card_logic import deck_filter_stats, get_deck_metrics
from src.snapshot_actions import (
    build_filter_label,
    compute_signals as _compute_signals,
    expected_pool_size,
    evaluate_pack,
    is_draft_complete,
    merge_taken_cards,
    resolve_colors,
)

from mtga_bridge.deck_view import hover_share_vm
from mtga_bridge.viewmodels import (
    CardStatsVM,
    CardVM,
    DraftStateVM,
    PoolSummaryVM,
    RecommendationVM,
    SignalsVM,
    TakenCardsVM,
)

logger = logging.getLogger(__name__)

_ROUND_FIELDS = {
    constants.DATA_FIELD_GIHWR: 1,
    constants.DATA_FIELD_OHWR: 1,
    constants.DATA_FIELD_GPWR: 1,
    constants.DATA_FIELD_ALSA: 1,
    constants.DATA_FIELD_ATA: 1,
    constants.DATA_FIELD_IWD: 1,
}

# Type-count priority mirrors src/ui/dashboard.py's POOL BALANCE pie: a card
# falls into the first matching type, and basics are excluded.
_TYPE_COUNT_ORDER = [
    "Creature",
    "Planeswalker",
    "Battle",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
]


def _stat(stats: dict, field: str) -> Optional[float]:
    value = stats.get(field)
    if value in (None, ""):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    digits = _ROUND_FIELDS.get(field)
    return round(value, digits) if digits is not None else value


def card_stats_vm(card: CardData, active_filter: str) -> CardStatsVM:
    stats = deck_filter_stats(card, active_filter)
    gih = _stat(stats, constants.DATA_FIELD_GIH)
    ngp = _stat(stats, constants.DATA_FIELD_NGP)
    return CardStatsVM(
        gihwr=_stat(stats, constants.DATA_FIELD_GIHWR),
        ohwr=_stat(stats, constants.DATA_FIELD_OHWR),
        gpwr=_stat(stats, constants.DATA_FIELD_GPWR),
        alsa=_stat(stats, constants.DATA_FIELD_ALSA),
        ata=_stat(stats, constants.DATA_FIELD_ATA),
        iwd=_stat(stats, constants.DATA_FIELD_IWD),
        gih=int(gih) if gih is not None else None,
        ngp=int(ngp) if ngp is not None else None,
    )


def recommendation_vm(rec: Recommendation) -> RecommendationVM:
    return RecommendationVM(**rec.model_dump())


def _first_tier_rating(card_name: str, tier_data: dict) -> Optional[str]:
    """Returns the rating from the first loaded tier list containing this card."""
    if not tier_data:
        return None
    for tier_obj in tier_data.values():
        ratings = getattr(tier_obj, "ratings", None)
        if ratings and card_name in ratings:
            return ratings[card_name].rating
    return None


def card_to_vm(
    card: CardData,
    active_filter: str,
    rec_map: Optional[Dict[str, Recommendation]] = None,
    picked_names: Optional[set] = None,
    tier_data: Optional[dict] = None,
) -> CardVM:
    name = card.get(constants.DATA_FIELD_NAME, "Unknown")
    rec = rec_map.get(name) if rec_map else None

    image = card.get(constants.DATA_SECTION_IMAGES, []) or []
    if isinstance(image, dict):
        image = [v for v in image.values() if v]

    try:
        cmc = float(card.get(constants.DATA_FIELD_CMC, 0) or 0)
    except (TypeError, ValueError):
        cmc = 0.0

    return CardVM(
        name=name,
        mana_cost=card.get(constants.DATA_FIELD_MANA_COST, "") or "",
        cmc=cmc,
        colors=list(card.get(constants.DATA_FIELD_COLORS, []) or []),
        types=list(card.get(constants.DATA_FIELD_TYPES, []) or []),
        rarity=card.get(constants.DATA_FIELD_RARITY, "") or "",
        image=[u for u in image if u],
        count=int(card.get(constants.DATA_FIELD_COUNT, 1) or 1),
        stats=card_stats_vm(card, active_filter),
        recommendation=recommendation_vm(rec) if rec else None,
        is_picked=bool(picked_names and name in picked_names),
        returnable_at=list(card.get("returnable_at", []) or []),
        tier=_first_tier_rating(name, tier_data or {}),
        deck_colors=hover_share_vm(card),
    )


def pool_summary_vm(taken_cards: List[CardData]) -> PoolSummaryVM:
    metrics = get_deck_metrics(taken_cards)
    pips: Dict[str, int] = {c: 0 for c in constants.CARD_COLORS}
    type_counts: Dict[str, int] = {t: 0 for t in _TYPE_COUNT_ORDER}
    for card in taken_cards:
        for color in card.get(constants.DATA_FIELD_COLORS, []) or []:
            if color in pips:
                pips[color] += 1
        types = card.get(constants.DATA_FIELD_TYPES, []) or []
        if "Basic" in types or card.get(constants.DATA_FIELD_NAME) in constants.BASIC_LANDS:
            continue
        count = int(card.get(constants.DATA_FIELD_COUNT, 1) or 1)
        for t in _TYPE_COUNT_ORDER:
            if t in types:
                type_counts[t] += count
                break
    return PoolSummaryVM(
        cmc_distribution=list(metrics.distribution_all),
        cmc_average=round(metrics.cmc_average, 2),
        color_pips=pips,
        creature_count=metrics.creature_count,
        noncreature_count=metrics.noncreature_count,
        card_count=metrics.total_cards,
        type_counts=type_counts,
    )


def compute_signals(scanner) -> Dict[str, float]:
    """Aggregates 'open lane' signals over the draft history (skips pack 2)."""
    return _compute_signals(
        scanner.retrieve_set_metrics(),
        scanner.retrieve_draft_history(),
        scanner.set_data,
    )


def _expected_pool_size(scanner) -> int:
    """The largest pack in the draft's history determines the pick count."""
    history = scanner.retrieve_draft_history() if scanner else []
    return expected_pool_size(history)


def compute_draft_complete(scanner, event_type, taken_count) -> bool:
    """True once a draft's full pool is picked — or a Sealed pool reaches 40 —
    matching the legacy dashboard's draft_complete/sealed_complete gates that
    swap the dashboard to the recap screen."""
    return is_draft_complete(event_type, taken_count, _expected_pool_size(scanner))


def build_draft_state(scanner, config, include_pool_summary: bool = True) -> DraftStateVM:
    """Snapshots the scanner and runs the math engines. Blocking; call off the event loop."""
    with scanner.lock:
        event_set, event_type = scanner.retrieve_current_limited_event()
        pack, pick = scanner.retrieve_current_pack_and_pick()
        metrics = scanner.retrieve_set_metrics()
        tier_data = scanner.retrieve_tier_data()
        taken_cards: List[CardData] = scanner.retrieve_taken_cards()
        pack_cards: List[CardData] = scanner.retrieve_current_pack_cards()
        missing_cards: List[CardData] = scanner.retrieve_current_missing_cards()
        picked_cards: List[CardData] = scanner.retrieve_current_picked_cards()
        draft_id = scanner.current_draft_id
        start_time = scanner.draft_start_time
        event_string = scanner.event_string
        arena_file = scanner.arena_file
        color_ratings = scanner.set_data.get_color_ratings()

    scores = compute_signals(scanner)

    recommendations = evaluate_pack(
        metrics, taken_cards, scores, pack_cards, pick, pack
    )
    rec_map = {r.card_name: r for r in recommendations}

    colors = resolve_colors(
        taken_cards, config.settings.deck_filter, metrics, config
    )
    active_filter = colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS
    is_auto = constants.FILTER_OPTION_AUTO in config.settings.deck_filter
    filter_label = build_filter_label(
        active_filter, config.settings.filter_format, color_ratings, is_auto
    )

    picked_names = {
        c.get(constants.DATA_FIELD_NAME) for c in (picked_cards or [])
    }

    log_name = os.path.basename(arena_file) if arena_file else ""
    log_source = "history" if log_name.startswith("DraftLog_") else "live"

    return DraftStateVM(
        booted=True,
        event_set=event_set or "",
        event_type=event_type or "",
        event_string=event_string or "",
        draft_id=draft_id or "",
        start_time=str(start_time) if start_time else None,
        pack=pack,
        pick=pick,
        active_filter=active_filter,
        filter_label=filter_label,
        pack_cards=[
            card_to_vm(c, active_filter, rec_map, picked_names, tier_data)
            for c in (pack_cards or [])
        ],
        missing_cards=[
            card_to_vm(c, active_filter, rec_map, picked_names, tier_data)
            for c in (missing_cards or [])
        ],
        taken_count=len(taken_cards or []),
        draft_complete=compute_draft_complete(
            scanner, event_type, len(taken_cards or [])
        ),
        signals=SignalsVM(scores=scores),
        pool_summary=pool_summary_vm(taken_cards or []) if include_pool_summary else None,
        dataset_name=config.card_data.latest_dataset or None,
        log_source=log_source,
        log_name=log_name,
    )


def snapshot_recap_inputs(scanner):
    """Snapshots the scanner state a recap needs, under the lock."""
    with scanner.lock:
        _, event_type = scanner.retrieve_current_limited_event()
        metrics = scanner.retrieve_set_metrics()
        taken_cards: List[CardData] = scanner.retrieve_taken_cards()
        draft_id = scanner.current_draft_id
    return taken_cards, metrics, draft_id, event_type


def build_taken_cards(scanner, config) -> TakenCardsVM:
    """Snapshot of the drafted pool with per-filter stats, name-deduped with counts."""
    with scanner.lock:
        metrics = scanner.retrieve_set_metrics()
        taken_cards: List[CardData] = scanner.retrieve_taken_cards()

    colors = resolve_colors(
        taken_cards, config.settings.deck_filter, metrics, config
    )
    active_filter = colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS

    # Dedup by name, accumulating counts
    merged, counts = merge_taken_cards(taken_cards)

    cards = []
    for card in merged:
        vm = card_to_vm(card, active_filter)
        vm.count = counts[card.get(constants.DATA_FIELD_NAME, "Unknown")]
        cards.append(vm)
    cards.sort(key=lambda c: (c.cmc, c.name))

    return TakenCardsVM(
        cards=cards,
        pool_summary=pool_summary_vm(taken_cards or []),
        active_filter=active_filter,
    )
