from server.validate import validate_dataset, enough_history_to_enforce
from server import config


def _card(name, all_samples, all_gihwr, arch_overrides=None):
    """Build a card object shaped like transform_payload output."""
    deck_colors = {}
    for arch in config.ARCHETYPES:
        deck_colors[arch] = {"samples": 0, "gihwr": 0.0}
    deck_colors["All Decks"] = {"samples": all_samples, "gihwr": all_gihwr}
    for arch, stats in (arch_overrides or {}).items():
        deck_colors[arch] = stats
    return {"name": name, "deck_colors": deck_colors}


def _dataset(cards):
    # Mimic many arena_ids sharing objects by giving each card two id keys.
    card_ratings = {}
    for i, c in enumerate(cards):
        card_ratings[str(1000 + i)] = c
        card_ratings[str(9000 + i)] = c  # duplicate reference, must be deduped
    return {"card_ratings": card_ratings}


def test_healthy_dataset_passes():
    cards = [
        _card(
            f"Card {i}",
            5000 - i * 100,
            60.0 + i,
            arch_overrides={
                "WU": {"samples": 1200 - i * 10, "gihwr": 62.0 + i},
                "BR": {"samples": 900 - i * 10, "gihwr": 58.0 + i},
            },
        )
        for i in range(6)
    ]
    warnings, critical = validate_dataset(
        "MSH", "PremierDraft", "All", _dataset(cards), total_games=100000
    )
    assert critical == []
    assert warnings == []


def test_identical_archetypes_is_critical():
    """The exact wrong-endpoint bug: every archetype copies All Decks."""
    cards = []
    for i in range(6):
        base = {"samples": 508, "gihwr": 64.96}
        overrides = {arch: dict(base) for arch in ["WU", "BR", "WG", "UR"]}
        cards.append(_card(f"Card {i}", 508, 64.96, arch_overrides=overrides))
    warnings, critical = validate_dataset(
        "MSH", "PremierDraft", "All", _dataset(cards), total_games=401787
    )
    assert critical, "identical-archetype data must be flagged critical"
    assert "colors filter" in critical[0]


def test_truncated_coverage_warns():
    """Colors filter works, but sample counts are a tiny fraction of games."""
    cards = [
        _card(
            f"Card {i}",
            500 - i * 10,
            64.0,
            arch_overrides={"WU": {"samples": 120 - i, "gihwr": 66.0}},
        )
        for i in range(6)
    ]
    warnings, critical = validate_dataset(
        "MSH", "PremierDraft", "All", _dataset(cards), total_games=401787
    )
    assert critical == []
    assert any("truncated" in w for w in warnings)


def test_empty_dataset_is_critical():
    warnings, critical = validate_dataset(
        "MSH", "PremierDraft", "All", {"card_ratings": {}}, total_games=0
    )
    assert critical
    assert "no card ratings" in critical[0].lower()


def test_enforcement_gated_on_set_maturity():
    """Day one/two of a set must not block a publish; a mature set must."""
    # Same calendar day -> 0 days of data (day one).
    assert enough_history_to_enforce("2026-06-23", "2026-06-23") is False
    # Two days in.
    assert enough_history_to_enforce("2026-06-23", "2026-06-25") is False
    # Past the maturity window -> enforce.
    assert enough_history_to_enforce("2026-06-23", "2026-06-30") is True
    # Unparseable dates keep the safety net on.
    assert enough_history_to_enforce("", None) is True


def test_only_all_decks_present_does_not_falsely_flag_archetypes():
    """A set where no color pair met the game threshold: only All Decks has data.
    Coverage may warn, but the archetype-divergence check must not fire."""
    cards = [_card(f"Card {i}", 6000 - i * 100, 60.0) for i in range(6)]
    warnings, critical = validate_dataset(
        "MSH", "PremierDraft", "All", _dataset(cards), total_games=100000
    )
    assert critical == []
