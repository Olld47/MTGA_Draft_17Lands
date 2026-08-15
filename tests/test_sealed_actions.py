"""
tests/test_sealed_actions.py
Pure tests for src.sealed_actions.SealedStudioActions — the shared action
orchestration consumed by the desktop bridge (mtga_bridge.sealed_session).
No bridge, no viewmodels:
a SealedSession is built directly against a tmp_path.

Ticket 09 convergence: these tests pin the shared behavior so the bridge and the legacy UI could
delegate without drifting (the actions were previously duplicated verbatim in
mtga_bridge/sealed_session.py and src/ui/windows/sealed_studio.py).
"""

import pytest

from src.sealed_actions import SealedStudioActions
from src.sealed_logic import SealedSession

_POOL_CARDS = [
    ("White Knight", 2, ["Creature"], ["W"], "{1}{W}"),
    ("Blue Flyer", 3, ["Creature"], ["U"], "{2}{U}"),
    ("Black Removal", 2, ["Instant"], ["B"], "{1}{B}"),
    ("Red Burn", 1, ["Instant"], ["R"], "{R}"),
    ("Green Beast", 4, ["Creature"], ["G"], "{2}{G}{G}"),
    ("WU Flex", 3, ["Creature"], ["W", "U"], "{1}{W}{U}"),
]


def _pool(copies: int = 8) -> list:
    """Flat pool as the scanner returns it: `copies` rows per card, each row
    carrying count 1 (the pool-size guard counts rows, like the bridge test)."""
    return [
        {
            "name": name,
            "cmc": cmc,
            "types": types,
            "colors": colors,
            "mana_cost": cost,
            "rarity": "common",
            "count": 1,
        }
        for name, cmc, types, colors, cost in _POOL_CARDS
        for _ in range(copies)
    ]


@pytest.fixture
def actions(tmp_path):
    session = SealedSession("test_sealed", str(tmp_path))
    session.load_pool(_pool())
    return SealedStudioActions(session)


@pytest.fixture
def small_actions(tmp_path):
    session = SealedSession("small_sealed", str(tmp_path))
    session.load_pool(_pool(copies=1)[:2])
    return SealedStudioActions(session)


# --- card movement ----------------------------------------------------------


def test_move_card_to_main_and_back(actions):
    ok, _ = actions.move_card("White Knight", to_sideboard=False, count=2)
    assert ok
    main, _ = actions.session.get_active_deck_lists()
    assert sum(c["count"] for c in main) == 2

    ok, _ = actions.move_card("White Knight", to_sideboard=True, count=2)
    assert ok
    main, _ = actions.session.get_active_deck_lists()
    assert sum(c["count"] for c in main) == 0


def test_move_over_pool_limit_rejected(actions):
    ok, message = actions.move_card("White Knight", to_sideboard=False, count=100)
    assert ok is False
    assert "limit" in message.lower() or "pool" in message.lower()


def test_clear_deck(actions):
    actions.move_card("White Knight", to_sideboard=False, count=3)
    ok, _ = actions.clear_deck()
    assert ok
    main, _ = actions.session.get_active_deck_lists()
    assert main == []


def test_add_all_to_main(actions):
    actions.move_card("White Knight", to_sideboard=False, count=8)
    ok, _ = actions.add_all_to_main()
    assert ok
    main, sb = actions.session.get_active_deck_lists()
    assert sum(c["count"] for c in main) == 48
    assert sb == []


def test_add_and_remove_basic_bypass_pool_limit(actions):
    ok, _ = actions.add_basic("Plains")
    assert ok
    main, _ = actions.session.get_active_deck_lists()
    assert any(c["name"] == "Plains" for c in main)

    ok, _ = actions.remove_basic("Plains")
    assert ok
    main, _ = actions.session.get_active_deck_lists()
    assert not any(c["name"] == "Plains" for c in main)


# --- variant management ------------------------------------------------------


def test_create_rename_delete_variant(actions):
    ok, _ = actions.create_variant("Aggro")
    assert ok
    assert actions.session.active_variant_name == "Aggro"

    ok, _ = actions.rename_variant("Aggro", "Tempo")
    assert ok
    assert "Tempo" in actions.session.variants

    ok, _ = actions.delete_variant("Tempo")
    assert ok
    assert "Tempo" not in actions.session.variants


def test_cannot_delete_only_variant(actions):
    only = actions.session.active_variant_name
    ok, _ = actions.delete_variant(only)
    assert ok is False
    assert only in actions.session.variants


def test_rename_empty_name_rejected(actions):
    ok, _ = actions.rename_variant(actions.session.active_variant_name, "   ")
    assert ok is False


def test_rename_duplicate_name_rejected(actions):
    actions.create_variant("Second")
    ok, _ = actions.rename_variant("Second", "Build 1")
    assert ok is False


def test_select_variant(actions):
    actions.create_variant("Second")
    ok, _ = actions.select_variant("Second")
    assert ok
    assert actions.session.active_variant_name == "Second"


# --- shell generation --------------------------------------------------------


def test_auto_generate_requires_40_cards(small_actions, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.sealed_actions.generate_sealed_shells",
        lambda session, metrics, tier_data=None: calls.append(session),
    )
    ok, message = small_actions.auto_generate({}, {})
    assert ok is False
    assert "40" in message
    assert calls == []


def test_auto_generate_builds_shells(actions, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.sealed_actions.generate_sealed_shells",
        lambda session, metrics, tier_data=None: calls.append(session),
    )
    ok, _ = actions.auto_generate({"some": "metrics"}, {"tier": True})
    assert ok
    assert calls == [actions.session]


# --- auto-lands --------------------------------------------------------------


def test_apply_auto_lands_removes_basics_and_fills_to_40(actions):
    for name in ["White Knight", "Blue Flyer", "WU Flex"]:
        actions.move_card(name, to_sideboard=False, count=7)
    actions.add_basic("Plains")
    actions.add_basic("Island")

    ok, _ = actions.apply_auto_lands()
    assert ok

    main, _ = actions.session.get_active_deck_lists()
    assert sum(c["count"] for c in main) == 40
    names = {c["name"]: c["count"] for c in main}
    # Deck colors are W/U, so auto-lands must strip the off-color basics and
    # add only Plains/Island.
    assert names.get("Plains", 0) + names.get("Island", 0) > 0
    assert "Swamp" not in names and "Mountain" not in names and "Forest" not in names


def test_apply_auto_lands_counts_copies_not_rows(actions):
    """Regression guard (the v0.14 deck_session bug shape): get_active_deck_lists
    returns stacked rows, so the missing-lands arithmetic must count copies, not
    rows, or auto-lands over-fills the deck past 40."""
    for name in ["White Knight", "Blue Flyer", "WU Flex"]:
        actions.move_card(name, to_sideboard=False, count=7)

    ok, _ = actions.apply_auto_lands()
    assert ok

    main, _ = actions.session.get_active_deck_lists()
    assert sum(c["count"] for c in main) == 40


def test_apply_auto_lands_requires_spells(actions):
    ok, _ = actions.apply_auto_lands()
    assert ok is False


# --- import / export ---------------------------------------------------------


def test_import_deck_from_text(actions):
    ok, _ = actions.import_deck("Deck\n4 White Knight\n3 Blue Flyer\n")
    assert ok
    main, _ = actions.session.get_active_deck_lists()
    assert sum(c["count"] for c in main) == 7


def test_import_deck_reports_missing(actions):
    ok, message = actions.import_deck("2 White Knight\n2 Totally Fake Card\n")
    assert ok  # partial import still succeeds
    assert "Fake" in message and "skipped" in message.lower()


def test_import_deck_rejects_garbage(actions):
    ok, _ = actions.import_deck("this is not a decklist")
    assert ok is False


def test_export_mtga_text(actions):
    actions.move_card("White Knight", to_sideboard=False, count=2)
    text = actions.export()
    assert text.startswith("Deck")
    assert "White Knight" in text
