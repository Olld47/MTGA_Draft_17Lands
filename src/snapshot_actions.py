"""
src/snapshot_actions.py
Shared draft-state computation for the dashboard/recap pipeline, consumed by
both the desktop bridge (mtga_bridge.snapshot) and the legacy tkinter app
(src/ui/app_controller.refresh_ui_data, src/ui/dashboard.py's completion
gate). Pure: open-lane signals, advisor evaluation, color resolution, the
draft-completion gate, taken-card merging, and the filter label — no tkinter,
no pytauri, no viewmodels. Scanner locking, thread marshalling, and
presentation stay in the adapters.

Ticket 09 convergence: this math was duplicated verbatim between the bridge's
snapshot module and the tkinter controller/dashboard (the signal loop, the
DraftAdvisor construction, the is_human/is_bot arms of the completion gate,
the expected-total heuristic). This module is the single implementation both
sides delegate to.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src import constants
from src.advisor.engine import DraftAdvisor
from src.advisor.schema import Recommendation
from src.card_logic import filter_display_name, filter_options, filter_win_rate
from src.signals import SignalCalculator

logger = logging.getLogger(__name__)


def compute_signals(metrics, history, set_data) -> Dict[str, float]:
    """Aggregates 'open lane' signals over the draft history (skips pack 2)."""
    sig_calc = SignalCalculator(metrics)
    scores: Dict[str, float] = {c: 0.0 for c in constants.CARD_COLORS}
    for entry in history or []:
        if entry["Pack"] == 2:
            continue
        h_pack = set_data.get_data_by_id(entry["Cards"])
        for color, value in sig_calc.calculate_pack_signals(
            h_pack, entry["Pick"]
        ).items():
            scores[color] += value
    return scores


def evaluate_pack(
    metrics, taken_cards, signals, pack_cards, pick, pack
) -> List[Recommendation]:
    """Runs the advisor over the current pack with the signal scores."""
    advisor = DraftAdvisor(metrics, taken_cards, signals=signals)
    return advisor.evaluate_pack(pack_cards, pick, current_pack=pack)


def resolve_colors(taken_cards, deck_filter, metrics, config) -> List[str]:
    """The active color filters for the pool (empty when the pool is empty)."""
    return filter_options(taken_cards, deck_filter, metrics, config)


# Event types that represent an actual draft — the legacy dashboard.py is_human
# / is_bot arms of draft_complete. Sealed is handled by its own arm.
_DRAFT_EVENT_TYPES = {
    constants.LIMITED_TYPE_STRING_DRAFT_PREMIER,
    constants.LIMITED_TYPE_STRING_DRAFT_QUICK,
    constants.LIMITED_TYPE_STRING_DRAFT_TRAD,
    constants.LIMITED_TYPE_STRING_DRAFT_BOT,
    constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO,
    constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO_TRAD,
    constants.LIMITED_TYPE_STRING_DRAFT_PICK_TWO_QUICK,
}


def is_draft_event(event_type) -> bool:
    return (event_type or "") in _DRAFT_EVENT_TYPES


def expected_pool_size(history) -> int:
    """The largest pack in the draft's history determines the pick count
    (14 → 42, 13 → 39, ≥15 → size × 3)."""
    max_pack_size = 0
    for entry in history or []:
        pack_size = entry.get("Pick", 1) + len(entry.get("Cards", [])) - 1
        if pack_size > max_pack_size:
            max_pack_size = pack_size
    if max_pack_size >= 15:
        return max_pack_size * 3
    if max_pack_size == 13:
        return 39
    return 42


def is_draft_complete(event_type, taken_count, expected_pool) -> bool:
    """True once a draft's full pool is picked — or a Sealed pool reaches 40 —
    matching the legacy dashboard's draft_complete/sealed_complete gates that
    swap the dashboard to the recap screen."""
    event_type = event_type or ""
    if constants.LIMITED_TYPE_STRING_SEALED in event_type:
        return taken_count >= 40
    return is_draft_event(event_type) and taken_count >= expected_pool


def merge_taken_cards(taken_cards) -> Tuple[List[dict], Dict[str, int]]:
    """Name-deduped cards keeping the first row per name, plus per-name
    counts."""
    merged: Dict[str, dict] = {}
    counts: Dict[str, int] = {}
    for card in taken_cards or []:
        name = card.get(constants.DATA_FIELD_NAME, "Unknown")
        counts[name] = counts.get(name, 0) + 1
        merged.setdefault(name, card)
    return list(merged.values()), counts


def build_filter_label(
    active_filter: str, filter_format, color_ratings, is_auto: bool
) -> str:
    """The masthead filter label. The Auto form is "Auto (Azorius 56.3%)" —
    the shape the legacy overlay builds, not format_filter_label's
    "Azorius (56.3%)" (that would nest parens)."""
    name = filter_display_name(active_filter, filter_format)
    rate = filter_win_rate(active_filter, color_ratings)
    if is_auto:
        return f"Auto ({name}{f' {rate}%' if rate is not None else ''})"
    return f"{name} ({rate}%)" if rate is not None else name
