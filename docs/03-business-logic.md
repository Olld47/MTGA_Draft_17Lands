# Business Logic & Scoring Specification: "Compositional Brain" (v5.5 Pro)

**Version:** 5.5 | **Architecture:** Pro-Tour Context Engine & Archetype Gravity

> **Calibration debt (read before tuning).** Every tuned number in the scoring
> sections below lives in **`ENGINE_PARAMS`** (`src/advisor/engine.py`, module
> constant) — this spec references field names, it does not restate values.
> These values are **heuristic hand-tuning with no backtest / regression
> harness**: changing a coefficient (or the branch that consumes it) cannot
> currently be measured against recommendation quality. See
> `ENGINE_PARAMS_CALIBRATION`. If you change a value, change it in exactly one
> place (`ENGINE_PARAMS`), not here and not in the engine body.

---

## 1. Introduction

The v5.5 Engine abandons rigid heuristics in favor of a fluid, context-aware model. It simulates high-level drafting by shifting its focus from global card quality to specific archetype performance as the draft progresses, while enforcing a sliding commitment curve to prevent late-draft indecision.

---

## 2. Lane Detection (Sunk Cost Evasion)

The engine does not "lock in" colors based on the first few picks. It uses recency bias to ensure that recent high-quality picks outweigh early mistakes.

- **Formula:** `Score = Base Z-Score * Recency Multiplier`
- **Recency Multiplier:** scales linearly from `ENGINE_PARAMS.lane.recency_base`x for the first drafted card up to `ENGINE_PARAMS.lane.recency_base` + `ENGINE_PARAMS.lane.recency_range`x for the most recent card.
- **Effect:** If you pivot from Red to Blue in Pack 2, the "Gravity" of your Red picks decays rapidly, allowing the Advisor to suggest the correct Blue cards for your current UX reality.

---

## 3. Archetype Gravity (Pair Performance)

Instead of evaluating a card globally (e.g., its win rate across all 17Lands users), the engine identifies your leading "Color Pair" (e.g., Blue-Black/UB) and prioritizes data for that specific pairing.

- **Gravity Logic:** The engine scores all 10 possible color pairs based on the weighted power of cards in your pool and the presence of "Gold" cards that reward specific pairs.
- **Progressive Weighting:** the archetype share of the blended score starts at `ENGINE_PARAMS.progressive.arch_weight_base` (global win rate dominates early) and grows by `ENGINE_PARAMS.progressive.arch_weight_ramp` per pick toward `ENGINE_PARAMS.progressive.arch_weight_max`; archetype stats are blended via Bayesian smoothing gated on `ENGINE_PARAMS.progressive.confidence_denominator` samples and ignored below `ENGINE_PARAMS.progressive.min_arch_samples`.
- **Synergy Payoff:** if a card performs more than `ENGINE_PARAMS.synergy.synergy_delta_threshold`% better in your specific color pair than its global average, it receives an **Archetype Synergy** bonus of delta × `ENGINE_PARAMS.synergy.synergy_multiplier`.

---

## 4. Sliding Commitment Curve (Lane Pressure)

To prevent the engine from suggesting off-color cards too late in the draft, it applies a sliding scale of pressure based on the pick number. Tuned values: `ENGINE_PARAMS.castability` (grace window, per-pick decay, floors, and pack 2/3 off-color multipliers).

| Phase             | Picks                          | Logic Name   | Behavior                                                                                                                  |
| :---------------- | :----------------------------- | :----------- | :------------------------------------------------------------------------------------------------------------------------ |
| **P1 Picks 1-7**  | Stay Open                      | Neutral      | No penalties for off-color cards (`ENGINE_PARAMS.castability.p1_grace_picks` picks of grace). Encourages taking the best card regardless of color. |
| **P1 Picks 8-15** | Lane Pressure                  | Linear Decay | Applies a `ENGINE_PARAMS.castability.p1_decay_per_pick` penalty multiplier per pick past grace to off-color cards. By the end of Pack 1 they are suppressed toward `ENGINE_PARAMS.castability.p1_off_color_floor`. |
| **Pack 2**        | Soft Lock                      | Disciplined  | Off-color cards drop to `ENGINE_PARAMS.castability.off_color_mult_p2` unless they are massive bombs (splash rules in §8). |
| **Pack 3**        | Hard Lock                      | Committed    | Off-color cards drop to `ENGINE_PARAMS.castability.off_color_mult_p3` to ensure the final pool is playable.               |

---

## 5. Compositional Math & Dynamic Needs

Modern Limited is dictated by "Mana Velocity" and "Mana Stability."

- **Velocity Target:** `ENGINE_PARAMS.targets.target_early_plays`+ "Early Plays" (CMC ≤ `ENGINE_PARAMS.targets.early_cmc_max` Creatures or cheap interaction).
- **Velocity Hunger:** The engine projects your final early-play count based on your current pool relative to the remaining picks in the draft. If the projection is below target entering Pack 2, early plays receive a "Critical: Needs 2-Drops" multiplier up to `1.0 + ENGINE_PARAMS.composition.early_plays_mult_cap`, scaled by `ENGINE_PARAMS.composition.early_plays_scale` per missing early play (Pack 1 gets the milder `ENGINE_PARAMS.composition.early_plays_pack1_mult`).
- **Top-Heavy Penalty:** If you have `ENGINE_PARAMS.composition.heavy_drops_threshold`+ cards costing `ENGINE_PARAMS.targets.heavy_cmc_min`+ mana, expensive cards receive a `ENGINE_PARAMS.composition.heavy_drops_mult` dampening multiplier to prevent "clunky" hands.
- **Dynamic Fixing Hunger:** The engine actively monitors whether you are drafting a highly synergistic 2-color deck, or moving towards a "Good Stuff" 3/4-color splash strategy. If the number of drafted off-color playables exceeds your dedicated fixing tools (dual lands, treasures, dorks) by Pack 2, fixing cards receive a massive `ENGINE_PARAMS.composition.fixing_hunger_mult` "Critical: Needs Fixing" multiplier.

---

## 6. Value Over Replacement (VOR) & "Glue Cards"

The v5 engine moves beyond raw win rates by pre-calculating the **Format Texture** of a set when it loads.

- **Role Scarcity (VOR):** The engine analyzes the dataset to count how many "Playable" (WR > baseline = `ENGINE_PARAMS.targets.playable_std_floor` std below mean) Commons and Uncommons exist for critical roles (e.g., Removal, 2-Drops) in each color.
  - If a user sees a Playable Red 2-Drop, and the engine knows there are at most `ENGINE_PARAMS.vor.scarce_role_count` viable Red 2-drops in the entire set, it applies a `ENGINE_PARAMS.vor.bonus` **High VOR** bonus.
  - If a role has `ENGINE_PARAMS.vor.replaceable_role_count`+ playables, cards in it lose `ENGINE_PARAMS.vor.replaceable_penalty` points (Highly Replaceable).
- **Archetype Glue:** If a Common/Uncommon (`ENGINE_PARAMS.synergy.glue_rarities`) has a win rate in the user's specific color pair that is more than `ENGINE_PARAMS.synergy.glue_delta_threshold`% higher than its global average, it is classified as "Archetype Glue." It receives a delta × `ENGINE_PARAMS.synergy.glue_multiplier` bonus to force it to outscore generic Rares.

---

## 7. Semantic Role Analysis (Interaction & Tricks)

The app parses Scryfall community tags to understand a card's functional role.

- **Hard Removal Quota:** Targets `ENGINE_PARAMS.targets.target_hard_removal`+ removal spells. If the pool is lacking entering Pack 2, interaction cards receive a `ENGINE_PARAMS.composition.removal_hunger_mult` panic multiplier. Conversely, if you have `ENGINE_PARAMS.composition.removal_saturated_count`+ removal spells, new ones are penalized (`ENGINE_PARAMS.composition.removal_saturated_mult`).
- **Trick Diminishing Returns:** documented intent — combat tricks and Auras are intended to be capped with a diminishing-returns penalty, but that branch is **not yet wired into `engine.py`** (no trick cap currently exists; the tuning constant is deliberately absent from `ENGINE_PARAMS` until the feature lands).

---

## 8. True Bomb Detection (IWD Injection)

- **Logic:** A card is tagged as a **TRUE BOMB** only if its Z-Score is above `ENGINE_PARAMS.bomb.iwd_bomb_z` AND its **Improvement When Drawn (IWD)** is above `ENGINE_PARAMS.targets.iwd_premium_threshold`%. TRUE BOMBs then multiply their power bonus by `ENGINE_PARAMS.bomb.iwd_mult`, where the raw power bonus itself scales as Z × `ENGINE_PARAMS.bomb.power_bonus_scale` once Z clears `ENGINE_PARAMS.bomb.power_bonus_min_z`.
- **Effect:** Distinguishes between "Great Filler" and "Game-Warping Power." These cards receive a power bonus that overrides the Sliding Commitment Curve, allowing for late-draft splashes (`ENGINE_PARAMS.targets.bomb_z_score` marks the elite threshold for both TRUE BOMB and the splash rules below).
- **Splash tiers** (per `ENGINE_PARAMS.castability`): bombs splash at `ENGINE_PARAMS.castability.bomb_splash_mult_p2` / `ENGINE_PARAMS.castability.bomb_splash_mult_p3` once fixing clears `ENGINE_PARAMS.castability.splash_fixing_floor_p2` / `ENGINE_PARAMS.castability.splash_fixing_floor_p3`; premium removal splashes at the same tier; a greedy two-pip bomb splashes at `ENGINE_PARAMS.castability.greedy_splash_mult` with `ENGINE_PARAMS.castability.greedy_fixing_floor` fixing; a single off-lane pip with dedicated fixing splashes at `ENGINE_PARAMS.castability.splashable_mult`. Double off-lane pips with no fixing are uncastable (`ENGINE_PARAMS.castability.uncastable_double_pip_mult`).

---

## 9. Interactive Deck Building & AI Optimization

### A. Frank Karsten Mana Base Engine ("Auto-Lands")

Users can click a single button to perfectly balance their lands using Pro-Tour heuristics:

- **Pip Volume Calculation:** Counts the exact number of specific colored mana symbols.
- **Universal Fixer Detection:** Explicitly identifies Treasure-makers, Fetchlands, and "Any Color" dorks.
- **Hybrid Mana Resolution:** Correctly categorizes hybrid mana (e.g., `{W/U}`) towards whichever core color the deck favors.
- **Splash Starvation Protection:** Strictly caps basic land allocations for splash colors to prevent main-color starvation.

### B. Monte Carlo Simulation

Evaluates the user's custom deck by running a 10,000-game Monte Carlo simulation.

- Applies pro-level London mulligan heuristics.
- Calculates probabilities for `cast_t2/t3/t4`, Mana Screw, Mana Flood, and Color Screw.

### C. On-Demand AI Auto-Optimizer

Users can actively "brute-force" permutations of their current deck configuration via a dedicated background task.

- It generates variations: **Play 18 Lands**, **Play 16 Lands**, **Curve Lower**, **Power Up**, and **Fix Mana Base** (swapping colorless utility lands for core colored basics).
- It simulates thousands of games for each variation simultaneously.
- Selects the deck configuration that maximizes `cast_t2/t3/t4` + `curve_out` while heavily penalizing `color_screw`, `mana_screw`, and `flood`.

---

## 10. Post-Draft Analysis & Dashboard

Transitions into a Post-Draft Recap tracking:

- **Holistic Pool Grading:** Evaluated on a realistic 100-point scale.
- **Steals & Reaches:** Compares exact Pack/Pick against global ALSA/ATA. The pack-1 "wheel" discount lives in `ENGINE_PARAMS.wheel` (pick cutoff, rank multipliers, and the wheeling-card multiplier) and is driven by `WHEEL_COEFFICIENTS` in `src/constants/wheel.py` (re-exported by the `src/constants` package aggregator).
- **Tribal Synergy:** Dynamically queries the MTGA SQLite database for `SubType` enumerators to highlight tribal synergies.

---

## 11. Sealed Studio & Shell Generation

Added in v4.15, the application includes a dedicated workspace for Sealed deckbuilding.

- **AI Shell Generator:** Because Sealed pools contain 90+ cards, it's difficult to find the correct lane manually. The AI evaluates the pool and generates the Top 3 mathematically optimal 40-card shells on demand:
  1. **Best 2-Color:** The most consistent 2-color pair based on raw power and curve.
  2. **Greedy Splash:** Automatically forces the best off-color Bomb into the deck, strictly allocating appropriate fixing lands/treasures.
  3. **Aggro/Tempo:** Filters the secondary best color pair through a strict CMC penalty to build a low-to-the-ground deck.
- **Visual Deckbuilder:** A 1-to-1 recreation of the MTGA client's column-based (CMC sorted) drag-and-drop workspace, complete with real-time image caching via the `ThreadPoolExecutor`.
