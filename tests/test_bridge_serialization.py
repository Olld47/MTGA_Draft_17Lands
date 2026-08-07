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
import re
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


# --- Event emit sites --------------------------------------------------------


EMIT_SOURCES = [
    os.path.join(BRIDGE_PATH, "mtga_bridge", name)
    for name in ("boot.py", "orchestrator_adapter.py", "__init__.py")
]

_EMIT_NAMES = {"emit", "_emit_safe"}


def _emit_calls(path):
    """(line number, payload argument node) for every emit()/_emit_safe() call,
    read from source so neither pytauri nor a running app is needed."""
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in _EMIT_NAMES and len(node.args) == 2:
            calls.append((node.lineno, node.args[1]))
    return calls


def test_emit_call_reflection_finds_the_sites():
    # Guards the reflection: a rename that emptied this list would turn the
    # assertion below into a silent no-op.
    total = sum(len(_emit_calls(path)) for path in EMIT_SOURCES)
    assert total >= 6, f"expected every event emit site, found {total}"


@pytest.mark.parametrize("path", EMIT_SOURCES, ids=os.path.basename)
def test_emit_sites_construct_a_model(path):
    """Every event payload must be a model, never a hand-written dict literal.

    The dict form is what caused the v0.6 blank window: keys typed by hand on
    the Python side, mirrored by hand in api/events.ts, with nothing checking
    they agree. A model routes through _VM's serialize_by_alias instead.
    """
    offenders = [
        f"{os.path.basename(path)}:{lineno}"
        for lineno, payload in _emit_calls(path)
        if isinstance(payload, ast.Dict)
    ]
    assert not offenders, f"emit sites passing a dict literal: {offenders}"


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
    "overlay_geometry": "380x600+120+80",
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


def test_reset_settings_restores_baseline(tmp_path, monkeypatch):
    """'Restore Defaults' writes a fresh Configuration and reloads it — the
    legacy settings.py:245 reset_configuration + re-read cycle. A mutated
    non-default value must read as baseline afterwards, on both the returned
    VM and the runtime config the frontend keeps referencing."""
    from src.configuration import write_configuration

    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("src.configuration.CONFIG_FILE", str(cfg_path))

    baseline = Configuration().settings.model_dump()
    config = Configuration()
    config.settings.desktop_theme = constants.DESKTOP_THEME_DARK
    config.settings.deck_filter = constants.DECK_FILTERS[-1]
    write_configuration(config, str(cfg_path))
    assert config.settings.model_dump() != baseline

    runtime = AppRuntime(config=config)
    vm = services.reset_settings(runtime)

    assert vm.desktop_theme == baseline["desktop_theme"]
    assert vm.deck_filter == baseline["deck_filter"]
    assert runtime.config.settings.model_dump() == baseline


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


# --- Orphaned backends -------------------------------------------------------

# A backend can be complete, registered as an IPC command, exported from
# client.ts — and called by nothing. v0.14 found four at once, including
# list_draft_logs/set_log_file, whose absence meant the desktop app could not
# open a past draft at all. plan.md tracks the port feature by feature, so a
# feature whose Python half shipped and whose React half never did reads as
# done. These tests are the mechanical version of that audit.

FRONTEND_DIR = os.path.join(os.path.dirname(BRIDGE_PATH), "..", "src")
CLIENT_SOURCE = os.path.join(FRONTEND_DIR, "api", "client.ts")


def _registered_commands():
    with open(COMMANDS_SOURCE, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr == "command"
            for d in node.decorator_list
        )
    }


def _client_source():
    with open(CLIENT_SOURCE, "r", encoding="utf-8") as handle:
        return handle.read()


def test_every_command_is_invoked_by_the_frontend():
    """A command with no pyInvoke is a backend the UI cannot reach."""
    client = _client_source()
    invoked = set(re.findall(r'pyInvoke(?:<[^>]*>)?\(\s*"([a-z_]+)"', client))
    commands = _registered_commands()
    assert len(commands) > 50, "command reflection found suspiciously few commands"

    assert not commands - invoked, f"commands with no pyInvoke: {sorted(commands - invoked)}"
    assert not invoked - commands, f"pyInvoke names with no command: {sorted(invoked - commands)}"


def test_every_client_export_has_a_caller():
    """An exported wrapper nobody calls means the feature stalled before its UI."""
    exports = set(re.findall(r"export const (\w+)\s*=", _client_source()))
    assert len(exports) > 50, "client.ts reflection found suspiciously few exports"

    orphans = set(exports)
    for root, _, files in os.walk(FRONTEND_DIR):
        if "node_modules" in root:
            continue
        for name in files:
            path = os.path.join(root, name)
            if not name.endswith((".ts", ".tsx")) or os.path.samefile(path, CLIENT_SOURCE):
                continue
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            orphans -= {e for e in orphans if re.search(rf"\b{e}\b", text)}

    assert not orphans, f"client.ts exports with no caller: {sorted(orphans)}"


def test_every_view_model_is_used_outside_viewmodels():
    """The six event models sat declared-but-unconstructed from v0.1 to v0.14
    while boot.py emitted hand-written dicts — the drift this file exists to
    catch. A VM referenced nowhere else is either dead or a contract nothing
    honors."""
    bridge_dir = os.path.dirname(COMMANDS_SOURCE)
    with open(os.path.join(bridge_dir, "viewmodels.py"), "r", encoding="utf-8") as handle:
        declared = set(re.findall(r"^class (\w+)\(_VM\):", handle.read(), re.M))
    assert len(declared) > 50, "viewmodels reflection found suspiciously few models"

    orphans = set(declared)
    for name in os.listdir(bridge_dir):
        if not name.endswith(".py") or name == "viewmodels.py":
            continue
        with open(os.path.join(bridge_dir, name), "r", encoding="utf-8") as handle:
            text = handle.read()
        orphans -= {v for v in orphans if re.search(rf"\b{v}\b", text)}

    assert not orphans, f"_VM classes never referenced outside viewmodels.py: {sorted(orphans)}"


# --- Field-level orphan audit -------------------------------------------------

# camelCase aliases serialized to the frontend but deliberately never read by
# any component. Keyed by alias (the JSON key the frontend sees). Each reason
# must stay true: wire a field up and remove it from this dict —
# test_allowlisted_fields_stay_unread fails the moment one of these appears in
# desktop/src, demanding its removal.
_UNREAD_FIELD_EXCEPTIONS = {
    "uiSize": "tkinter UI scale; Tauri sizes its own window",
    "updateNotificationsEnabled": "tkinter dataset-update poller; desktop has none",
    "activeVariant": "redundant with variants[].isActive (SealedPage tab bar)",
    "sessionId": "sealed-save persistence key; never displayed",
    "isBuilding": "mirrored locally by SuggestPage around the awaited command",
    "rating": "already inside the rendered label ('(Power: N)')",
    "labelPrefix": "already inside the rendered label",
    "identityColors": "engine-internal; legacy never rendered it",
    "gih": "sample-size tooltip metadata; desktop has no tooltip",
    "ngp": "sample-size tooltip metadata; never displayed even in legacy",
    "rowTag": "recomputed client-side from colors + colorTint",
    "archetypeFit": "legacy 'High' branch unreachable; engine emits lane names",
    "baseWinRate": "raw input to the score; never displayed in legacy either",
    "castProbability": "internal; conveyed via reasoning chips",
    "functionalCmc": "internal computation; never displayed in legacy",
    "startTime": "legacy silent footer metadata; desktop header deliberately lean",
    "logSource": "redundant with 'Live'/'history' switcher labels",
    "isLive": "same label distinction; desktop status dot uses heartbeat mtime",
    "activeDataset": "redundant with DatasetInfo.isActive",
    "seq": "draft://refresh event sequence; handlers re-fetch and ignore the counter",
}

# Payload-type files mirror the VMs — their field names are the contract, not
# readers. Everything else under desktop/src counts as a consumer.
_FIELD_AUDIT_SKIP = {
    os.path.join(FRONTEND_DIR, "api", "types.ts"),
    os.path.join(FRONTEND_DIR, "api", "events.ts"),
}


def _read_frontend_sources():
    for root, _, files in os.walk(FRONTEND_DIR):
        if "node_modules" in root:
            continue
        for name in files:
            path = os.path.join(root, name)
            if not name.endswith((".ts", ".tsx")) or path in _FIELD_AUDIT_SKIP:
                continue
            with open(path, "r", encoding="utf-8") as handle:
                yield handle.read()


def test_every_serialized_field_is_read_or_allowlisted():
    """A field serialized to the frontend but read by no component is an orphan
    the whole-object tests cannot see (v0.18: filter_format passed all three —
    complete on both sides, no UI, no React reader). Every _VM field's camelCase
    alias must appear somewhere in desktop/src — unless the deliberate omission
    is documented in _UNREAD_FIELD_EXCEPTIONS."""
    sources = "\n".join(_read_frontend_sources())
    unread = [
        (cls.__name__, finfo.alias or name)
        for cls in VM_CLASSES
        for name, finfo in cls.model_fields.items()
        if not re.search(rf"\b{finfo.alias or name}\b", sources)
    ]
    offenders = [
        f"{cls}.{alias}" for cls, alias in unread if alias not in _UNREAD_FIELD_EXCEPTIONS
    ]
    assert not offenders, f"serialized fields with no frontend reader: {sorted(offenders)}"


def test_allowlisted_fields_stay_unread():
    """Allowlist-rot check: every exception must be genuinely unread. Wire a
    field up and the frontend starts reading it — remove it from the dict
    instead of letting the reason outlive the omission."""
    sources = "\n".join(_read_frontend_sources())
    now_read = [
        alias
        for alias in _UNREAD_FIELD_EXCEPTIONS
        if re.search(rf"\b{alias}\b", sources)
    ]
    assert not now_read, f"allowlisted aliases now read by the frontend: {sorted(now_read)}"
