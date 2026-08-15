"""Seam S3 (ticket 07): per-feature command registration must be complete and
collision-free.

After the commands.py split, each feature module owns a `Commands()` instance
and the package aggregator merges them. A duplicate name would make the later
merge silently clobber the earlier command; a module left out of the
aggregator would drop its whole IPC surface. Read from source because pytauri
is not installed in the root test environment.
"""

import ast
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMANDS_DIR = os.path.join(
    REPO_ROOT, "desktop", "src-tauri", "src-python", "mtga_bridge", "commands"
)


def _feature_modules() -> list[str]:
    """Non-private .py modules in the commands package."""
    assert os.path.isdir(COMMANDS_DIR), f"missing commands package: {COMMANDS_DIR}"
    return sorted(
        name[:-3]
        for name in os.listdir(COMMANDS_DIR)
        if name.endswith(".py") and not name.startswith("_")
    )


def _registered_names(module_name: str) -> list[str]:
    """@commands.command()-decorated function names in a feature module."""
    with open(
        os.path.join(COMMANDS_DIR, f"{module_name}.py"), encoding="utf-8"
    ) as handle:
        tree = ast.parse(handle.read())

    names = []
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
            names.append(node.name)
    return names


def test_feature_command_names_are_unique_across_modules():
    """A duplicate would silently clobber on merge — the frontend would invoke
    the wrong handler for one of the two commands."""
    seen: dict[str, str] = {}
    for module in _feature_modules():
        for name in _registered_names(module):
            assert name not in seen, (
                f"{name} registered in both {seen[name]} and {module}"
            )
            seen[name] = module


def test_aggregator_merges_every_feature_module():
    """commands/__init__ must import each feature module whose commands it
    merges; an unimported module drops its entire IPC surface silently."""
    with open(os.path.join(COMMANDS_DIR, "__init__.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "mtga_bridge.commands":
                imported.update(alias.name for alias in node.names)
            elif node.level == 1 and node.module is None:
                imported.update(alias.name for alias in node.names)

    registering = {m for m in _feature_modules() if _registered_names(m)}
    assert imported == registering, (
        f"unimported feature modules: {sorted(registering - imported)}; "
        f"unused imports: {sorted(imported - registering)}"
    )


def test_aggregated_command_count_is_at_least_the_pre_split_count():
    """The flat commands.py registered 64 commands; the split must not drop
    any (the >50 guard in test_bridge_serialization stays loose on purpose)."""
    total = sum(len(_registered_names(m)) for m in _feature_modules())
    assert total >= 64, f"command count dropped from 64 to {total} during the split"
