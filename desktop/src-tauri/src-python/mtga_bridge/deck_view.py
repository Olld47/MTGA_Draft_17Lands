"""
mtga_bridge.deck_view
Shared deck row / stats / simulation view-model builders used by the
custom-deck (deck_session.py), sealed-studio (sealed_session.py) and
suggest-deck (suggest_session.py) sessions. These port the arithmetic from
custom_deck.py::_render_deck_stats and the ADVISOR SUMMARY heuristics from
_show_sim_results once so every caller stays identical. Pure — no tkinter,
no pytauri.
"""

import random
from typing import Dict, List, Optional

from src import constants
from src.advisor.mana_base import get_strict_colors, is_castable
from src.card_logic import (
    deck_filter_stats,
    get_functional_cmc,
    row_color_tag,
)
from src.deck_actions import card_sort_key

from mtga_bridge.viewmodels import (
    DeckColorVM,
    DeckPipVM,
    DeckRowVM,
    DeckStatsVM,
    RecapRoleVM,
    SampleHandVM,
    SimResultVM,
    SimStatsVM,
)

BASIC_COLOR_MAP = {
    "Plains": "W",
    "Island": "U",
    "Swamp": "B",
    "Mountain": "R",
    "Forest": "G",
}
PIP_META = [("W", "White"), ("U", "Blue"), ("B", "Black"), ("R", "Red"), ("G", "Green")]
SUPERTYPES = {
    "Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker",
    "Land", "Legendary", "Basic", "Snow", "World", "Tribal", "Kindred", "Ongoing",
}


def _clean_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _clean_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def hover_share_vm(card: dict) -> List[DeckColorVM]:
    """Per-color play-share stats for the hover ARCHETYPE PLAY SHARE section.
    Mirrors the legacy CardToolTip filter (`gihwr > 0`), sort (samples desc) and
    cap (top 10); "All Decks" is never a play-share archetype."""
    deck_colors = card.get("deck_colors", {}) or {}
    shares = []
    for color, stats in deck_colors.items():
        if color == "All Decks":
            continue
        gihwr = _clean_float(stats.get("gihwr"))
        if not gihwr or gihwr <= 0:
            continue
        shares.append(
            DeckColorVM(
                color=color,
                gihwr=gihwr,
                samples=_clean_int(stats.get("samples")) or 0,
            )
        )
    shares.sort(key=lambda s: s.samples, reverse=True)
    return shares[:10]


def row_vm(card: dict, active_filter: str) -> DeckRowVM:
    raw = deck_filter_stats(card, active_filter).get("gihwr")
    gihwr = None
    if raw not in (None, ""):
        try:
            gihwr = round(float(raw), 1)
        except (TypeError, ValueError):
            gihwr = None
    all_decks = card.get("deck_colors", {}).get("All Decks", {}) or {}
    try:
        cmc = float(card.get("cmc", 0) or 0)
    except (TypeError, ValueError):
        cmc = 0.0
    image = card.get(constants.DATA_SECTION_IMAGES, []) or []
    if isinstance(image, dict):
        image = [v for v in image.values() if v]
    return DeckRowVM(
        name=card.get("name", "Unknown"),
        count=int(card.get("count", 1) or 1),
        cmc=cmc,
        types=list(card.get("types", []) or []),
        colors=list(card.get("colors", []) or []),
        rarity=card.get("rarity", "") or "",
        mana_cost=card.get("mana_cost", "") or "",
        gihwr=gihwr,
        iwd=_clean_float(all_decks.get("iwd")),
        alsa=_clean_float(all_decks.get("alsa")),
        ata=_clean_float(all_decks.get("ata")),
        samples=_clean_int(all_decks.get("samples")),
        deck_colors=hover_share_vm(card),
        tags=list(card.get("tags", []) or []),
        row_tag=row_color_tag(card.get("mana_cost", "")),
        image=[u for u in image if u],
    )


def build_stats(deck_list: List[dict]) -> DeckStatsVM:
    """Port of custom_deck.py::_render_deck_stats' arithmetic."""
    if not deck_list:
        return DeckStatsVM()
    total_cards = sum(c.get("count", 1) for c in deck_list)
    creatures = sum(
        c.get("count", 1) for c in deck_list if "Creature" in c.get("types", [])
    )
    lands = sum(c.get("count", 1) for c in deck_list if "Land" in c.get("types", []))
    spells = total_cards - creatures - lands

    pips = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
    curve = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    tags: Dict[str, int] = {}
    subtypes: Dict[str, int] = {}
    cmc_sum = 0
    non_lands = 0

    for c in deck_list:
        count = c.get("count", 1)
        if "Land" not in c.get("types", []):
            non_lands += count
            cmc = get_functional_cmc(c)
            cmc_sum += cmc * count
            idx = min(cmc, 6) or 1
            curve[idx] += count
            cost = c.get("mana_cost", "")
            for symbol in "WUBRG":
                pips[symbol] += cost.count(symbol) * count
            for t in c.get("tags", []):
                tags[t] = tags.get(t, 0) + count
        if "Creature" in c.get("types", []):
            for t in c.get("types", []):
                if t not in SUPERTYPES:
                    subtypes[t] = subtypes.get(t, 0) + count

    avg_cmc = cmc_sum / non_lands if non_lands else 0.0
    top_tribes = sorted(subtypes.items(), key=lambda x: x[1], reverse=True)[:5]
    top_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)[:6]

    basics = {
        name: sum(c.get("count", 1) for c in deck_list if c["name"] == name)
        for name in BASIC_COLOR_MAP
    }

    return DeckStatsVM(
        total_cards=total_cards,
        creatures=creatures,
        noncreatures=spells,
        lands=lands,
        avg_cmc=round(avg_cmc, 2),
        pips=[
            DeckPipVM(symbol=sym, name=name, count=pips[sym])
            for sym, name in PIP_META
            if pips[sym] > 0
        ],
        curve={str(k): v for k, v in curve.items()},
        tribes=[RecapRoleVM(label=t, count=n) for t, n in top_tribes],
        tags=[
            RecapRoleVM(label=constants.TAG_VISUALS.get(t, t), count=n)
            for t, n in top_tags
        ],
        basics=basics,
    )


def _gihwr(card: dict) -> float:
    try:
        return float(card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0))
    except (TypeError, ValueError):
        return 0.0


def build_advice(
    deck_list: List[dict], sb_list: List[dict], stats: dict, optimization_note: str
) -> List[str]:
    """Port of the ADVISOR SUMMARY heuristics in _show_sim_results."""
    advice: List[str] = []
    if stats["cast_t2"] < 50:
        advice.append("• Add more 2-drops to improve early board presence.")

    non_basics = [
        c
        for c in deck_list
        if "Land" in c.get("types", [])
        and "Basic" not in c.get("types", [])
        and c.get("name") not in constants.BASIC_LANDS
    ]
    colorless_lands = [c for c in non_basics if not c.get("colors")]

    if stats["color_screw_t3"] > 10.0:
        if colorless_lands:
            advice.append(
                f"• Color screw risk is elevated. Consider cutting a colorless utility land (like {colorless_lands[0].get('name', '')}) for a basic land."
            )
        else:
            advice.append(
                "• High color screw risk. Consider cutting a splash card or adding more fixing."
            )

    is_18_lands = optimization_note and "18 Lands" in optimization_note
    is_16_lands = optimization_note and "16 Lands" in optimization_note
    if stats["screw_t3"] > 22.0 and not is_16_lands:
        advice.append("• Frequently missing land drops. Consider running an extra land.")
    if stats["flood_t5"] > 28.0 and not is_18_lands:
        advice.append("• High flood risk. Consider cutting a land or adding mana sinks.")
    if stats["removal_t4"] < 45:
        advice.append("• Low early interaction. Prioritize cheap removal.")

    deck_colors = set()
    for c in deck_list:
        if "Land" not in c.get("types", []):
            for col in c.get("colors", []):
                deck_colors.add(col)
    if len(deck_colors) >= 3:
        advice.append(
            "⚠️ Mana Base: You are playing 3+ colors. This inherently increases your risk of color screw. Ensure you have at least 3-4 strong fixing sources."
        )

    if not optimization_note and (stats["cast_t2"] < 50 or stats["flood_t5"] > 25):
        expensive_cards = [
            c
            for c in deck_list
            if int(c.get("cmc", 0)) >= 5 and "Land" not in c.get("types", [])
        ]
        if expensive_cards:
            deck_spells = [c for c in deck_list if "Land" not in c.get("types", [])]
            deck_colors_strict = (
                get_strict_colors(deck_spells) if deck_spells else ["W", "U", "B", "R", "G"]
            )
            worst_expensive = min(expensive_cards, key=_gihwr)
            cheap_sb = [
                c
                for c in sb_list
                if int(c.get("cmc", 0)) <= 3
                and "Land" not in c.get("types", [])
                and "Creature" in c.get("types", [])
                and is_castable(c, deck_colors_strict, strict=True)
            ]
            if cheap_sb:
                best_cheap = max(cheap_sb, key=_gihwr)
                advice.append(
                    f"• Swap: Cut [{worst_expensive['name']}] for [{best_cheap['name']}] to lower curve."
                )
    return advice


def build_sim_result(
    deck_list: List[dict],
    sb_list: List[dict],
    stats: dict,
    optimization_note: str = "",
) -> SimResultVM:
    return SimResultVM(
        ok=True,
        stats=SimStatsVM(**{k: round(float(v), 2) for k, v in stats.items()}),
        optimization_note=optimization_note or "",
        advice=build_advice(deck_list, sb_list, stats, optimization_note),
    )


def _hand_sort_key(card: dict):
    types = card.get("types", [])
    name = card.get("name", "")
    cmc = int(card.get("cmc", 0))
    if "Land" in types:
        if "Basic" in types or name in constants.BASIC_LANDS:
            color_order = 5
            for i, land in enumerate(("Plains", "Island", "Swamp", "Mountain", "Forest")):
                if land in name:
                    color_order = i
                    break
            return (0, color_order, name)
        return (1, 0, name)
    return (2, cmc, name)


def build_sample_hand(deck_list: List[dict], active_filter: str) -> SampleHandVM:
    """Port of _draw_sample_hand's card selection + ordering (image loading is
    left to the frontend, which reads the Scryfall URLs directly)."""
    if not deck_list:
        return SampleHandVM(cards=[], message="Generate a deck first.")
    flat_deck: List[dict] = []
    for c in deck_list:
        flat_deck.extend([c] * int(c.get("count", 1)))
    if len(flat_deck) < 7:
        return SampleHandVM(cards=[], message="Deck has fewer than 7 cards.")

    hand = random.sample(flat_deck, 7)
    hand.sort(key=_hand_sort_key)
    return SampleHandVM(cards=[row_vm(c, active_filter) for c in hand])
