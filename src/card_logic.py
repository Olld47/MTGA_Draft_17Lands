"""
src/card_logic.py
The Pro Deck Construction Engine & UI Utilities.
Generates dynamic deck variants and handles data formatting for the UI.
"""

from itertools import combinations
from dataclasses import dataclass, field
import logging
import math
import copy
import re
import io
import csv
import json
from src import constants
from src.card_data import CardData
from src.logger import create_logger

logger = create_logger()

# --- CARD-TEXT HELPER ---


def get_oracle_text(card: CardData) -> str:
    """Returns the lower-cased oracle text of a card, safe for substring
    matching. The single normalization point for card text: falls back to ""
    — without raising — for cards with no usable text (missing / None / empty /
    non-string ``oracle_text``). Never stringify ``None`` into ``"none"``."""
    text = card.get("oracle_text", "")
    return text.lower() if isinstance(text, str) else ""


# --- HELPER CLASSES ---


def get_functional_cmc(card: CardData) -> int:
    """
    Determines the practical mana cost of a card by checking for cost-reduction
    mechanics, alternate casting costs (Disguise/Morph/Evoke), and channel abilities.
    Prevents expensive but highly playable cards from being falsely penalized as 'clunky'.
    """
    try:
        raw_cmc = int(card.get("cmc", 0))
        text = get_oracle_text(card)

        if not text:
            return raw_cmc

        if "landcycling" in text or "bloodrush" in text:
            return min(raw_cmc, 2)

        # Mechanics that let you play the card face down for 3
        if "disguise {" in text or "morph {" in text or "face down as a 2/2" in text:
            return min(raw_cmc, 3)

        # Channel abilities (act as spells)
        if "channel \u2014" in text or "channel —" in text or "channel -" in text:
            return min(raw_cmc, 2)

        # Generic cost reduction: e.g., "costs {3} less", "costs {1} and {U} less", "costs 2 less"
        reduction_match = re.search(r"costs?\s+(.*?)\s+less", text)
        if reduction_match:
            try:
                cost_str = reduction_match.group(1)
                blocks = re.findall(r"\{(.*?)\}", cost_str)
                total_reduction = 0

                if not blocks:
                    # e.g. "costs 2 less"
                    digits = re.findall(r"\d+", cost_str)
                    if digits:
                        total_reduction = sum(int(d) for d in digits)
                else:
                    # e.g. "costs {1} and {U} less"
                    for b in blocks:
                        if b.isdigit():
                            total_reduction += int(b)
                        else:
                            total_reduction += 1

                if total_reduction > 0:
                    return max(1, raw_cmc - total_reduction)
            except (ValueError, TypeError):
                pass

        # Alternate cost keywords that typically mean it's castable for much cheaper
        alt_keywords = [
            "evoke {",
            "prototype {",
            "spectacle {",
            "surge {",
            "cleave {",
            "blitz {",
            "prowl {",
            "madness {",
            "miracle {",
            "convoke",
            "affinity for",
            "improvise",
            "spree",
            "sneak {",
        ]
        if raw_cmc > 3 and any(kw in text for kw in alt_keywords):
            # Generically treat these as 2 mana cheaper for curve/simulation purposes
            return max(2, raw_cmc - 2)

        return raw_cmc
    except Exception:
        return 0


def format_types_for_ui(types_array):
    """Extracts supertypes from a raw types array, guaranteeing 'Creature' is always first."""
    if not types_array:
        return ""

    allowed = {
        "Creature",
        "Enchantment",
        "Land",
        "Artifact",
        "Planeswalker",
        "Instant",
        "Sorcery",
        "Battle",
    }
    filtered = [t for t in types_array if t in allowed]

    if "Creature" in filtered:
        filtered.remove("Creature")
        filtered.insert(0, "Creature")

    return " ".join(filtered)


@dataclass
class DeckMetrics:
    cmc_average: float = 0.0
    creature_count: int = 0
    noncreature_count: int = 0
    total_cards: int = 0
    total_non_land_cards: int = 0
    distribution_all: list = field(default_factory=lambda: [0] * 8)
    distribution_creatures: list = field(default_factory=lambda: [0] * 8)
    distribution_noncreatures: list = field(default_factory=lambda: [0] * 8)
    pip_counts: dict = field(default_factory=dict)
    fixing_sources: dict = field(default_factory=dict)


# --- UI UTILITIES ---


def filter_options(deck, option_selection, metrics, configuration):
    """
    Returns the active color filter for the dashboard.
    Handles 'Auto' by detecting the top color pair in the pool.
    """
    if constants.FILTER_OPTION_AUTO not in option_selection:
        return [option_selection]

    # Auto Logic: Identify top 2 colors
    try:
        # Don't auto-switch until we have enough data (e.g. pick 5)
        if len(deck) < 5:
            return [constants.FILTER_OPTION_ALL_DECKS]

        from src.advisor.deck_scorer import identify_top_pairs

        top_pair = identify_top_pairs(deck, metrics)
        if top_pair and top_pair[0]:
            from src.utils import normalize_color_string

            # Convert ["U", "B"] -> "UB" in strict WUBRG order
            pair_str = normalize_color_string("".join(top_pair[0]))

            # Check if we actually have data for this archetype
            if pair_str:
                mean, std = metrics.get_metrics(pair_str, constants.DATA_FIELD_GIHWR)
                if mean > 0.0:
                    return [pair_str]

    except Exception as e:
        logger.error(f"Auto filter error: {e}")

    return [constants.FILTER_OPTION_ALL_DECKS]


def deck_filter_stats(card: CardData, active_filter: str) -> dict:
    """The per-archetype stats to render for a card under the active filter.

    17Lands records per-card rates per deck archetype. A card that never
    appeared in this exact color combination ships `samples: 0` with every
    rate at 0.0 — the dataset's no-data placeholder. Rendering that as a real
    0% win rate is the "17Lands has the number but the tool shows 0" bug. When
    the active archetype has no games but the set-wide "All Decks" lane does,
    fall back to it: the same card's real rate, aggregated over every deck."""
    deck_colors = card.get(constants.DATA_FIELD_DECK_COLORS, {}) or {}
    stats = deck_colors.get(active_filter, {})
    if (
        active_filter != constants.FILTER_OPTION_ALL_DECKS
        and not stats.get("samples")
    ):
        all_decks = deck_colors.get(constants.FILTER_OPTION_ALL_DECKS, {})
        if all_decks.get("samples"):
            return all_decks
    return stats


def filter_display_name(filter_key, filter_format):
    """A deck filter as the user asked to see it: "Azorius" under the Names
    format, "WU" under Colors. Falls back to the key for anything absent from
    COLOR_NAMES_DICT, which is what "Auto" and "All Decks" hit."""
    if filter_format != constants.DECK_FILTER_FORMAT_NAMES:
        return filter_key
    return constants.COLOR_NAMES_DICT.get(filter_key, filter_key)


def filter_win_rate(filter_key, color_ratings):
    """The archetype's overall win rate, or None when 17Lands reported no
    ratings for it. 0.0 is not usable as the absent value: a real archetype can
    round to it, and the UI has to tell "no data" from "terrible"."""
    if not color_ratings:
        return None
    return color_ratings.get(filter_key)


def format_filter_label(filter_key, filter_format, color_ratings):
    """The label the filter dropdown and the masthead both show, e.g.
    "Azorius (56.3%)". Mirrors log_scanner.retrieve_color_win_rate's format."""
    name = filter_display_name(filter_key, filter_format)
    rate = filter_win_rate(filter_key, color_ratings)
    return f"{name} ({rate}%)" if rate is not None else name


def get_deck_metrics(deck):
    """Calculates distribution and average CMC."""
    metrics = DeckMetrics()
    cmc_total = 0
    try:
        metrics.total_cards = len(deck)
        for card in deck:
            c_types = card.get(constants.DATA_FIELD_TYPES, [])
            c_cmc = get_functional_cmc(card)

            if constants.CARD_TYPE_LAND not in c_types:
                cmc_total += c_cmc
                metrics.total_non_land_cards += 1

                idx = min(c_cmc, 7)
                metrics.distribution_all[idx] += 1

                if constants.CARD_TYPE_CREATURE in c_types:
                    metrics.creature_count += 1
                    metrics.distribution_creatures[idx] += 1
                else:
                    metrics.noncreature_count += 1
                    metrics.distribution_noncreatures[idx] += 1

        metrics.cmc_average = (
            cmc_total / metrics.total_non_land_cards
            if metrics.total_non_land_cards
            else 0.0
        )
    except Exception as error:
        logger.error(f"get_deck_metrics error: {error}")
    return metrics


def get_card_colors(mana_cost):
    """
    Parses a mana cost string (e.g., "{1}{W}{U}") and returns a dictionary
    of color counts (e.g., {'W': 1, 'U': 1}).
    """
    colors = {}
    try:
        if not mana_cost:
            return colors
        for color in constants.CARD_COLORS:
            count = mana_cost.count(color)
            if count > 0:
                colors[color] = count
    except Exception as error:
        logger.error(f"get_card_colors error: {error}")
    return colors


def row_color_tag(mana_cost):
    """Selects the color tag for a table row based on mana cost."""
    if not mana_cost:
        return constants.CARD_ROW_COLOR_COLORLESS_TAG

    colors = set()
    for c in constants.CARD_COLORS:
        if c in mana_cost:
            colors.add(c)

    if len(colors) > 1:
        return constants.CARD_ROW_COLOR_GOLD_TAG
    elif constants.CARD_COLOR_SYMBOL_RED in colors:
        return constants.CARD_ROW_COLOR_RED_TAG
    elif constants.CARD_COLOR_SYMBOL_BLUE in colors:
        return constants.CARD_ROW_COLOR_BLUE_TAG
    elif constants.CARD_COLOR_SYMBOL_BLACK in colors:
        return constants.CARD_ROW_COLOR_BLACK_TAG
    elif constants.CARD_COLOR_SYMBOL_WHITE in colors:
        return constants.CARD_ROW_COLOR_WHITE_TAG
    elif constants.CARD_COLOR_SYMBOL_GREEN in colors:
        return constants.CARD_ROW_COLOR_GREEN_TAG

    return constants.CARD_ROW_COLOR_COLORLESS_TAG


def field_process_sort(field_value):
    """Helper for treeview sorting."""
    try:
        if isinstance(field_value, str):
            val = field_value.replace("*", "").replace("%", "").strip()
            if val in ["NA", "-", ""]:
                return (0, 0.0)

            for k, v in constants.GRADE_ORDER_DICT.items():
                if k.strip() == val:
                    return (1, float(v))

            return (1, float(val))

        elif field_value is None:
            return (0, 0.0)

        return (1, float(field_value))
    except (ValueError, TypeError):
        return (2, str(field_value).lower())


def stack_cards(cards):
    """Consolidates duplicates for UI display."""
    stacked = {}
    for c in cards:
        name = c.get(constants.DATA_FIELD_NAME, "Unknown")
        if name not in stacked:
            stacked[name] = copy.deepcopy(c)
            stacked[name]["count"] = 1
        else:
            stacked[name]["count"] += 1
    return list(stacked.values())


def count_copies(cards):
    """Card count of a stacked list, where each row carries a count."""
    return sum(c.get(constants.DATA_FIELD_COUNT, 1) for c in cards)


def take_copies(cards, limit):
    """The first `limit` copies, splitting the row that straddles the boundary."""
    taken = []
    remaining = limit
    for card in cards:
        if remaining <= 0:
            break
        count = min(card.get(constants.DATA_FIELD_COUNT, 1), remaining)
        row = dict(card)
        row[constants.DATA_FIELD_COUNT] = count
        taken.append(row)
        remaining -= count
    return taken


def copy_deck(deck, sideboard):
    """Formats deck for Clipboard."""
    output = "Deck\n"
    for c in deck:
        count = c.get("count", 1)
        name = c.get("name", "Unknown")
        output += f"{count} {name}\n"

    if sideboard:
        output += "\nSideboard\n"
        for c in sideboard:
            count = c.get("count", 1)
            name = c.get("name", "Unknown")
            output += f"{count} {name}\n"
    return output


def export_draft_to_csv(history, dataset, picked_cards_map):
    import io, csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Pack",
            "Pick",
            "Picked",
            "Name",
            "Colors",
            "CMC",
            "Type",
            "GIHWR",
            "ALSA",
            "ATA",
            "IWD",
        ]
    )
    if not history:
        return output.getvalue()
    user_picks = picked_cards_map[0] if picked_cards_map else []

    for entry in history:
        for cid in entry["Cards"]:
            c_list = dataset.get_data_by_id([cid])
            if not c_list:
                continue
            c = c_list[0]
            stats = c.get("deck_colors", {}).get("All Decks", {})
            writer.writerow(
                [
                    entry["Pack"],
                    entry["Pick"],
                    "1" if str(cid) in user_picks else "0",
                    c.get("name", ""),
                    "".join(c.get("colors", [])),
                    str(c.get("cmc", "")),
                    " ".join(c.get("types", [])),
                    stats.get("gihwr", ""),
                    stats.get("alsa", ""),
                    stats.get("ata", ""),
                    stats.get("iwd", ""),
                ]
            )
    return output.getvalue()


def export_draft_to_json(history, dataset, picked_cards_map):
    import json

    output = []
    user_picks = picked_cards_map[0] if picked_cards_map else []
    for entry in history:
        pack_data = {"Pack": entry["Pack"], "Pick": entry["Pick"], "Cards": []}
        for cid in entry["Cards"]:
            c_list = dataset.get_data_by_id([cid])
            if not c_list:
                continue
            c = c_list[0]
            pack_data["Cards"].append(
                {
                    "Name": c.get("name", ""),
                    "Picked": (str(cid) in user_picks),
                    "Colors": c.get("colors", []),
                    "CMC": c.get("cmc", 0),
                    "Type": c.get("types", []),
                }
            )
        output.append(pack_data)
    return json.dumps(output, indent=4)


def format_win_rate(val, color, field, metrics, result_format):
    from src import constants

    if val == 0.0 or val == "-":
        return "-"

    if (
        not metrics
        or result_format == constants.RESULT_FORMAT_WIN_RATE
        or field not in constants.WIN_RATE_OPTIONS
    ):
        return f"{val:.1f}" if isinstance(val, float) else str(val)

    mean, std = metrics.get_metrics(color, field)
    if std == 0:
        return f"{val:.1f}" if isinstance(val, float) else str(val)

    z_score = (val - mean) / std

    if result_format == constants.RESULT_FORMAT_GRADE:
        for grade, limit in constants.GRADE_DEVIATION_DICT.items():
            if z_score >= limit:
                return grade.strip()
        return "F"
    elif result_format == constants.RESULT_FORMAT_RATING:
        upper, lower = mean + (2.0 * std), mean - (1.67 * std)
        if upper == lower:
            return "2.5"
        rating = ((val - lower) / (upper - lower)) * 5.0
        return f"{max(0.0, min(5.0, rating)):.1f}"

    return f"{val:.1f}" if isinstance(val, float) else str(val)


class CardResult:
    """Processes lists for UI Tables (Dashboard/Overlay)."""

    def __init__(self, set_metrics, tier_data, configuration, pick_number):
        self.metrics = set_metrics
        self.tier_data = tier_data
        self.configuration = configuration
        self.pick_number = pick_number

    def return_results(self, card_list, colors, fields):
        return_list = []
        for card in card_list:
            try:
                selected_card = copy.deepcopy(card)
                selected_card["results"] = ["NA"] * len(fields)
                primary_color = (
                    colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS
                )

                for count, option in enumerate(fields):
                    if option in constants.WIN_RATE_OPTIONS or option in [
                        "alsa",
                        "iwd",
                        "ata",
                        "ohwr",
                        "gpwr",
                        "gdwr",
                        "gnswr",
                    ]:
                        stats = card.get("deck_colors", {}).get(primary_color, {})
                        val = stats.get(option, 0.0)

                        if (
                            option in constants.WIN_RATE_OPTIONS
                            and self.configuration.settings.result_format
                            != constants.RESULT_FORMAT_WIN_RATE
                        ):
                            val = self._format_win_rate(val, primary_color, option)

                        selected_card["results"][count] = val if val != 0.0 else "-"
                    elif option == "name":
                        selected_card["results"][count] = card.get("name", "Unknown")
                    elif option == "colors":
                        selected_card["results"][count] = "".join(
                            card.get("colors", [])
                        )
                    elif "TIER" in option:
                        if self.tier_data and option in self.tier_data:
                            tier_list = self.tier_data[option]
                            card_name = card.get(constants.DATA_FIELD_NAME, "")
                            if card_name in tier_list.ratings:
                                selected_card["results"][count] = tier_list.ratings[
                                    card_name
                                ].rating
                            else:
                                selected_card["results"][count] = "NA"
                        else:
                            selected_card["results"][count] = "NA"
                    elif option == "value":
                        selected_card["results"][count] = 0

                return_list.append(selected_card)
            except Exception as e:
                logger.error(f"CardResult error: {e}")
        return return_list

    def _format_win_rate(self, val, color, field):
        """Converts raw winrate to Grade (A+) or Rating (0-5.0) based on set metrics."""
        if not self.metrics:
            return val
        mean, std = self.metrics.get_metrics(color, field)
        if std == 0:
            return val
        z_score = (val - mean) / std

        if self.configuration.settings.result_format == constants.RESULT_FORMAT_GRADE:
            for grade, limit in constants.GRADE_DEVIATION_DICT.items():
                if z_score >= limit:
                    return grade
            return constants.LETTER_GRADE_F
        elif (
            self.configuration.settings.result_format == constants.RESULT_FORMAT_RATING
        ):
            upper, lower = mean + (2.0 * std), mean - (1.67 * std)
            if upper == lower:
                return 2.5
            rating = ((val - lower) / (upper - lower)) * 5.0
            return round(max(0.0, min(5.0, rating)), 1)
        return val


# NOTE: no advisor-layer symbols are re-exported from this module. The simulator
# / deck_scorer / mana_base / deck_builder names that once lived here at module
# scope formed circular imports that only resolved by import order (importing
# any of those modules first raised ImportError), and dragged the whole advisor
# stack in whenever this low-level module was imported. Consumers must import
# those names from their real modules — src.advisor.simulator, src.advisor.deck_scorer,
# src.advisor.mana_base, src.advisor.deck_builder — directly. The one symbol this
# module still calls (identify_top_pairs, in filter_options) is imported
# function-locally, so card_logic never depends on the advisor layer at import
# time.
