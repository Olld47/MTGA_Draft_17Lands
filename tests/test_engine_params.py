"""
tests/test_engine_params.py

The scoring engine's tuning coefficients must live in a single annotated config
(ENGINE_PARAMS) and be *referenced* — never restated — by both the engine code
and docs/03. These tests pin the four seams: config structure + calibration
debt, docs<->config sync, config<->engine wiring, and (behaviorally) that the
engine actually reads the params rather than re-hardcoding literals.
"""

import dataclasses
import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.advisor import engine as engine_module
from src.advisor.engine import ENGINE_PARAMS, ENGINE_PARAMS_CALIBRATION, DraftAdvisor

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "03-business-logic.md"
ENGINE_SRC = (REPO_ROOT / "src" / "advisor" / "engine.py").read_text()


@pytest.fixture
def metrics():
    m = MagicMock()
    m.format_texture = {}
    m.get_metrics.return_value = (55.0, 4.0)
    return m


def _param_fields():
    fields = {}
    for group_name in [f.name for f in dataclasses.fields(ENGINE_PARAMS)]:
        group = getattr(ENGINE_PARAMS, group_name)
        for field in dataclasses.fields(group):
            fields[(group_name, field.name)] = getattr(group, field.name)
    return fields


# ---------------------------------------------------------------------------
# Seam 1: config structure + calibration debt
# ---------------------------------------------------------------------------


def test_engine_params_is_frozen_annotated_config():
    assert dataclasses.is_dataclass(ENGINE_PARAMS)
    # Both the outer config and every nested group are frozen — dataclasses.replace
    # (used by the behavioral tests) depends on it.
    with pytest.raises(dataclasses.FrozenInstanceError):
        ENGINE_PARAMS.targets = object()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ENGINE_PARAMS.targets.total_picks = 999
    for group in [getattr(ENGINE_PARAMS, f.name) for f in dataclasses.fields(ENGINE_PARAMS)]:
        assert dataclasses.is_dataclass(group)


def test_every_param_group_has_docstring():
    for group_name in [f.name for f in dataclasses.fields(ENGINE_PARAMS)]:
        group_cls = type(getattr(ENGINE_PARAMS, group_name))
        doc = group_cls.__doc__ or ""
        assert doc and not doc.startswith(
            group_cls.__name__ + "("
        ), f"{group_name} group needs a real docstring (got {doc!r})"


def test_engine_params_calibration_debt_documented():
    assert "ENGINE_PARAMS_CALIBRATION" in ENGINE_SRC
    note = ENGINE_PARAMS_CALIBRATION.lower()
    assert any(
        word in note for word in ("backtest", "calibrat", "validat", "heuristic")
    ), "calibration note must admit the values are unvalidated heuristics"


def test_signal_capitalization_gate_is_annotated_param():
    # The pack-1 pick floor for the late-signal bonus must be a typed
    # ENGINE_PARAMS field (single source), not an engine-method literal.
    from typing import get_type_hints

    hints = get_type_hints(type(ENGINE_PARAMS.bomb))
    assert "signal_min_pick" in hints
    assert hints["signal_min_pick"] is int
    assert ENGINE_PARAMS.bomb.signal_min_pick == 5


# ---------------------------------------------------------------------------
# Seam 2: docs/03 references config field names instead of restating values
# ---------------------------------------------------------------------------


def test_docs03_references_resolve_to_real_params():
    text = DOC.read_text()
    refs = re.findall(r"ENGINE_PARAMS\.(\w+)\.(\w+)", text)
    assert refs, "docs/03 must reference ENGINE_PARAMS field names, not restate values"
    fields = _param_fields()
    unresolved = {f"{g}.{f}" for g, f in refs if (g, f) not in fields}
    assert not unresolved, f"docs/03 references unknown params: {unresolved}"


# ---------------------------------------------------------------------------
# Seam 3: every config field is actually read by the engine (no dead config)
# ---------------------------------------------------------------------------


def test_every_param_is_wired_in_engine():
    refs = set(re.findall(r"ENGINE_PARAMS\.(\w+)\.(\w+)", ENGINE_SRC))
    fields = _param_fields()
    unwired = {f"{g}.{f}" for (g, f) in fields if (g, f) not in refs}
    assert not unwired, f"params never read by engine: {unwired}"


# ---------------------------------------------------------------------------
# Seam 4: behavior moves when a param moves (engine reads params, not literals)
# ---------------------------------------------------------------------------


def test_composition_reads_fixing_hunger_mult(metrics, monkeypatch):
    advisor = DraftAdvisor(metrics, [])
    advisor.pool_metrics = {
        "fixing_count": 0,
        "off_color_playables": 2,
        "splash_targets": [],
        "early_plays": 0,
        "hard_removal_count": 0,
        "creature_count": 0,
        "heavy_drops": 0,
        "artifacts": 0,
        "graveyard_enablers": 0,
        "counters_enablers": 0,
    }
    mult, _ = advisor._calculate_composition_bonus({"types": ["Land"]}, pack=2)
    assert mult == ENGINE_PARAMS.composition.fixing_hunger_mult

    new = replace(
        ENGINE_PARAMS,
        composition=replace(ENGINE_PARAMS.composition, fixing_hunger_mult=1.9),
    )
    monkeypatch.setattr(engine_module, "ENGINE_PARAMS", new)
    mult2, _ = advisor._calculate_composition_bonus({"types": ["Land"]}, pack=2)
    assert mult2 == 1.9


def test_castability_reads_uncastable_double_pip_mult(metrics, monkeypatch):
    advisor = DraftAdvisor(metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.pool_metrics = {"fixing_count": 0}
    card = {"colors": ["B"], "mana_cost": "{B}{B}"}
    mult, _ = advisor._calculate_castability_v5(card, pack=2, pick=1, z_score=0.0)
    assert mult == ENGINE_PARAMS.castability.uncastable_double_pip_mult

    new = replace(
        ENGINE_PARAMS,
        castability=replace(
            ENGINE_PARAMS.castability, uncastable_double_pip_mult=0.05
        ),
    )
    monkeypatch.setattr(engine_module, "ENGINE_PARAMS", new)
    mult2, _ = advisor._calculate_castability_v5(card, pack=2, pick=1, z_score=0.0)
    assert mult2 == 0.05


def test_wheel_reads_mult(metrics, monkeypatch):
    advisor = DraftAdvisor(metrics, [])
    card = {"deck_colors": {"All Decks": {"alsa": 10.0}}}
    mult, _, _ = advisor._check_relative_wheel(card, pick=2, rank_in_pack=5)
    assert mult == ENGINE_PARAMS.wheel.mult

    new = replace(ENGINE_PARAMS, wheel=replace(ENGINE_PARAMS.wheel, mult=0.5))
    monkeypatch.setattr(engine_module, "ENGINE_PARAMS", new)
    mult2, _, _ = advisor._check_relative_wheel(card, pick=2, rank_in_pack=5)
    assert mult2 == 0.5


def test_weighted_score_reads_signal_boost(metrics, monkeypatch):
    card = {"colors": ["W", "U"], "deck_colors": {"All Decks": {"gihwr": 60.0}}}
    advisor = DraftAdvisor(metrics, [])
    with_signals = DraftAdvisor(metrics, [], signals={"W": 6.0, "U": 6.0})
    base = advisor._calculate_weighted_score(card, pick_number=10)
    boosted = with_signals._calculate_weighted_score(card, pick_number=10)
    assert boosted == pytest.approx(base * ENGINE_PARAMS.progressive.signal_boost)

    new = replace(
        ENGINE_PARAMS,
        progressive=replace(ENGINE_PARAMS.progressive, signal_boost=1.2),
    )
    monkeypatch.setattr(engine_module, "ENGINE_PARAMS", new)
    boosted2 = with_signals._calculate_weighted_score(card, pick_number=10)
    assert boosted2 == pytest.approx(base * 1.2)


def test_bomb_reads_iwd_mult(metrics, monkeypatch):
    advisor = DraftAdvisor(metrics, [])
    pack = [
        {
            "name": "Bomb",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 75.0, "iwd": 5.0, "alsa": 2.0}},
        },
        {
            "name": "F1",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 0.0, "alsa": 8.0}},
        },
        {
            "name": "F2",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 0.0, "alsa": 8.0}},
        },
    ]
    bomb = next(
        r for r in advisor.evaluate_pack(pack, current_pick=1) if r.card_name == "Bomb"
    )
    new = replace(ENGINE_PARAMS, bomb=replace(ENGINE_PARAMS.bomb, iwd_mult=1.4))
    monkeypatch.setattr(engine_module, "ENGINE_PARAMS", new)
    bomb2 = next(
        r for r in advisor.evaluate_pack(pack, current_pick=1) if r.card_name == "Bomb"
    )
    assert bomb2.contextual_score != bomb.contextual_score


def test_signal_capitalization_reads_min_pick_gate(metrics, monkeypatch):
    advisor = DraftAdvisor(metrics, [])
    pack = [
        {
            "name": "Bomb",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 75.0, "iwd": 5.0, "alsa": 2.0}},
        },
        {
            "name": "F1",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 0.0, "alsa": 8.0}},
        },
        {
            "name": "F2",
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 0.0, "alsa": 8.0}},
        },
    ]
    # Pack 1, pick 5, alsa 2 → lateness 3 ≥ 2 and z ≈ 1.4 > 0.5, so the
    # late-signal branch fires at the stock gate (signal_min_pick=5).
    bomb = next(
        r for r in advisor.evaluate_pack(pack, current_pick=5) if r.card_name == "Bomb"
    )
    assert any("LATE SIGNAL" in reason for reason in bomb.reasoning)

    new = replace(ENGINE_PARAMS, bomb=replace(ENGINE_PARAMS.bomb, signal_min_pick=6))
    monkeypatch.setattr(engine_module, "ENGINE_PARAMS", new)
    bomb2 = next(
        r for r in advisor.evaluate_pack(pack, current_pick=5) if r.card_name == "Bomb"
    )
    assert not any("LATE SIGNAL" in reason for reason in bomb2.reasoning)
    assert bomb2.contextual_score < bomb.contextual_score
