"""
src/advisor/simulator.py
Monte Carlo Simulation Engine for evaluating deck consistency and mana bases.
"""

import random
import re
from src.card_logic import get_functional_cmc


def simulate_deck(deck_list, iterations=10000):
    flat_deck = []
    for c in deck_list:
        is_land = "Land" in c.get("types", [])
        is_ramp = False
        text = str(c.get("oracle_text", c.get("text", ""))).lower()
        if (
            "fixing_ramp" in c.get("tags", [])
            or "any color" in text
            or "treasure" in text
        ):
            is_ramp = True

        colors_produced = set()
        if is_land or is_ramp:
            colors_produced.update(c.get("colors", []))
            if "any color" in text or "fixing_ramp" in c.get("tags", []):
                colors_produced.update(["W", "U", "B", "R", "G"])

        pips = []
        if not is_land:
            cost = c.get("mana_cost", "")
            matches = re.findall(r"\{(.*?)\}", cost)
            for pip in matches:
                opts = [opt for opt in pip.split("/") if opt in "WUBRG"]
                if opts:
                    pips.append(opts)

        for _ in range(int(c.get("count", 1))):
            flat_deck.append(
                {
                    "is_land": is_land,
                    "is_ramp": is_ramp and not is_land,
                    "is_removal": "removal" in c.get("tags", []),
                    "colors_produced": colors_produced,
                    "cmc": get_functional_cmc(c),
                    "pips": pips,
                }
            )

    if len(flat_deck) < 40:
        return None

    stats = {
        "mulligans": 0,
        "screw_t3": 0,
        "screw_t4": 0,
        "flood_t5": 0,
        "cast_t2": 0,
        "cast_t3": 0,
        "cast_t4": 0,
        "curve_out": 0,
        "removal_t4": 0,
        "color_screw_t3": 0,
        "avg_hand_size": 0,
    }

    for _ in range(iterations):
        random.shuffle(flat_deck)

        mull_count = 0
        hand = flat_deck[0:7]
        lands = sum(1 for c in hand if c["is_land"])

        if lands < 2 or lands > 5:
            mull_count = 1
            hand = flat_deck[7:14]
            lands = sum(1 for c in hand if c["is_land"])
            if lands < 2 or lands > 4:
                mull_count = 2
                hand = flat_deck[14:21]

        if mull_count > 0:
            stats["mulligans"] += 1
        kept_size = 7 - mull_count
        stats["avg_hand_size"] += kept_size
        start_idx = mull_count * 7
        current_7 = flat_deck[start_idx : start_idx + 7]

        if kept_size < 7:
            current_7.sort(key=lambda x: x["cmc"])
        kept_hand = current_7[:kept_size]
        deck_rest = flat_deck[start_idx + 7 :]
        game_state = kept_hand + deck_rest

        t2_state, t3_state = game_state[: kept_size + 1], game_state[: kept_size + 2]
        t4_state, t5_state = game_state[: kept_size + 3], game_state[: kept_size + 4]

        lands_t3 = [c for c in t3_state if c["is_land"]]
        if len(lands_t3) < 3:
            stats["screw_t3"] += 1

        lands_t4 = [c for c in t4_state if c["is_land"]]
        if len(lands_t4) < 4:
            stats["screw_t4"] += 1

        lands_t5 = sum(1 for c in t5_state if c["is_land"])
        if lands_t5 >= 6:
            stats["flood_t5"] += 1

        if any(c["is_removal"] for c in t4_state):
            stats["removal_t4"] += 1

        def can_cast(state, target_cmc):
            available_mana = []
            for c in state:
                if c["is_land"]:
                    available_mana.append(c)
                elif c["is_ramp"] and c["cmc"] < target_cmc:
                    available_mana.append(c)

            if len(available_mana) < target_cmc:
                return False

            spells = [c for c in state if not c["is_land"] and c["cmc"] == target_cmc]
            if not spells:
                return False

            color_sources = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
            for m in available_mana:
                for c in m["colors_produced"]:
                    color_sources[c] += 1

            for s in spells:
                castable = True
                temp_sources = color_sources.copy()
                for pip_opts in s["pips"]:
                    paid = False
                    for opt in pip_opts:
                        if temp_sources.get(opt, 0) > 0:
                            temp_sources[opt] -= 1
                            paid = True
                            break
                    if not paid:
                        castable = False
                        break
                if castable:
                    return True
            return False

        c2, c3, c4 = can_cast(t2_state, 2), can_cast(t3_state, 3), can_cast(t4_state, 4)
        if c2:
            stats["cast_t2"] += 1
        if c3:
            stats["cast_t3"] += 1
        if c4:
            stats["cast_t4"] += 1
        if c2 and c3 and c4:
            stats["curve_out"] += 1

        if len(lands_t3) >= 3 and not c3:
            has_3_drop = any(not c["is_land"] and c["cmc"] == 3 for c in t3_state)
            if has_3_drop:
                stats["color_screw_t3"] += 1

    stats["avg_hand_size"] = stats["avg_hand_size"] / iterations
    for k in list(stats.keys()):
        if k != "avg_hand_size":
            stats[k] = (stats[k] / iterations) * 100.0
    return stats
