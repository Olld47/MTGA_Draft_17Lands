"""
tests/test_bridge_serialization.py
Locks the IPC serialization contract for the pytauri bridge.

pytauri serializes command returns, events and Channel messages with a bare
``model_dump_json()`` — no ``by_alias=True``. Pydantic only applies
``alias_generator`` when asked, so before ``serialize_by_alias=True`` was added
to ``_VM.model_config`` every payload shipped snake_case keys while the whole
TypeScript frontend reads camelCase. The result was a blank window.

These tests reflect over the models and the command signatures instead of
checking pages one at a time, so a new model or a new command can't
reintroduce the bug. Requires neither pytauri nor tkinter.
"""

import ast
import os
import sys
from typing import Any, get_args, get_origin
from unittest.mock import patch

import pytest
from pydantic import BaseModel

# Make the bridge package importable from the root test run
BRIDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "desktop",
    "src-tauri",
    "src-python",
)
if BRIDGE_PATH not in sys.path:
    sys.path.insert(0, BRIDGE_PATH)

from src import constants
from src.configuration import Configuration

from mtga_bridge import services, viewmodels
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import SettingsPatch, _VM


COMMANDS_SOURCE = os.path.join(BRIDGE_PATH, "mtga_bridge", "commands.py")


def _vm_classes():
    """Every _VM subclass declared in viewmodels, excluding _VM itself."""
    found = []
    for name in dir(viewmodels):
        obj = getattr(viewmodels, name)
        if isinstance(obj, type) and issubclass(obj, _VM) and obj is not _VM:
            found.append(obj)
    return sorted(found, key=lambda c: c.__name__)


VM_CLASSES = _vm_classes()


def _dummy(annotation: Any) -> Any:
    """Smallest value satisfying a required field's annotation."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _instantiate(annotation)
    origin = get_origin(annotation)
    if origin in (list, set, tuple):
        return []
    if origin is dict:
        return {}
    if annotation is bool:
        return False
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is str:
        return ""
    raise AssertionError(
        f"test needs a dummy value for {annotation!r} — extend _dummy()"
    )


def _instantiate(model: type) -> BaseModel:
    """Builds a model using defaults, filling only the required fields."""
    kwargs = {
        name: _dummy(field.annotation)
        for name, field in model.model_fields.items()
        if field.is_required()
    }
    return model(**kwargs)


def _snake_keys(payload: Any) -> list:
    """Every key containing an underscore, anywhere in a nested payload."""
    offenders = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if "_" in key:
                offenders.append(key)
            offenders.extend(_snake_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            offenders.extend(_snake_keys(item))
    return offenders


# --- The serialization contract ----------------------------------------------


def test_vm_classes_discovered():
    # Guards the reflection itself: an import rename that empties the list would
    # otherwise turn every parametrized test below into a silent no-op.
    assert len(VM_CLASSES) > 40


@pytest.mark.parametrize("model", VM_CLASSES, ids=lambda m: m.__name__)
def test_bare_dump_emits_camel_case(model):
    """A bare model_dump() — what pytauri calls — must not emit snake_case."""
    offenders = _snake_keys(_instantiate(model).model_dump())
    assert not offenders, f"{model.__name__} emitted snake_case keys: {offenders}"


@pytest.mark.parametrize("model", VM_CLASSES, ids=lambda m: m.__name__)
def test_bare_dump_json_emits_camel_case(model):
    """model_dump_json() is the exact call at all three pytauri exits."""
    import json

    offenders = _snake_keys(json.loads(_instantiate(model).model_dump_json()))
    assert offenders == [], f"{model.__name__} emitted snake_case keys: {offenders}"


@pytest.mark.parametrize("model", VM_CLASSES, ids=lambda m: m.__name__)
def test_aliased_fields_replace_their_field_names(model):
    """Each renamed field ships under its alias only, never under both."""
    dumped = _instantiate(model).model_dump()
    for name, field in model.model_fields.items():
        alias = field.alias
        if alias is None or alias == name:
            continue
        assert alias in dumped, f"{model.__name__}.{name} missing alias {alias}"
        assert name not in dumped, f"{model.__name__} leaked field name {name}"


def test_at_least_one_model_actually_has_a_renamed_field():
    # The camelCase assertions above pass trivially for single-word models; this
    # confirms the suite is exercising the aliasing path at all.
    renamed = [
        model
        for model in VM_CLASSES
        if any(
            f.alias and f.alias != n for n, f in model.model_fields.items()
        )
    ]
    assert len(renamed) > 30


@pytest.mark.parametrize("model", VM_CLASSES, ids=lambda m: m.__name__)
def test_inbound_accepts_both_casings(model):
    """populate_by_name keeps frontend -> Python validation working."""
    instance = _instantiate(model)
    by_alias = model.model_validate(instance.model_dump())
    by_name = model.model_validate(instance.model_dump(by_alias=False))
    assert by_alias.model_dump() == by_name.model_dump()


# --- Command signatures ------------------------------------------------------


def _command_return_annotations():
    """(command name, return annotation) for every @commands.command() in
    commands.py, read from source so pytauri needn't be importable."""
    with open(COMMANDS_SOURCE, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        decorated = any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr == "command"
            for d in node.decorator_list
        )
        if decorated:
            results.append((node.name, ast.unparse(node.returns) if node.returns else None))
    return results


def test_every_command_returns_a_vm_model():
    """A command returning a plain BaseModel would ship snake_case keys, since
    only _VM carries serialize_by_alias."""
    commands = _command_return_annotations()
    assert len(commands) > 50, "command reflection found suspiciously few commands"

    offenders = []
    for name, annotation in commands:
        if annotation is None:
            offenders.append((name, "no return annotation"))
            continue
        model = getattr(viewmodels, annotation, None)
        if model is None or not issubclass(model, _VM):
            offenders.append((name, annotation))
    assert not offenders, f"commands not returning a _VM subclass: {offenders}"


# --- by_alias=False consumers ------------------------------------------------


# Values chosen to survive Settings' field validators — a rejected value falls
# back to the field default, which would look like a write-through failure.
_PATCH_VALUES = {
    "deck_filter": constants.DECK_FILTERS[-1],
    "filter_format": constants.DECK_FILTER_FORMAT_NAMES,
    "result_format": constants.RESULT_FORMAT_RATING,
    "ui_size": "80%",
    "desktop_theme": constants.DESKTOP_THEME_LIGHT,
    "card_colors_enabled": True,
    "draft_log_enabled": False,
    "update_notifications_enabled": False,
    "missing_notifications_enabled": False,
    "auto_sync_datasets": False,
    "arena_log_location": "/tmp/does-not-exist/Player.log",
    "database_location": "/tmp/does-not-exist/MTGA_Data",
    "column_configs": {"pack_table": ["name", "value"]},
}


def test_patch_values_cover_every_settings_patch_field():
    assert set(_PATCH_VALUES) == set(SettingsPatch.model_fields)


@pytest.mark.parametrize("field_name", sorted(SettingsPatch.model_fields))
def test_apply_settings_patch_writes_through_each_field(field_name):
    """apply_settings_patch dumps with by_alias=False because its keys are
    setattr'd onto the snake_case Settings model. A field whose alias leaked
    would raise, or silently fail to persist."""
    value = _PATCH_VALUES[field_name]
    runtime = AppRuntime(config=Configuration())
    assert getattr(runtime.config.settings, field_name) != value

    with patch("mtga_bridge.services.write_configuration"):
        services.apply_settings_patch(runtime, SettingsPatch(**{field_name: value}))

    assert getattr(runtime.config.settings, field_name) == value


def test_apply_settings_patch_ignores_unset_fields():
    runtime = AppRuntime(config=Configuration())
    before = runtime.config.settings.model_dump()

    with patch("mtga_bridge.services.write_configuration"):
        services.apply_settings_patch(runtime, SettingsPatch())

    assert runtime.config.settings.model_dump() == before


# --- Frontend error reporting ------------------------------------------------


def test_report_frontend_error_logs(caplog):
    body = viewmodels.FrontendErrorBody(
        message="undefined is not an object",
        source="boundary",
        stack="at DashboardPage.tsx:22",
    )
    with caplog.at_level("ERROR", logger="mtga_bridge.services"):
        ack = services.report_frontend_error(body)

    assert ack.ok
    logged = caplog.text
    assert "undefined is not an object" in logged
    assert "boundary" in logged
    assert "DashboardPage.tsx:22" in logged


def test_report_frontend_error_without_source(caplog):
    body = viewmodels.FrontendErrorBody(message="boom")
    with caplog.at_level("ERROR", logger="mtga_bridge.services"):
        services.report_frontend_error(body)
    assert "unknown" in caplog.text
