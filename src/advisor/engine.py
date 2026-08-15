"""
src/advisor/engine.py
The "Compositional Brain" (v5.5 Pro-Tour Architecture)
Updated: Bayesian Smoothing, Signal Tie-Breakers, Top-End/Synergy Tracking, and Premium Removal Splash.

All scoring coefficients live in ENGINE_PARAMS below — the engine reads them
and never restates a tuned value. docs/03-business-logic.md references the same
field names; change a coefficient in exactly one place (ENGINE_PARAMS).
"""

import statistics
import logging
import math
import numpy as np
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants
from src.card_data import CardData
from src.advisor.mana_base import count_fixing
from src.card_logic import get_functional_cmc

logger = logging.getLogger(__name__)

# Exceptions that indicate dirty / missing data in a card dict — caught and
# skipped in all scoring loops. Structural errors (AttributeError, etc.) are
# deliberately left uncaught so they surface as visible failures.
_DIRTY_DATA_EXC = (TypeError, ValueError, KeyError)


ENGINE_PARAMS_CALIBRATION = (
    "The ENGINE_PARAMS values below are heuristic hand-tuned tuning constants. "
    "There is NO backtest or regression harness validating them: changing a "
    "value (or the branch that consumes it) has no way to measure whether the "
    "engine's recommendations got better or worse. This is acknowledged "
    "calibration debt — each field documents the docs/03 section and the "
    "consuming branch so a change is at least traceable."
)


# --- targets: draft-shape definitions & baselines (docs/03 §2, §5, §7, §8) ---
@dataclass(frozen=True)
class TargetsParams:
    """Baseline draft shape: pick counts, role targets, bomb thresholds."""

    total_picks: int = 45                # picks in a full draft = 3 × picks_per_pack
    picks_per_pack: int = 15             # cards per pack (commitment-curve math)
    target_early_plays: int = 7          # docs §5: "Velocity Target 7+ early plays"
    target_hard_removal: int = 3         # docs §7: hard-removal quota
    bomb_z_score: float = 1.5            # docs §8: elite / TRUE BOMB Z threshold
    iwd_premium_threshold: float = 4.5   # docs §8: IWD % above which a bomb gets its bonus
    global_mean_fallback: float = 54.0   # baseline GIHWR mean when the set has no stats
    global_std_fallback: float = 4.0     # baseline GIHWR std when the set has no stats
    early_cmc_max: int = 2               # "early play" = CMC ≤ 2 (velocity/VOR roles)
    heavy_cmc_min: int = 5               # "top-heavy" = CMC ≥ 5 (docs §5)
    playable_std_floor: float = 1.0      # z-floor (mean − 1·std) for "playable"; feeds VOR, lane detection, off-color


# --- lane: recency bias & color-lane detection (docs/03 §2) ---
@dataclass(frozen=True)
class LaneParams:
    """Recency decay and the color-weight heuristic that finds the open lane."""

    recency_base: float = 1.0            # docs §2: recency multiplier for the first drafted card
    recency_range: float = 2.0           # docs §2: linear ramp → newest card gets recency_base + recency_range
    color_weight_base: float = 1.0       # lane score: base points per playable card
    color_weight_gain: float = 2.0       # lane score: points gained per std above the mean WR
    color_weight_floor: float = 0.2      # lane score: floor per card so weak cards still count a little
    min_pool_for_lane: int = 15          # pool size before color weighting activates
    min_color_total: int = 5             # minimum drafted cards before the leader-set rule applies
    color_share_threshold: float = 0.15  # share of the pool a color needs to join the lane
    weight_floor: float = 2.5            # small-pool lane: raw weight a color must clear
    splash_z: float = 1.5                # pool: WR z above this marks a color as a splash target


# --- progressive: archetype weighting & bayesian blending (docs/03 §3, §6) ---
@dataclass(frozen=True)
class ProgressiveParams:
    """How global vs archetype win rates blend and how signals tie-break."""

    arch_weight_base: float = 0.2        # docs §3: archetype share at pick 1 (global dominates early)
    arch_weight_ramp: float = 0.7        # docs §3: archetype share gained per pick toward max
    arch_weight_max: float = 0.9         # docs §3: archetype share cap at the final pick
    confidence_denominator: float = 1000.0  # docs §3: samples for full archetype trust (bayesian)
    min_arch_samples: int = 10           # archetype stats ignored below this sample count
    base_score_offset: float = 50.0      # docs §6: base score at the global-mean win rate
    base_score_scale: float = 15.0       # docs §6: score points per std of WR deviation
    std_floor: float = 0.1               # guards division by a near-zero std
    signal_threshold: float = 10.0       # signal strength across a card's colors before the tie-breaker
    signal_boost: float = 1.05           # tie-breaker multiplier on cards backed by strong signals


# --- synergy: archetype glue / synergy / on-lane boosts (docs/03 §3, §6) ---
@dataclass(frozen=True)
class SynergyParams:
    """Rewards for cards that overperform in the drafted lane."""

    glue_delta_threshold: float = 1.0    # docs §6: lane outperformance % that makes a common/uncommon glue
    glue_multiplier: float = 5.0         # docs §6: glue bonus = delta × this (outscore generic rares)
    glue_rarities: tuple = ("common", "uncommon")  # docs §6: only these rarities can be glue
    synergy_delta_threshold: float = 1.5  # docs §3: lane outperformance % before archetype synergy fires
    synergy_multiplier: float = 3.0      # docs §3: synergy bonus = delta × this
    on_lane_needs_playables_mult: float = 1.3  # docs §3: pack-3 on-lane boost when the pool is short
    on_lane_mult: float = 1.1            # docs §3: standard on-lane base multiplier
    needs_playables_threshold: int = 20  # pack-3 on-color pool below which the 1.3× boost applies


# --- vor: value over replacement / role scarcity (docs/03 §6) ---
@dataclass(frozen=True)
class VorParams:
    """Bump or penalty for playing a rare/plentiful role in the set texture."""

    scarce_role_count: int = 2           # docs §6: ≤ this many playables → High VOR
    bonus: float = 6.0                   # docs §6: High VOR bonus points
    replaceable_role_count: int = 7      # docs §6: ≥ this many playables → Highly Replaceable
    replaceable_penalty: float = 2.0     # docs §6: penalty points for a replaceable role


# --- bomb: IWD / true-bomb / power-bonus math (docs/03 §8) ---
@dataclass(frozen=True)
class BombParams:
    """How game-warping cards break past the normal scoring curve."""

    iwd_mult: float = 1.15               # docs §8: TRUE BOMB IWD power multiplier
    iwd_bomb_z: float = 1.0              # docs §8: min Z alongside high IWD for the premium
    power_bonus_scale: float = 10.0      # docs §8: Z → power-bonus scale
    power_bonus_min_z: float = 0.5       # docs §8: Z floor before power bonus counts
    lateness_threshold: float = 2.0      # docs §4: picks past ALSA before the late-signal bonus
    lateness_scale: float = 3.0          # docs §4: late-signal bonus scale
    signal_min_pick: int = 5             # docs §4: pack-1 picks at/after which late-signal capitalization fires
    elite_castability_floor: float = 0.4  # docs §8: min castability for elite designation


# --- castability: sliding commitment curve & splash rules (docs/03 §4, §8) ---
@dataclass(frozen=True)
class CastabilityParams:
    """Off-color discipline across the packs, plus premium/removal splash."""

    p1_grace_picks: int = 7              # docs §4: pack-1 picks free of off-color pressure
    p1_decay_per_pick: float = 0.05      # docs §4: −0.05 per pick past the grace window
    p1_gold_pip_floor: float = 0.2       # docs §4: pack-1 off-color gold floor
    p1_gold_extra_penalty: float = 0.2   # docs §4: extra penalty for multi-pip gold in pack 1
    p1_off_color_floor: float = 0.4      # docs §4: pack-1 off-color floor
    double_pip_fixing_floor: int = 2     # docs §4: below this fixing, double-pip is uncastable
    uncastable_double_pip_mult: float = 0.01  # docs §4: double-pip off-lane penalty
    premium_removal_z: float = 1.0       # docs §8: Z floor for the premium-removal splash
    splash_fixing_floor_p2: int = 3      # docs §4: fixing sources needed to splash in pack 2
    splash_fixing_floor_p3: int = 4      # docs §4: fixing sources needed to splash in pack 3
    bomb_splash_mult_p2: float = 0.45    # docs §4: bomb splash multiplier in pack 2
    bomb_splash_mult_p3: float = 0.35    # docs §4: bomb splash multiplier in pack 3
    greedy_fixing_floor: int = 4         # docs §4: fixing needed for the greedy 2-pip bomb splash
    greedy_splash_mult: float = 0.30     # docs §4: greedy 2-pip bomb splash multiplier
    splashable_mult: float = 0.3         # docs §4: single off-lane pip with dedicated fixing
    off_color_mult_p2: float = 0.05      # docs §4: generic off-color penalty in pack 2
    off_color_mult_p3: float = 0.01      # docs §4: generic off-color penalty in pack 3


# --- composition: dynamic pool needs (docs/03 §5, §7) ---
@dataclass(frozen=True)
class CompositionParams:
    """Curve, creature/synergy/fixing/removal hunger, and early-play pressure."""

    heavy_drops_threshold: int = 4       # docs §5: ≥ this many 5+-drops triggers the top-heavy penalty
    heavy_drops_mult: float = 0.7        # docs §5: top-heavy dampening multiplier
    creature_projection_floor: int = 13  # docs §5: projected creatures below this → needs creatures
    creature_mult: float = 1.25          # docs §5: creature-hunger multiplier
    artifact_synergy_count: int = 4      # docs §5: artifacts before artifact synergy fires
    graveyard_synergy_count: int = 3     # docs §5: graveyard enablers before synergy fires
    counters_synergy_count: int = 3      # docs §5: counter enablers before synergy fires
    synergy_mult: float = 1.2            # docs §5: A+B synergy multiplier (shared across the three)
    fixing_hunger_mult: float = 1.4      # docs §5: fixing cards when off-color playables outstrip fixing
    splash_enabler_mult: float = 1.3     # docs §5: fixing that enables a drafted splash bomb
    premium_fixing_mult: float = 1.15    # docs §5: early multi-color fixing
    removal_hunger_mult: float = 1.3     # docs §7: below quota → interaction panic multiplier
    removal_saturated_count: int = 6     # docs §7: ≥ this many removal → saturated
    removal_saturated_mult: float = 0.8  # docs §7: saturated-removal penalty
    early_plays_mult_cap: float = 0.5    # docs §5: max 2-drop-hunger boost
    early_plays_scale: float = 0.15      # docs §5: boost gained per missing 2-drop
    early_plays_pack1_mult: float = 1.1  # docs §5: pack-1 curve-foundation boost


# --- deck: late-draft deck-score improvement (docs/03 §9.C context) ---
@dataclass(frozen=True)
class DeckParams:
    """Pack-3 bonus for cards that lift the projected best deck."""

    improvement_threshold: float = 0.1   # deck-score gain above which the bonus counts as real
    improvement_mult: float = 3.0        # deck-improvement bonus multiplier
    min_pool_for_deck_scoring: int = 23  # pool size before deck-scoring/improvement activates


# --- wheel: relative wheel logic (docs/03 §10 "Steals & Reaches" context) ---
@dataclass(frozen=True)
class WheelParams:
    """Multipliers for cards likely to come back around (fed by WHEEL_COEFFICIENTS)."""

    cutoff_pick: int = 9                 # picks at/after this never wheel-check
    coeff_index_cap: int = 5             # index cap into constants.WHEEL_COEFFICIENTS (packs 1-6)
    rank0_mult: float = 0.10             # best card in the pack rarely wheels
    rank_top2_mult: float = 0.40         # top-2 pack cards rarely wheel
    mult: float = 0.8                    # wheeling-card multiplier
    prob_threshold: float = 75.0         # wheel % above which the 0.8× applies
    min_rank: int = 4                    # rank floor for the wheel discount


@dataclass(frozen=True)
class EngineParams:
    """Single source of truth for every scoring coefficient. See
    ENGINE_PARAMS_CALIBRATION for the calibration-debt caveat."""

    targets: TargetsParams = TargetsParams()
    lane: LaneParams = LaneParams()
    progressive: ProgressiveParams = ProgressiveParams()
    synergy: SynergyParams = SynergyParams()
    vor: VorParams = VorParams()
    bomb: BombParams = BombParams()
    castability: CastabilityParams = CastabilityParams()
    composition: CompositionParams = CompositionParams()
    deck: DeckParams = DeckParams()
    wheel: WheelParams = WheelParams()


ENGINE_PARAMS = EngineParams()


class DraftAdvisor:
    def __init__(
        self, set_metrics, taken_cards: List[CardData], signals: Dict[str, float] = None
    ):
        self.metrics = set_metrics
        self.pool = taken_cards or []
        self.signals = signals or {}

        # 1. Base statistical baselines
        self.global_mean, self.global_std = self.metrics.get_metrics(
            "All Decks", "gihwr"
        )
        if self.global_mean <= 0:
            self.global_mean = ENGINE_PARAMS.targets.global_mean_fallback
        if self.global_std <= 0:
            self.global_std = ENGINE_PARAMS.targets.global_std_fallback

        # 2. Identify established lane
        self.main_colors, self.color_counts = self._identify_main_colors()
        self.main_archetype = (
            "".join(sorted(self.main_colors[:2]))
            if len(self.main_colors) >= 2
            else "All Decks"
        )
        self.active_colors = self.main_colors

        # 3. Analyze Pool Needs
        self.fixing_map = count_fixing(self.pool)
        self.pool_metrics = self._analyze_pool()

    def evaluate_pack(
        self, pack_cards: List[CardData], current_pick: int, current_pack: int = 1
    ) -> List[Recommendation]:
        if not pack_cards:
            return []
        safe_pick = max(1, min(ENGINE_PARAMS.targets.total_picks, current_pick))
        pack_number = max(1, current_pack)

        on_color_pool = [
            c
            for c in self.pool
            if all(col in self.main_colors for col in c.get("colors", []))
        ]
        needs_playables = (
            len(on_color_pool) < ENGINE_PARAMS.synergy.needs_playables_threshold
            and pack_number == 3
        )

        pack_wrs = []
        for c in pack_cards:
            try:
                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )
                if wr > 0:
                    pack_wrs.append(wr)
            except _DIRTY_DATA_EXC:
                continue

        pack_mean = statistics.mean(pack_wrs) if pack_wrs else self.global_mean
        pack_std = statistics.pstdev(pack_wrs) if len(pack_wrs) > 1 else self.global_std
        if pack_std <= 0:
            pack_std = self.global_std

        pack_cards_sorted = sorted(pack_cards, key=self._pack_win_rate_sort_key, reverse=True)
        pack_ranks = {
            str(c.get("name", "Unknown")).strip(): i
            for i, c in enumerate(pack_cards_sorted)
        }

        self.base_deck_score = 0.0
        self.color_options = []
        if pack_number >= 3 and len(self.pool) >= ENGINE_PARAMS.deck.min_pool_for_deck_scoring:
            try:
                from src.advisor.deck_scorer import identify_top_pairs

                self.color_options = identify_top_pairs(self.pool, self.metrics)
                self.base_deck_score = self._get_fast_best_deck_score(
                    self.pool, self.color_options
                )
            except Exception as e:
                logger.warning(f"Advisor base deck scoring error: {e}")
                self.base_deck_score = 0.0
                self.color_options = []

        recommendations = []
        for card in pack_cards:
            try:
                name = str(card.get("name", "Unknown")).strip()
                stats = card.get("deck_colors", {}).get("All Decks", {})
                raw_gihwr, raw_iwd, alsa = (
                    float(stats.get("gihwr", 0.0)),
                    float(stats.get("iwd", 0.0)),
                    float(stats.get("alsa", 0.0)),
                )
                card_colors = card.get("colors", [])
                reasons, synergy_bonus = [], 0.0

                # --- STEP 1: Blended Base Score (With Bayesian Smoothing & Signals) ---
                base_score = self._calculate_weighted_score(card, safe_pick)

                # --- STEP 2: Bomb Detection ---
                z_score = (raw_gihwr - pack_mean) / pack_std
                iwd_mult = (
                    ENGINE_PARAMS.bomb.iwd_mult
                    if (
                        raw_iwd > ENGINE_PARAMS.targets.iwd_premium_threshold
                        and z_score > ENGINE_PARAMS.bomb.iwd_bomb_z
                    )
                    else 1.0
                )
                power_bonus = (
                    max(0, z_score * ENGINE_PARAMS.bomb.power_bonus_scale * iwd_mult)
                    if z_score > ENGINE_PARAMS.bomb.power_bonus_min_z
                    else 0
                )

                # --- STEP 3: Signal Capitalization ---
                if (
                    pack_number == 1
                    and safe_pick >= ENGINE_PARAMS.bomb.signal_min_pick
                    and alsa > 0
                ):
                    lateness = safe_pick - alsa
                    if (
                        lateness >= ENGINE_PARAMS.bomb.lateness_threshold
                        and z_score > ENGINE_PARAMS.bomb.power_bonus_min_z
                    ):
                        power_bonus += lateness * z_score * ENGINE_PARAMS.bomb.lateness_scale
                        reasons.append(f"LATE SIGNAL")

                # --- STEP 4: Archetype Synergy & 'Glue Cards' ---
                is_on_lane = (
                    all(c in self.main_colors for c in card_colors)
                    if card_colors
                    else True
                )
                if len(self.main_colors) >= 2:
                    arch_wr = float(
                        card.get("deck_colors", {})
                        .get(self.main_archetype, {})
                        .get("gihwr", 0.0)
                    )
                    if arch_wr > 0.0:
                        delta = arch_wr - raw_gihwr

                        # GLUE CARD DETECTION:
                        # If a Common/Uncommon heavily outperforms its global average in our specific lane,
                        # it is an archetype "Glue Card" and gets a massive multiplier to push it over generic Rares.
                        rarity = str(card.get("rarity", "common")).lower()
                        if (
                            delta >= ENGINE_PARAMS.synergy.glue_delta_threshold
                            and rarity in ENGINE_PARAMS.synergy.glue_rarities
                        ):
                            synergy_bonus = delta * ENGINE_PARAMS.synergy.glue_multiplier
                            reasons.append(f"Archetype Glue (+{synergy_bonus:.1f})")
                        elif delta >= ENGINE_PARAMS.synergy.synergy_delta_threshold:
                            synergy_bonus = delta * ENGINE_PARAMS.synergy.synergy_multiplier
                            reasons.append(f"Archetype Synergy (+{synergy_bonus:.1f})")

                    if is_on_lane:
                        base_score *= (
                            ENGINE_PARAMS.synergy.on_lane_needs_playables_mult
                            if needs_playables
                            else ENGINE_PARAMS.synergy.on_lane_mult
                        )

                # --- STEP 5: Value Over Replacement (VOR) ---
                if pack_number == 1 and card_colors and len(card_colors) == 1:
                    c = card_colors[0]
                    texture = getattr(self.metrics, "format_texture", {}).get(c, {})
                    if texture and raw_gihwr >= (
                        self.global_mean
                        - ENGINE_PARAMS.targets.playable_std_floor * self.global_std
                    ):
                        tags = card.get("tags", [])
                        cmc = get_functional_cmc(card)

                        roles_to_check = []
                        if "Creature" in card.get("types", []) and cmc <= ENGINE_PARAMS.targets.early_cmc_max:
                            roles_to_check.append(("2-drop", "2-Drops"))
                        if "removal" in tags:
                            roles_to_check.append(("removal", "Removal"))
                        if "evasion" in tags:
                            roles_to_check.append(("evasion", "Evasion"))

                        for role_key, role_name in roles_to_check:
                            count = texture.get(role_key, 99)
                            if count <= ENGINE_PARAMS.vor.scarce_role_count:
                                vor_bonus = ENGINE_PARAMS.vor.bonus
                                power_bonus += vor_bonus
                                reasons.append(
                                    f"High VOR: Scarce {c} {role_name} (+{vor_bonus:.0f})"
                                )
                            elif count >= ENGINE_PARAMS.vor.replaceable_role_count:
                                power_bonus -= ENGINE_PARAMS.vor.replaceable_penalty
                                reasons.append(f"Highly Replaceable {role_name}")

                # --- STEP 6: Castability (Pip-Sensitive Discipline & Premium Splashing) ---
                cast_mult, cast_reason = self._calculate_castability_v5(
                    card, pack_number, safe_pick, z_score
                )
                if cast_reason:
                    reasons.append(cast_reason)

                # --- STEP 7: Composition & Synergies ---
                role_mult, role_reason = self._calculate_composition_bonus(
                    card, pack_number
                )
                if role_reason:
                    reasons.append(role_reason)

                # --- STEP 7.5: Late Draft Deck Improvement ---
                deck_improvement_bonus = 0.0
                if pack_number >= 3 and len(self.pool) >= ENGINE_PARAMS.deck.min_pool_for_deck_scoring:
                    try:
                        test_pool = self.pool + [card]
                        new_score = self._get_fast_best_deck_score(
                            test_pool, self.color_options
                        )
                        improvement = new_score - self.base_deck_score
                        if improvement > ENGINE_PARAMS.deck.improvement_threshold:
                            deck_improvement_bonus = improvement * ENGINE_PARAMS.deck.improvement_mult
                            reasons.append(
                                f"Improves Best Deck (+{deck_improvement_bonus:.1f})"
                            )
                    except Exception as e:
                        logger.warning(f"Advisor deck improvement scoring error: {e}")

                # --- STEP 8: Wheel logic ---
                rank_in_pack = pack_ranks.get(name, 99)
                wheel_mult, _, wheel_pct = self._check_relative_wheel(
                    card, safe_pick, rank_in_pack
                )

                # === MASTER ALGORITHM ===
                final_score = (
                    (base_score + power_bonus + synergy_bonus + deck_improvement_bonus)
                    * cast_mult
                    * role_mult
                    * wheel_mult
                )

                is_basic_land = name in constants.BASIC_LANDS or (
                    "Basic" in card.get("types", []) and "Land" in card.get("types", [])
                )

                if is_basic_land:
                    final_score = 0.0
                    if len(pack_cards) == 1:
                        reasons = ["This is the only available option."]
                    else:
                        reasons = ["Basic Land (Skip)"]

                if iwd_mult > 1.0 and final_score > 0:
                    reasons.insert(0, "TRUE BOMB (High IWD)")

                recommendations.append(
                    Recommendation(
                        card_name=name,
                        base_win_rate=raw_gihwr,
                        contextual_score=round(max(0.0, final_score), 1),
                        z_score=round(z_score, 2),
                        cast_probability=cast_mult,
                        wheel_chance=wheel_pct,
                        functional_cmc=get_functional_cmc(card),
                        reasoning=reasons,
                        is_elite=(
                            (
                                z_score >= ENGINE_PARAMS.targets.bomb_z_score
                                and cast_mult > ENGINE_PARAMS.bomb.elite_castability_floor
                            )
                            if not is_basic_land
                            else False
                        ),
                        archetype_fit=(
                            self.main_archetype if is_on_lane else "Splash/Speculative"
                        ),
                        tags=card.get("tags", []),
                    )
                )
            except Exception as e:
                logger.warning(f"Advisor error: {e}")
                continue

        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _pack_win_rate_sort_key(self, card: CardData) -> float:
        """Sort key for pack cards: dirty values fall to 0.0; a structurally
        broken card (e.g. None) still propagates instead of being masked."""
        try:
            return float(
                card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                or 0.0
            )
        except _DIRTY_DATA_EXC:
            return 0.0

    def _identify_main_colors(self) -> Tuple[List[str], Dict[str, float]]:
        color_weights, color_counts = (
            {c: 0.0 for c in constants.CARD_COLORS},
            {c: 0 for c in constants.CARD_COLORS},
        )
        playable_threshold, total_pool_size = (
            self.global_mean - ENGINE_PARAMS.targets.playable_std_floor * self.global_std,
            len(self.pool),
        )
        for idx, c in enumerate(self.pool):
            try:
                colors = c.get("colors", [])
                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )
                if "Land" not in c.get("types", []):
                    for col in colors:
                        color_counts[col] += 1
                if wr < playable_threshold:
                    continue
                base_points = max(
                    ENGINE_PARAMS.lane.color_weight_floor,
                    ENGINE_PARAMS.lane.color_weight_base
                    + ENGINE_PARAMS.lane.color_weight_gain
                    * ((wr - self.global_mean) / self.global_std),
                )
                recency_mult = ENGINE_PARAMS.lane.recency_base + (
                    ENGINE_PARAMS.lane.recency_range * (idx / max(1, total_pool_size))
                )
                for color in colors:
                    if color in color_weights:
                        color_weights[color] += base_points * recency_mult
            except _DIRTY_DATA_EXC:
                continue
        sorted_w = sorted(color_weights.items(), key=lambda x: x[1], reverse=True)
        main_colors = []
        if (
            total_pool_size >= ENGINE_PARAMS.lane.min_pool_for_lane
            and sum(color_counts.values()) > ENGINE_PARAMS.lane.min_color_total
        ):
            threshold = sum(color_counts.values()) * ENGINE_PARAMS.lane.color_share_threshold
            leader_set = [
                v[0]
                for v in sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[
                    :2
                ]
                if v[1] > 0
            ]
            for col, weight in sorted_w:
                if col in leader_set or color_counts[col] >= threshold:
                    main_colors.append(col)
        else:
            for col, weight in sorted_w:
                if weight >= ENGINE_PARAMS.lane.weight_floor:
                    main_colors.append(col)
        return main_colors[:3], color_counts

    def _analyze_pool(self) -> Dict[str, Any]:
        early_plays, hard_removal_count, fixing_count, splash_targets = 0, 0, 0, set()
        off_color_playables = 0
        creature_count = 0
        heavy_drops = 0
        artifacts = 0
        graveyard_enablers = 0
        counters_enablers = 0

        for c in self.pool:
            try:
                cmc, tags = get_functional_cmc(c), c.get("tags", [])
                colors = c.get("colors", [])
                types = c.get("types", [])

                if "Creature" in types:
                    creature_count += 1
                    if cmc <= ENGINE_PARAMS.targets.early_cmc_max:
                        early_plays += 1

                if cmc >= ENGINE_PARAMS.targets.heavy_cmc_min and "Land" not in types:
                    heavy_drops += 1

                if (
                    "Artifact" in types
                    or "synergy_artifacts" in tags
                    or "token_maker" in tags
                ):
                    artifacts += 1
                if "synergy_graveyard" in tags or "card_advantage" in tags:
                    graveyard_enablers += 1
                if "synergy_counters" in tags:
                    counters_enablers += 1

                if "removal" in tags:
                    hard_removal_count += 1
                    if cmc <= ENGINE_PARAMS.targets.early_cmc_max and "Creature" not in types:
                        early_plays += 1
                if "fixing_ramp" in tags or ("Land" in types and len(colors) > 1):
                    fixing_count += 1

                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )

                is_off_color = False
                if self.main_colors and colors:
                    is_off_color = not all(col in self.main_colors for col in colors)

                if is_off_color and wr > (
                    self.global_mean
                    - ENGINE_PARAMS.targets.playable_std_floor * self.global_std
                ):
                    off_color_playables += 1

                if wr > (self.global_mean + (ENGINE_PARAMS.lane.splash_z * self.global_std)):
                    for col in colors:
                        if self.main_colors and col not in self.main_colors:
                            splash_targets.add(col)
            except _DIRTY_DATA_EXC:
                continue
        return {
            "early_plays": early_plays,
            "hard_removal_count": hard_removal_count,
            "fixing_count": fixing_count,
            "splash_targets": splash_targets,
            "off_color_playables": off_color_playables,
            "creature_count": creature_count,
            "heavy_drops": heavy_drops,
            "artifacts": artifacts,
            "graveyard_enablers": graveyard_enablers,
            "counters_enablers": counters_enablers,
        }

    def _calculate_composition_bonus(self, card: CardData, pack: int) -> Tuple[float, str]:
        tags, cmc = card.get("tags", []), get_functional_cmc(card)
        types = card.get("types", [])

        # 1. Curve and Heavy Drops Check
        if (
            cmc >= ENGINE_PARAMS.targets.heavy_cmc_min
            and self.pool_metrics["heavy_drops"] >= ENGINE_PARAMS.composition.heavy_drops_threshold
            and "Land" not in types
        ):
            return ENGINE_PARAMS.composition.heavy_drops_mult, "Curve Too Heavy"

        # 2. Creature Quota Check
        if pack >= 2 and "Creature" in types:
            projected_creatures = self.pool_metrics["creature_count"] * (
                ENGINE_PARAMS.targets.total_picks / max(1, len(self.pool))
            )
            if projected_creatures < ENGINE_PARAMS.composition.creature_projection_floor:
                return ENGINE_PARAMS.composition.creature_mult, "Critical: Needs Creatures"

        # 3. Synergy (A+B) Checks
        if (
            "synergy_artifacts" in tags
            and self.pool_metrics["artifacts"] >= ENGINE_PARAMS.composition.artifact_synergy_count
        ):
            return ENGINE_PARAMS.composition.synergy_mult, "Artifact Synergy"
        if (
            "synergy_graveyard" in tags
            and self.pool_metrics["graveyard_enablers"] >= ENGINE_PARAMS.composition.graveyard_synergy_count
        ):
            return ENGINE_PARAMS.composition.synergy_mult, "Graveyard Synergy"
        if (
            "synergy_counters" in tags
            and self.pool_metrics["counters_enablers"] >= ENGINE_PARAMS.composition.counters_synergy_count
        ):
            return ENGINE_PARAMS.composition.synergy_mult, "Counters Synergy"

        # 4. Fixing Hunger
        if "Land" in types or "fixing_ramp" in tags:
            off_color_playables = self.pool_metrics.get("off_color_playables", 0)
            fixing_count = self.pool_metrics.get("fixing_count", 0)

            if (
                pack >= 2
                and off_color_playables > 0
                and fixing_count <= off_color_playables
            ):
                return ENGINE_PARAMS.composition.fixing_hunger_mult, "Critical: Needs Fixing"

            if any(
                c in self.pool_metrics["splash_targets"] for c in card.get("colors", [])
            ):
                return ENGINE_PARAMS.composition.splash_enabler_mult, "Enables Bomb Splash"

            return (
                (ENGINE_PARAMS.composition.premium_fixing_mult, "Premium Fixing")
                if pack == 1 and len(card.get("colors", [])) > 1
                else (1.0, "")
            )

        # 5. Removal Check
        if "removal" in tags:
            if (
                pack >= 2
                and self.pool_metrics["hard_removal_count"]
                < ENGINE_PARAMS.targets.target_hard_removal
            ):
                return ENGINE_PARAMS.composition.removal_hunger_mult, "Critical: Needs Removal"
            elif self.pool_metrics["hard_removal_count"] > ENGINE_PARAMS.composition.removal_saturated_count:
                return ENGINE_PARAMS.composition.removal_saturated_mult, "Removal Saturated"

        # 6. Early Interaction
        if cmc <= ENGINE_PARAMS.targets.early_cmc_max and ("Creature" in types or "removal" in tags):
            projected = self.pool_metrics["early_plays"] * (
                ENGINE_PARAMS.targets.total_picks / max(1, len(self.pool))
            )
            if projected < ENGINE_PARAMS.targets.target_early_plays:
                return (
                    (
                        1.0
                        + min(
                            ENGINE_PARAMS.composition.early_plays_mult_cap,
                            (ENGINE_PARAMS.targets.target_early_plays - projected)
                            * ENGINE_PARAMS.composition.early_plays_scale,
                        ),
                        "Critical: Needs 2-Drops",
                    )
                    if pack >= 2
                    else (ENGINE_PARAMS.composition.early_plays_pack1_mult, "Curve Foundation")
                )
        return 1.0, ""

    def _calculate_castability_v5(
        self, card: CardData, pack: int, pick: int, z_score: float
    ) -> Tuple[float, str]:
        mana_cost = card.get("mana_cost", "")
        card_colors = card.get("colors", [])
        top_2_lane = self.main_colors[:2]

        if mana_cost:
            off_color_pips = 0
            is_on_lane = True
            pips = re.findall(r"\{(.*?)\}", mana_cost)
            for pip in pips:
                options = [c for c in pip.split("/") if c in "WUBRG"]
                if not options:
                    continue
                if any(opt in top_2_lane for opt in options):
                    continue
                else:
                    off_color_pips += 1
                    is_on_lane = False
        else:
            is_on_lane = (
                all(c in top_2_lane for c in card_colors) if card_colors else True
            )
            off_color_pips = 0 if is_on_lane else 1

        if pack == 1:
            if is_on_lane:
                return 1.0, ""
            pressure = 1.0 - (
                max(
                    0,
                    (
                        (pack - 1) * ENGINE_PARAMS.targets.picks_per_pack
                        + (pick - 1)
                    )
                    - ENGINE_PARAMS.castability.p1_grace_picks,
                )
                * ENGINE_PARAMS.castability.p1_decay_per_pick
            )
            return (
                (
                    max(
                        ENGINE_PARAMS.castability.p1_gold_pip_floor,
                        pressure - ENGINE_PARAMS.castability.p1_gold_extra_penalty,
                    ),
                    "Off-Color Gold",
                )
                if len(card_colors) > 1 and off_color_pips > 0
                else (max(ENGINE_PARAMS.castability.p1_off_color_floor, pressure), "Off-Color")
            )

        if not is_on_lane:
            if (
                pack >= 2
                and off_color_pips >= 2
                and self.pool_metrics["fixing_count"]
                < ENGINE_PARAMS.castability.double_pip_fixing_floor
            ):
                return ENGINE_PARAMS.castability.uncastable_double_pip_mult, "Uncastable (Double Pip)"

            splash_colors = [c for c in card_colors if c not in top_2_lane]
            has_specific_fixing = (
                all(self.fixing_map.get(c, 0) > 0 for c in splash_colors)
                if splash_colors
                else False
            )

            is_premium_removal = (
                "removal" in card.get("tags", [])
                and z_score >= ENGINE_PARAMS.castability.premium_removal_z
            )

            # Allow premium 1-for-1s to be splashed just like game-winning bombs
            if z_score >= ENGINE_PARAMS.targets.bomb_z_score or is_premium_removal:
                if off_color_pips == 1:
                    if has_specific_fixing or self.pool_metrics["fixing_count"] >= (
                        ENGINE_PARAMS.castability.splash_fixing_floor_p3
                        if pack == 3
                        else ENGINE_PARAMS.castability.splash_fixing_floor_p2
                    ):
                        reason = (
                            "Bomb Splash"
                            if z_score >= ENGINE_PARAMS.targets.bomb_z_score
                            else "Premium Removal Splash"
                        )
                        return (
                            (
                                ENGINE_PARAMS.castability.bomb_splash_mult_p3
                                if pack == 3
                                else ENGINE_PARAMS.castability.bomb_splash_mult_p2
                            ),
                            reason,
                        )
                elif (
                    off_color_pips == 2
                    and get_functional_cmc(card) >= ENGINE_PARAMS.targets.heavy_cmc_min
                    and z_score >= ENGINE_PARAMS.targets.bomb_z_score
                ):
                    if self.pool_metrics["fixing_count"] >= ENGINE_PARAMS.castability.greedy_fixing_floor:
                        return ENGINE_PARAMS.castability.greedy_splash_mult, "Greedy Bomb Splash"

            if off_color_pips == 1 and has_specific_fixing:
                return ENGINE_PARAMS.castability.splashable_mult, "Splashable"

            return (
                ENGINE_PARAMS.castability.off_color_mult_p3
                if pack == 3
                else ENGINE_PARAMS.castability.off_color_mult_p2,
                "Off-Color",
            )
        return 1.0, ""

    def _check_relative_wheel(
        self, card: CardData, pick: int, rank_in_pack: int
    ) -> Tuple[float, str, float]:
        if pick >= ENGINE_PARAMS.wheel.cutoff_pick:
            return 1.0, "", 0.0
        try:
            alsa = float(
                card.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0)
            )
            if alsa <= pick:
                return 1.0, "", 0.0
            coeffs = constants.WHEEL_COEFFICIENTS[
                min(pick - 1, ENGINE_PARAMS.wheel.coeff_index_cap)
            ]
            context_prob = float(np.polyval(coeffs, alsa))
            if rank_in_pack == 0:
                context_prob *= ENGINE_PARAMS.wheel.rank0_mult
            elif rank_in_pack <= 2:
                context_prob *= ENGINE_PARAMS.wheel.rank_top2_mult
            final_prob = max(0.0, min(100.0, context_prob))
            return (
                (
                    ENGINE_PARAMS.wheel.mult,
                    f"Wheels ~{final_prob:.0f}%",
                    final_prob,
                )
                if final_prob >= ENGINE_PARAMS.wheel.prob_threshold
                and rank_in_pack >= ENGINE_PARAMS.wheel.min_rank
                else (1.0, "", final_prob)
            )
        except _DIRTY_DATA_EXC:
            return 1.0, "", 0.0

    def _calculate_weighted_score(self, card: CardData, pick_number: int) -> float:
        try:
            stats = card.get("deck_colors", {})
            global_wr = float(stats.get("All Decks", {}).get("gihwr", 0.0))
            arch_weight = min(
                ENGINE_PARAMS.progressive.arch_weight_max,
                ENGINE_PARAMS.progressive.arch_weight_base
                + (pick_number / ENGINE_PARAMS.targets.total_picks)
                * ENGINE_PARAMS.progressive.arch_weight_ramp,
            )
            arch_stats = stats.get(self.main_archetype, {})
            arch_wr = float(arch_stats.get("gihwr", global_wr))

            # BAYESIAN SMOOTHING: Confidently blend global & archetype win rates based on sample size
            samples = int(arch_stats.get("samples", 0))
            confidence = min(1.0, samples / ENGINE_PARAMS.progressive.confidence_denominator)
            trusted_arch_wr = (arch_wr * confidence) + (global_wr * (1.0 - confidence))

            blended_wr = (
                (global_wr * (1.0 - arch_weight)) + (trusted_arch_wr * arch_weight)
                if (arch_wr > 0 and samples >= ENGINE_PARAMS.progressive.min_arch_samples)
                else global_wr
            )

            base_score = max(
                0.0,
                ENGINE_PARAMS.progressive.base_score_offset
                + (
                    (blended_wr - self.global_mean)
                    / max(ENGINE_PARAMS.progressive.std_floor, self.global_std)
                )
                * ENGINE_PARAMS.progressive.base_score_scale,
            )

            # SIGNAL TIE-BREAKER
            card_colors = card.get("colors", [])
            if self.signals and card_colors:
                signal_strength = sum(self.signals.get(c, 0.0) for c in card_colors)
                if signal_strength > ENGINE_PARAMS.progressive.signal_threshold:
                    base_score *= ENGINE_PARAMS.progressive.signal_boost

            return base_score
        except _DIRTY_DATA_EXC:
            return 0.0

    def _get_fast_best_deck_score(
        self, pool: List[CardData], color_options: List[List[str]]
    ) -> float:
        from src.advisor.deck_builder import (
            build_variant_consistency,
            build_variant_greedy,
            build_variant_curve,
            build_variant_soup,
        )
        from src.advisor.deck_scorer import calculate_holistic_score

        best_score = 0.0
        for main_colors in color_options:
            for builder in [build_variant_consistency, build_variant_curve]:
                deck = builder(pool, main_colors, self.metrics)
                if deck:
                    score, _ = calculate_holistic_score(
                        deck, main_colors, len(pool), self.metrics
                    )
                    if score > best_score:
                        best_score = score

            deck, splash = build_variant_greedy(pool, main_colors, self.metrics)
            if deck:
                target_colors = main_colors + [splash] if splash else main_colors
                score, _ = calculate_holistic_score(
                    deck, target_colors, len(pool), self.metrics
                )
                if score > best_score:
                    best_score = score

        deck, soup_colors = build_variant_soup(pool, self.metrics)
        if deck:
            target_colors = soup_colors[:3] if soup_colors else ["All Decks"]
            score, _ = calculate_holistic_score(
                deck, target_colors, len(pool), self.metrics
            )
            if score > best_score:
                best_score = score

        return best_score
