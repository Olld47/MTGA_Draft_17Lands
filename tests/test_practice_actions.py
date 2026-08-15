"""
tests/test_practice_actions.py
Tests for the shared practice-pool action layer (src.practice_actions), the
single implementation the desktop bridge (mtga_bridge.practice) and the
pre-convergence dialog delegate to — ticket 09 convergence. The behaviors here are the ones the bridge port
(`tests/test_bridge_practice.py`) already pinned, re-expressed against the
pure layer: no scanner, explicit parameters.
"""

import pytest

from src.practice_actions import (
    PACK_COUNT,
    RARES_PER_PACK,
    UNCOMMONS_PER_PACK,
    COMMONS_PER_PACK,
    build_set_options,
    dataset_rank,
    generate_random_pool,
    new_session_id,
    parse_pool_text,
)

_CARDS = [
    ("Common A", "common"),
    ("Common B", "common"),
    ("Common C", "common"),
    ("Common D", "common"),
    ("Common E", "common"),
    ("Uncommon A", "uncommon"),
    ("Uncommon B", "uncommon"),
    ("Uncommon C", "uncommon"),
    ("Rare A", "rare"),
    ("Rare B", "rare"),
    ("Mythic A", "mythic"),
]


class _FakeDataset:
    """Minimal stand-in for the loaded set dataset: card ratings by id plus
    by-name lookup returning prototype copies."""

    def __init__(self, cards):
        self._cards = list(cards)

    def get_card_ratings(self):
        return {str(i): dict(c) for i, c in enumerate(self._cards)}

    def get_data_by_name(self, names):
        found = []
        for name in names:
            match = next((c for c in self._cards if c["name"] == name), None)
            if match:
                found.append(dict(match))
        return found


def _dataset():
    cards = [
        {
            "name": name,
            "cmc": 2,
            "types": ["Creature"],
            "colors": ["W"],
            "rarity": rarity,
            "mana_cost": "{1}{W}",
        }
        for name, rarity in _CARDS
    ]
    cards.append(
        {
            "name": "Plains",
            "cmc": 0,
            "types": ["Basic", "Land"],
            "colors": [],
            "rarity": "common",
            "mana_cost": "",
        }
    )
    return _FakeDataset(cards)


class _SetInfo:
    def __init__(self, code, sl_code=None):
        self.set_code = code
        self.seventeenlands = [sl_code] if sl_code else []


# --- Set listing --------------------------------------------------------------


def test_build_set_options_orders_active_first_in_manifest_order():
    data = {"Older Set": _SetInfo("OLD"), "Test Set": _SetInfo("TEST")}

    options = build_set_options(data, active_codes=["OLD"], latest_set="")

    assert [o["code"] for o in options] == ["OLD", "TEST"]
    assert options[0]["is_active"] is True
    assert options[0]["name"] == "Older Set"
    assert options[1]["is_active"] is False


def test_build_set_options_appends_the_latest_set_when_not_active():
    data = {"Older Set": _SetInfo("OLD"), "Test Set": _SetInfo("TEST")}

    options = build_set_options(data, active_codes=["OLD"], latest_set="TEST")

    # OLD ranks 0; TEST is appended as latest (rank 1) — both active.
    assert [o["code"] for o in options] == ["OLD", "TEST"]
    assert all(o["is_active"] for o in options)


def test_build_set_options_sorts_inactive_alphabetically():
    data = {"Zeta Set": _SetInfo("ZET"), "Alpha Set": _SetInfo("ALP")}

    options = build_set_options(data, active_codes=[], latest_set="")

    assert [o["code"] for o in options] == ["ALP", "ZET"]
    assert not any(o["is_active"] for o in options)


def test_build_set_options_skips_entries_without_a_code():
    data = {
        "Valid Set": _SetInfo("VAL", sl_code="VAL"),
        "Broken Set": _SetInfo(""),
    }

    options = build_set_options(data, active_codes=[], latest_set="")

    assert [o["code"] for o in options] == ["VAL"]


def test_build_set_options_is_empty_for_empty_data():
    assert build_set_options({}, active_codes=[], latest_set="") == []


# --- Dataset ranking ----------------------------------------------------------


def test_dataset_rank_prefers_sealed_over_premier_over_trad():
    assert dataset_rank("Sealed") < dataset_rank("PremierDraft")
    assert dataset_rank("PremierDraft") < dataset_rank("TradDraft")


def test_dataset_rank_falls_back_for_unknown_event_types():
    assert dataset_rank("QuickDraft") > dataset_rank("TradDraft")
    assert dataset_rank("") > dataset_rank("TradDraft")


# --- Random pool generation ---------------------------------------------------


def test_generate_random_pool_pack_composition():
    pool, error = generate_random_pool(_dataset())

    assert error == ""
    assert PACK_COUNT == 6
    assert RARES_PER_PACK == 1
    assert UNCOMMONS_PER_PACK == 3
    assert COMMONS_PER_PACK == 10
    # 6 packs * (1 rare/mythic + 3 uncommons + 10 commons)
    assert len(pool) == 84

    rarities = [c["rarity"] for c in pool]
    assert sum(r in ("rare", "mythic") for r in rarities) == 6
    assert rarities.count("uncommon") == 18
    assert rarities.count("common") == 60
    assert "Plains" not in [c["name"] for c in pool]


def test_generate_random_pool_returns_copies():
    pool, _ = generate_random_pool(_dataset())
    pool[0]["name"] = "Mutated"

    ratings = _dataset().get_card_ratings()
    assert "Mutated" not in [c["name"] for c in ratings.values()]


def test_generate_random_pool_rejects_incomplete_dataset():
    class _CommonsOnly:
        @staticmethod
        def get_card_ratings():
            return {"1": {"name": "Common A", "rarity": "common", "types": []}}

    pool, error = generate_random_pool(_CommonsOnly())

    assert pool == []
    assert "incomplete" in error


# --- MTGA decklist import -----------------------------------------------------


def test_parse_pool_text_expands_counts():
    text = "Deck\n2 Common A\n1 Rare A (TEST) 42\n\nSideboard\n3 Uncommon B"
    pool, error = parse_pool_text(_dataset(), text)

    assert error == ""
    names = [c["name"] for c in pool]
    assert names.count("Common A") == 2
    assert names.count("Rare A") == 1
    assert names.count("Uncommon B") == 3


def test_parse_pool_text_skips_unknown_cards():
    pool, error = parse_pool_text(_dataset(), "1 Common A\n4 Not In This Set")

    assert error == ""
    assert [c["name"] for c in pool] == ["Common A"]


def test_parse_pool_text_rejects_garbage():
    pool, error = parse_pool_text(_dataset(), "This is just some random text.")

    assert pool == []
    assert "No valid MTGA format cards" in error


# --- Session id ---------------------------------------------------------------


def test_new_session_id_has_the_practice_prefix():
    assert new_session_id().startswith("practice_")
