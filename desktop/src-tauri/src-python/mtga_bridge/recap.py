"""
mtga_bridge.recap
Headless port of src/ui/dashboard_recap.py::DraftRecapScreen.update_summary.
Computes the post-draft pool grade, steals/reaches, synergy, roles and charts
as a pure view-model. No tkinter, no pytauri — unit-testable from the root
poetry environment.
"""

import logging
from typing import List, Optional

from src import constants
from src.card_logic import get_deck_metrics, identify_top_pairs
from src.utils import normalize_color_string

from mtga_bridge.viewmodels import (
    DraftRecordVM,
    RecapArchetypeVM,
    RecapCardVM,
    RecapPickVM,
    RecapRoleVM,
    RecapVM,
)

logger = logging.getLogger(__name__)

_TYPE_ORDER = [
    "Creature",
    "Planeswalker",
    "Battle",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
]

_GRADE_MAP = [
    (90, "S (God Tier)", "success"),
    (85, "A (Amazing)", "success"),
    (80, "B+ (Great)", "info"),
    (75, "B (Good)", "info"),
    (70, "C (Average)", "warning"),
    (60, "D (Below Average)", "danger"),
]


def _gihwr(card: dict) -> float:
    return float(
        card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
    )


def _stat(card: dict, field: str) -> float:
    return float(card.get("deck_colors", {}).get("All Decks", {}).get(field, 0.0))


def _is_basic(card: dict) -> bool:
    return "Basic" in card.get("types", []) or card.get("name") in constants.BASIC_LANDS


def build_recap(taken_cards, metrics, draft_id, event_type) -> RecapVM:
    """Pure port of DraftRecapScreen.update_summary. Returns has_data=False when
    fewer than 40 cards are available (recap requires a completed draft)."""
    if not taken_cards or len(taken_cards) < 40:
        return RecapVM(has_data=False)

    valid_cards = [c for c in taken_cards if not _is_basic(c)]
    if not valid_cards:
        return RecapVM(has_data=False)

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
        ((g, s) for threshold, g, s in _GRADE_MAP if pool_power >= threshold),
        ("F (Trainwreck)", "danger"),
    )

    # 2. TOP ARCHETYPES
    top_pairs = identify_top_pairs(taken_cards, metrics)
    arch_data: List[RecapArchetypeVM] = []
    for pair in top_pairs:
        lane = normalize_color_string("".join(pair))
        wr, _ = metrics.get_metrics(lane, "gihwr") if metrics else (0, 0)
        arch_data.append(
            RecapArchetypeVM(
                name=constants.COLOR_NAMES_DICT.get(lane, lane),
                win_rate=round(wr, 1) if wr and wr > 0 else None,
            )
        )
    arch_data.sort(key=lambda a: a.win_rate or 0.0, reverse=True)

    # 3. BEST CARDS
    best_cards = [
        RecapCardVM(name=c.get("name", "Unknown"), win_rate=round(_gihwr(c), 1))
        for c in top_23[:6]
    ]

    # 4. STEALS & REACHES
    total_cards = len(taken_cards)
    cards_per_pack = (
        15
        if total_cards >= 45
        else (14 if total_cards >= 42 else (total_cards // 3 if total_cards >= 3 else 14))
    )

    steals, reaches = [], []
    for i, c in enumerate(taken_cards):
        name = c.get("name", "")
        if _is_basic(c):
            continue
        pack, pick = (i // cards_per_pack) + 1, (i % cards_per_pack) + 1
        gihwr, alsa, ata = _gihwr(c), _stat(c, "alsa"), _stat(c, "ata")
        if alsa > 0 and pick > alsa + 1.5 and gihwr >= 55.0:
            steals.append(
                RecapPickVM(
                    name=name, pack=pack, pick=pick,
                    reference=round(alsa, 1), delta=round(pick - alsa, 1),
                )
            )
        if ata > 0 and ata > pick + 1.5 and gihwr < 54.0:
            reaches.append(
                RecapPickVM(
                    name=name, pack=pack, pick=pick,
                    reference=round(ata, 1), delta=round(ata - pick, 1),
                )
            )
    steals.sort(key=lambda p: p.delta, reverse=True)
    reaches.sort(key=lambda p: p.delta, reverse=True)

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
        RecapRoleVM(label=t, count=n)
        for t, n in sorted(subs_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        if n >= 3
    ]
    roles = [
        RecapRoleVM(label=constants.TAG_VISUALS.get(t, t.capitalize()), count=n)
        for t, n in sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    staples = [
        c
        for c in valid_cards
        if str(c.get("rarity", "")).lower() in ("common", "uncommon")
        and _gihwr(c) >= 57.0
    ]
    staples.sort(key=_gihwr, reverse=True)
    staple_vms = [
        RecapCardVM(name=c.get("name", ""), win_rate=round(_gihwr(c), 1))
        for c in staples[:6]
    ]

    non_basics.sort(key=_gihwr, reverse=True)
    land_vms = [
        RecapCardVM(name=c.get("name", ""), win_rate=round(_gihwr(c), 1))
        for c in non_basics[:6]
    ]

    # 6. RARES & MYTHICS
    rares = [
        c for c in valid_cards if str(c.get("rarity", "")).lower() in ("rare", "mythic")
    ]
    rares.sort(key=_gihwr, reverse=True)
    rare_vms = [
        RecapCardVM(name=c.get("name", ""), win_rate=round(_gihwr(c), 1))
        for c in rares[:10]
    ]

    # 7. CHARTS
    deck_metrics = get_deck_metrics(taken_cards)
    type_counts = {t: 0 for t in _TYPE_ORDER}
    for card in taken_cards:
        if _is_basic(card):
            continue
        for t in _TYPE_ORDER:
            if t in card.get("types", []):
                type_counts[t] += 1

    return RecapVM(
        has_data=True,
        pool_power=round(pool_power, 0),
        grade=grade_str,
        grade_style=grade_style,
        top_23_avg=round(avg_gihwr, 1),
        format_avg=round(global_mean, 1),
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


def fetch_draft_record(draft_id: str) -> DraftRecordVM:
    """Blocking 17Lands draft-record fetch. Call off the event loop."""
    if not draft_id:
        return DraftRecordVM(found=False)
    from src.seventeenlands import Seventeenlands

    record = Seventeenlands().get_draft_record(draft_id)
    if record and record.get("wins") is not None:
        return DraftRecordVM(
            found=True,
            wins=int(record["wins"]),
            losses=int(record["losses"]),
            url=record.get("url", ""),
        )
    return DraftRecordVM(found=False)
