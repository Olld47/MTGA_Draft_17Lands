import pytest
from src.sealed_logic import (
    HeuristicEvaluator,
    SealedSession,
    SealedVariant,
    generate_sealed_shells,
)
from src.constants import DATA_FIELD_NAME


def test_heuristic_evaluator():
    """Verify Day-1 card evaluation applies logic to metadata."""

    # Premium 2-drop removal
    premium_removal = {"rarity": "uncommon", "cmc": 2, "tags": ["removal"]}
    score = HeuristicEvaluator.evaluate(premium_removal)
    assert score == 60.0  # 54 (uncommon) + 6 (premium removal) = 60.0

    # Clunky vanilla creature (should be penalized)
    vanilla_beater = {"rarity": "common", "cmc": 6, "types": ["Creature"], "tags": []}
    score2 = HeuristicEvaluator.evaluate(vanilla_beater)
    assert score2 == 48.0  # 52 (common) - 4 (vanilla >= 5cmc) = 48.0

    # Evasive threat
    evasion_threat = {
        "rarity": "rare",
        "cmc": 3,
        "types": ["Creature"],
        "tags": ["evasion"],
    }

    score3 = HeuristicEvaluator.evaluate(evasion_threat)
    assert score3 == 61.5  # 58 (rare) + 2.5 (evasion) + 1.0 (3cmc Creature) = 61.5


def test_sealed_session_variant_management():
    session = SealedSession("test_id")
    pool = [
        {DATA_FIELD_NAME: "Card A", "count": 2},
        {DATA_FIELD_NAME: "Plains", "types": ["Basic", "Land"]},
    ]
    session.load_pool(pool)

    # Ensure it created a default build
    assert len(session.variants) == 1
    assert "Build 1" in session.variants

    # Move card to main
    assert session.move_to_main("Card A", 1) is True
    assert session.variants["Build 1"].main_deck_counts["Card A"] == 1

    # Move second card
    assert session.move_to_main("Card A", 1) is True

    # Fail to move third card (only 2 in pool)
    assert session.move_to_main("Card A", 1) is False

    # Basic lands should be infinite
    assert session.move_to_main("Plains", 17) is True

    # Check Active Deck Retrieval
    main, sb = session.get_active_deck_lists()

    # Main has Card A x2, Plains x17
    assert sum(c["count"] for c in main) == 19
    # Sideboard is empty since both copies of Card A are in the main deck
    assert len(sb) == 0


# --- session_dir injection ---------------------------------------------------
# Ticket 08: sealed session files were hard-pinned to constants.TEMP_FOLDER.
# The seam is now an injectable directory on the session and on load_session.

def test_sealed_session_injected_dir_roundtrip(tmp_path):
    """A session built with an injected session_dir persists and reloads there —
    never to the module-level TEMP_FOLDER default."""
    from pathlib import Path
    from src import constants as constants_mod

    pool = [
        {DATA_FIELD_NAME: "Card A", "count": 2},
        {DATA_FIELD_NAME: "Plains", "types": ["Basic", "Land"]},
    ]
    session = SealedSession("sess_injected", session_dir=str(tmp_path))
    session.load_pool(pool)
    session.active_variant_name = "Build 1"
    session.save_session()

    state_file = tmp_path / "sealed_sess_injected.json"
    assert state_file.exists()
    assert not (
        Path(constants_mod.TEMP_FOLDER) / "sealed_sess_injected.json"
    ).exists()

    loaded = SealedSession.load_session(
        "sess_injected", pool, session_dir=str(tmp_path)
    )
    assert loaded is not None
    assert loaded.active_variant_name == "Build 1"


def test_sealed_session_default_dir_uses_temp_folder(monkeypatch, tmp_path):
    """Omitting session_dir keeps the legacy TEMP_FOLDER-derived path."""
    from src import constants as constants_mod

    monkeypatch.setattr(constants_mod, "TEMP_FOLDER", str(tmp_path))
    session = SealedSession("sess_default")
    session.save_session()
    assert (tmp_path / "sealed_sess_default.json").exists()

    loaded = SealedSession.load_session("sess_default", [])
    assert loaded is not None
    assert loaded.session_id == "sess_default"


def test_generate_sealed_shells(monkeypatch):
    """Verify AI generates shells based on the pool."""
    # We must mock metrics and holistic scoring since it relies on dataset
    session = SealedSession("test_id")
    pool = []

    # Generate 40 playable green/red cards to simulate a pool
    for i in range(40):
        pool.append(
            {
                DATA_FIELD_NAME: f"GR Card {i}",
                "colors": ["G", "R"],
                "cmc": 2,
                "types": ["Creature"],
                "deck_colors": {"All Decks": {"gihwr": 55.0}},
            }
        )

    session.load_pool(pool)

    mock_metrics = type(
        "MockMetrics", (), {"get_metrics": lambda self, c, f: (55.0, 4.0)}
    )()

    generate_sealed_shells(session, mock_metrics, None)

    # Should have generated Safe 2-Color and Aggro Curve variants
    assert len(session.variants) >= 2
    assert any("Safe 2-Color" in k for k in session.variants.keys())
    assert any("Aggro Curve" in k for k in session.variants.keys())
