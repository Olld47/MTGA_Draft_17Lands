"""
mtga_bridge.deck_view
Shared deck row / stats view-model builders used by both the custom-deck
(deck_session.py) and sealed-studio (sealed_session.py) sessions. These port
the arithmetic from custom_deck.py::_render_deck_stats once so both callers
stay identical. Pure — no tkinter, no pytauri.
"""

from typing import Dict, List

from src import constants
from src.card_logic import get_functional_cmc, row_color_tag

from mtga_bridge.viewmodels import DeckPipVM, DeckRowVM, DeckStatsVM, RecapRoleVM

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


def card_sort_key(card: dict):
    return (card.get(constants.DATA_FIELD_CMC, 0), card.get(constants.DATA_FIELD_NAME, ""))


def row_vm(card: dict, active_filter: str) -> DeckRowVM:
    raw = card.get("deck_colors", {}).get(active_filter, {}).get("gihwr")
    gihwr = None
    if raw not in (None, ""):
        try:
            gihwr = round(float(raw), 1)
        except (TypeError, ValueError):
            gihwr = None
    try:
        cmc = float(card.get("cmc", 0) or 0)
    except (TypeError, ValueError):
        cmc = 0.0
    return DeckRowVM(
        name=card.get("name", "Unknown"),
        count=int(card.get("count", 1) or 1),
        cmc=cmc,
        types=list(card.get("types", []) or []),
        colors=list(card.get("colors", []) or []),
        mana_cost=card.get("mana_cost", "") or "",
        gihwr=gihwr,
        row_tag=row_color_tag(card.get("mana_cost", "")),
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
