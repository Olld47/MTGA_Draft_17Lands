"""
src/recap_actions.py
Shared post-draft recap computation for the Recap screen, consumed by both
the desktop bridge (mtga_bridge.recap) and the legacy tkinter view
(src/ui/dashboard_recap.py). Pure: grades the pool, extracts steals/reaches,
synergy/roles, card lists and charts into a plain RecapData dataclass — no
tkinter, no pytauri, no viewmodels. Widget rendering, view-model mapping,
and threading stay in the adapters.

Ticket 09 convergence: the whole analysis was duplicated verbatim between the
bridge's build_recap and the tkinter screen's update_summary (and had drifted
in formatting details). This module is the single implementation both sides
delegate to.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src import constants
from src.advisor.deck_scorer import identify_top_pairs
from src.card_logic import get_deck_metrics
from src.utils import normalize_color_string

logger = logging.getLogger(__name__)

TYPE_ORDER = [
    "Creature",
    "Planeswalker",
    "Battle",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
]

GRADE_MAP = [
    (90, "S (God Tier)", "success"),
    (85, "A (Amazing)", "success"),
    (80, "B+ (Great)", "info"),
    (75, "B (Good)", "info"),
    (70, "C (Average)", "warning"),
    (60, "D (Below Average)", "danger"),
]


def _gihwr(card: dict) -> float:
    return float(card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))


def _stat(card: dict, field: str) -> float:
    return float(card.get("deck_colors", {}).get("All Decks", {}).get(field, 0.0))


def _is_basic(card: dict) -> bool:
    return "Basic" in card.get("types", []) or card.get("name") in constants.BASIC_LANDS


@dataclass
class RecapData:
    """Plain recap result. has_data=False means fewer than 40 usable cards —
    there is nothing to grade. All values are raw; the adapters round, format,
    and map them into their own presentation layer."""

    has_data: bool = False
    pool_power: float = 0.0
    grade: str = ""
    grade_style: str = ""
    top_23_avg: float = 0.0
    format_avg: float = 0.0
    archetypes: List[Tuple[str, float]] = field(default_factory=list)
    best_cards: List[Tuple[str, float]] = field(default_factory=list)
    steals: List[Tuple[str, int, int, float, float]] = field(default_factory=list)
    reaches: List[Tuple[str, int, int, float, float]] = field(default_factory=list)
    tribes: List[Tuple[str, int]] = field(default_factory=list)
    roles: List[Tuple[str, int]] = field(default_factory=list)
    staples: List[Tuple[str, float]] = field(default_factory=list)
    non_basic_lands: List[Tuple[str, float]] = field(default_factory=list)
    rares: List[Tuple[str, float]] = field(default_factory=list)
    cmc_distribution: List[int] = field(default_factory=list)
    type_counts: Dict[str, int] = field(default_factory=dict)
    is_sealed: bool = False
    draft_id: str = ""


def build_recap_data(taken_cards, metrics, draft_id, event_type) -> RecapData:
    """Computes the full post-draft recap. Returns has_data=False when fewer
    than 40 cards are available (recap requires a completed draft)."""
    if not taken_cards or len(taken_cards) < 40:
        return RecapData()

    valid_cards = [c for c in taken_cards if not _is_basic(c)]
    if not valid_cards:
        return RecapData()

    # 1. OVERALL GRADE
    valid_cards.sort(key=_gihwr, reverse=True)
    top_23 = valid_cards[:23]
    avg_gihwr = sum(_gihwr(c) for c in top_23) / len(top_23)

    global_mean, global_std = (
        metrics.get_metrics("All Decks", "gihwr") if metrics else (54.5, 3.5)
    )
    if global_mean <= 0:
        global_mean = 54.5
    if global_std <= 0:
        global_std = 3.5

    z_score = (avg_gihwr - global_mean) / global_std
    pool_power = max(0, min(100, 75.0 + (z_score * 12.0)))
    grade_str, grade_style = next(
        ((g, s) for threshold, g, s in GRADE_MAP if pool_power >= threshold),
        ("F (Trainwreck)", "danger"),
    )

    # 2. TOP ARCHETYPES
    top_pairs = identify_top_pairs(taken_cards, metrics)
    arch_data: List[Tuple[str, float]] = []
    for pair in top_pairs:
        lane = normalize_color_string("".join(pair))
        wr, _ = metrics.get_metrics(lane, "gihwr") if metrics else (0, 0)
        arch_data.append((constants.COLOR_NAMES_DICT.get(lane, lane), wr or 0.0))
    arch_data.sort(key=lambda a: a[1], reverse=True)

    # 3. BEST CARDS
    best_cards = [(c.get("name", "Unknown"), _gihwr(c)) for c in top_23[:6]]

    # 4. STEALS & REACHES
    total_cards = len(taken_cards)
    cards_per_pack = (
        15
        if total_cards >= 45
        else (14 if total_cards >= 42 else (total_cards // 3 if total_cards >= 3 else 14))
    )

    steals: List[Tuple[str, int, int, float, float]] = []
    reaches: List[Tuple[str, int, int, float, float]] = []
    for i, c in enumerate(taken_cards):
        name = c.get("name", "")
        if _is_basic(c):
            continue
        pack, pick = (i // cards_per_pack) + 1, (i % cards_per_pack) + 1
        gihwr, alsa, ata = _gihwr(c), _stat(c, "alsa"), _stat(c, "ata")
        if alsa > 0 and pick > alsa + 1.5 and gihwr >= 55.0:
            steals.append((name, pack, pick, alsa, pick - alsa))
        if ata > 0 and ata > pick + 1.5 and gihwr < 54.0:
            reaches.append((name, pack, pick, ata, ata - pick))
    steals.sort(key=lambda p: p[4], reverse=True)
    reaches.sort(key=lambda p: p[4], reverse=True)

    # 5. SYNERGY & ROLES
    subs_counts, tags_count, non_basics = {}, {}, []
    for c in taken_cards:
        if _is_basic(c):
            continue
        types = c.get("types", [])
        if "Land" in types:
            non_basics.append(c)
        if "Creature" in types:
            for s in c.get("subtypes", []):
                subs_counts[s] = subs_counts.get(s, 0) + 1
        for t in c.get("tags", []):
            tags_count[t] = tags_count.get(t, 0) + 1

    tribes = [
        (t, n)
        for t, n in sorted(subs_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        if n >= 3
    ]
    roles = [
        (constants.TAG_VISUALS.get(t, t.capitalize()), n)
        for t, n in sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    staples = [
        c
        for c in valid_cards
        if str(c.get("rarity", "")).lower() in ("common", "uncommon")
        and _gihwr(c) >= 57.0
    ]
    staples.sort(key=_gihwr, reverse=True)
    staple_vms = [(c.get("name", ""), _gihwr(c)) for c in staples[:6]]

    non_basics.sort(key=_gihwr, reverse=True)
    land_vms = [(c.get("name", ""), _gihwr(c)) for c in non_basics[:6]]

    # 6. RARES & MYTHICS
    rares = [
        c for c in valid_cards if str(c.get("rarity", "")).lower() in ("rare", "mythic")
    ]
    rares.sort(key=_gihwr, reverse=True)
    rare_vms = [(c.get("name", ""), _gihwr(c)) for c in rares[:10]]

    # 7. CHARTS
    deck_metrics = get_deck_metrics(taken_cards)
    type_counts = {t: 0 for t in TYPE_ORDER}
    for card in taken_cards:
        if _is_basic(card):
            continue
        for t in TYPE_ORDER:
            if t in card.get("types", []):
                type_counts[t] += 1

    return RecapData(
        has_data=True,
        pool_power=pool_power,
        grade=grade_str,
        grade_style=grade_style,
        top_23_avg=avg_gihwr,
        format_avg=global_mean,
        archetypes=arch_data[:3],
        best_cards=best_cards,
        steals=steals[:6],
        reaches=reaches[:6],
        tribes=tribes,
        roles=roles,
        staples=staple_vms,
        non_basic_lands=land_vms,
        rares=rare_vms,
        cmc_distribution=list(deck_metrics.distribution_all),
        type_counts=type_counts,
        is_sealed="Sealed" in (event_type or ""),
        draft_id=draft_id or "",
    )


def fetch_draft_record(draft_id) -> Optional[Tuple[int, int, str]]:
    """Blocking 17Lands draft-record fetch: (wins, losses, url), or None when
    the draft is untracked. Call off the event loop."""
    if not draft_id:
        return None
    from src.seventeenlands import Seventeenlands

    record = Seventeenlands().get_draft_record(draft_id)
    if record and record.get("wins") is not None:
        return (
            int(record["wins"]),
            int(record["losses"]),
            record.get("url", ""),
        )
    return None
