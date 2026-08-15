"""Guardrail: the shared core must not reach into a UI toolkit.

Layering enforcement from `.scratch/architecture-review/issues/02`
(narrowed by decision 01; the tkinter UI was removed 2026-08-15): the
desktop bridge and every non-UI module in `src/` must not import
tkinter/ttkbootstrap, and the bridge must not import from the `src.ui`
package at all. `src.ui` no longer exists — the import guard doubles as a
reintroduction tripwire. AST-based, so comments or docstrings that merely
mention "tkinter" don't trip it — only real import statements do.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
BRIDGE_ROOT = REPO_ROOT / "desktop" / "src-tauri" / "src-python" / "mtga_bridge"
ROOT_ENTRY = REPO_ROOT / "main.py"

FORBIDDEN_TOP_LEVEL = {"tkinter", "ttkbootstrap"}
UI_PACKAGE = "src.ui"


def _py_files(root):
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _import_module_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.append(node.module)
    return names


def _forbidden_top_level_imports(source):
    tree = ast.parse(source)
    return sorted(
        name
        for name in _import_module_names(tree)
        if name.split(".", 1)[0] in FORBIDDEN_TOP_LEVEL
    )


def _ui_package_imports(source):
    tree = ast.parse(source)
    return sorted(
        name
        for name in _import_module_names(tree)
        if name == UI_PACKAGE or name.startswith(UI_PACKAGE + ".")
    )


class TestLayering:
    def test_shared_src_has_no_tkinter_import(self):
        offenders = {}
        for path in _py_files(SRC_ROOT):
            bad = _forbidden_top_level_imports(path.read_text(encoding="utf-8"))
            if bad:
                offenders[str(path.relative_to(REPO_ROOT))] = bad
        assert not offenders, offenders

    def test_shared_src_does_not_import_the_ui_package(self):
        offenders = {}
        for path in _py_files(SRC_ROOT):
            bad = _ui_package_imports(path.read_text(encoding="utf-8"))
            if bad:
                offenders[str(path.relative_to(REPO_ROOT))] = bad
        assert not offenders, offenders

    def test_bridge_does_not_import_the_ui_package(self):
        offenders = {}
        for path in _py_files(BRIDGE_ROOT):
            bad = _ui_package_imports(path.read_text(encoding="utf-8"))
            if bad:
                offenders[str(path.relative_to(REPO_ROOT))] = bad
        assert not offenders, offenders

    def test_root_entry_has_no_ui_toolkit_import(self):
        """main.py is the shared launcher; importing tkinter/ttkbootstrap or
        the deleted src.ui package here would reintroduce a Tk path."""
        bad = _forbidden_top_level_imports(ROOT_ENTRY.read_text(encoding="utf-8"))
        assert not bad, bad
        bad = _ui_package_imports(ROOT_ENTRY.read_text(encoding="utf-8"))
        assert not bad, bad
