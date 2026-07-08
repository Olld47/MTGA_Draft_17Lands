"""
server/validate.py

Post-transform data-quality checks. These run on the fully assembled dataset
(no extra network calls) and are designed to catch *silent* extraction failures
where the pipeline "succeeds" but the numbers are wrong -- e.g. hitting an
endpoint that ignores the date range or the colors filter, which collapses every
archetype into a tiny copy of the "All Decks" baseline.

A check is either a WARNING (surfaced in the report, does not block) or CRITICAL
(logged as an error and used by the caller to skip saving, so the previous good
file keeps serving).
"""

import logging
from datetime import date
from server import config

logger = logging.getLogger(__name__)

# How many of the most-played cards to inspect per file.
SAMPLE_SIZE = 5
# The single most-played card should appear in at least this fraction of all
# games. Set very low: a real staple covers tens of percent; the wrong-endpoint
# bug produced ~0.1%.
MIN_TOP_SAMPLE_RATIO = 0.01


def _all_decks_samples(card: dict) -> int:
    return card.get("deck_colors", {}).get("All Decks", {}).get("samples", 0) or 0


def _unique_cards(card_ratings: dict) -> list:
    """card_ratings maps many arena_ids to shared card objects; dedupe by name."""
    seen = set()
    cards = []
    for card in card_ratings.values():
        name = card.get("name")
        if name in seen:
            continue
        seen.add(name)
        cards.append(card)
    return cards


def validate_dataset(
    set_code: str,
    draft_format: str,
    user_group: str,
    dataset: dict,
    total_games: int,
) -> tuple[list, list]:
    """Return (warnings, critical_errors) as lists of human-readable strings.

    Critical errors mean the data is almost certainly broken and should not
    overwrite the previously published file.
    """
    label = f"{set_code} {draft_format} ({user_group})"
    warnings: list = []
    critical: list = []

    card_ratings = dataset.get("card_ratings", {})
    cards = _unique_cards(card_ratings)

    if not cards:
        critical.append("Dataset contains no card ratings.")
        return warnings, critical

    top_cards = sorted(cards, key=_all_decks_samples, reverse=True)[:SAMPLE_SIZE]
    max_samples = _all_decks_samples(top_cards[0])

    # --- Check 1: sample coverage vs. total games in the format ---------------
    # Only meaningful once the format has a non-trivial number of games.
    if total_games >= config.MIN_GAMES_THRESHOLD:
        if max_samples < total_games * MIN_TOP_SAMPLE_RATIO:
            warnings.append(
                f"Sample coverage looks truncated: most-played card seen in "
                f"{max_samples} games vs {total_games} total in format "
                f"({max_samples / total_games:.2%}). Card ratings may be a partial "
                f"snapshot (ignored date range or wrong endpoint)."
            )

    # --- Check 2: at least some sampled cards have real win-rate data ---------
    if all(
        c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0) == 0
        and _all_decks_samples(c) > 0
        for c in top_cards
    ):
        critical.append(
            "Every sampled card has a 0% 'All Decks' win rate despite non-zero "
            "samples -- win-rate fields were not populated."
        )

    # --- Check 3: archetype (colors) filter actually applied ------------------
    # Which archetypes (besides All Decks) carry any per-card data at all?
    active_archs = set()
    for c in cards:
        for arch, stats in c.get("deck_colors", {}).items():
            if arch != "All Decks" and (stats.get("samples", 0) or 0) > 0:
                active_archs.add(arch)

    if active_archs:
        diverged = False
        for c in top_cards:
            deck_colors = c.get("deck_colors", {})
            base = deck_colors.get("All Decks", {})
            for arch in active_archs:
                stats = deck_colors.get(arch, {})
                if (stats.get("samples", 0) or 0) <= 0:
                    continue
                if stats.get("samples") != base.get("samples") or stats.get(
                    "gihwr"
                ) != base.get("gihwr"):
                    diverged = True
                    break
            if diverged:
                break

        if not diverged:
            critical.append(
                f"All {len(active_archs)} color-pair archetypes are byte-identical "
                f"to 'All Decks' across the {len(top_cards)} most-played cards -- the "
                f"colors filter was ignored and every archetype is a copy of the "
                f"baseline."
            )

    if not warnings and not critical:
        logger.info(f"   [Validation] {label}: passed.")
    return warnings, critical


def enough_history_to_enforce(start_date: str, end_date: str) -> bool:
    """Whether the set has enough days of data for a critical validation issue to
    justify *blocking* a publish. Day one/two of a set can legitimately look thin,
    so criticals are treated as warnings until the set matures. If the dates can't
    be parsed we keep the safety net on (enforce)."""
    try:
        span = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
    except (ValueError, TypeError):
        return True
    return span >= config.VALIDATION_ENFORCE_MIN_DAYS
