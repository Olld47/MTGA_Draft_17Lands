"""Guardrail: the tkinter UI is frozen — bug fixes only, no new features.

Directional decision from `.scratch/architecture-review/issues/01-dup-app-layer-dual-ui.md`
(Option B): the desktop app is the sole evolution line; tkinter is a legacy
distribution channel kept alive for bug fixes. This module is a policy tripwire,
not a behavioural test — the frozen baseline is the tkinter surface at freeze
time, and any seam crossing it must be consciously reviewed (and the baseline
bumped in this file) before landing.

Three seams:
- S1: the set of window modules under `src/ui/windows/` is frozen.
- S2: the set of notebook tabs registered in `app_layout.py` is frozen.
- S3: each tkinter view class stays within its freeze-time line budget, so
      business logic cannot pile back into the view layer.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_DIR = REPO_ROOT / "src" / "ui" / "windows"
APP_LAYOUT = REPO_ROOT / "src" / "ui" / "app_layout.py"
DASHBOARD_RECAP = REPO_ROOT / "src" / "ui" / "dashboard_recap.py"

# --- S1: frozen window module allowlist (excludes __init__.py) ---
FROZEN_WINDOW_MODULES = {
    "compare",
    "custom_deck",
    "download",
    "overlay",
    "practice_dialog",
    "sealed_studio",
    "settings",
    "splash",
    "suggest_deck",
    "taken_cards",
    "tier_list_panel",
}

# --- S2: frozen notebook tab labels (from AppLayoutManager._build_panels) ---
FROZEN_NOTEBOOK_TABS = {
    "Datasets",
    "Card Pool",
    "Deck Builder",
    "Custom Deck",
    "Comparisons",
    "Tier Lists",
}

# --- S3: frozen line budgets per tkinter view module (incl. dashboard_recap) ---
FROZEN_LINE_BUDGETS = {
    "compare.py": 203,
    "custom_deck.py": 1594,
    "dashboard_recap.py": 455,
    "download.py": 561,
    "overlay.py": 648,
    "practice_dialog.py": 263,
    "sealed_studio.py": 1638,
    "settings.py": 262,
    "splash.py": 162,
    "suggest_deck.py": 1345,
    "taken_cards.py": 373,
    "tier_list_panel.py": 218,
}


def _window_modules():
    return {
        p.stem for p in WINDOWS_DIR.glob("*.py") if p.name != "__init__.py"
    }


def _notebook_tabs():
    """Extract the `text=` labels from every `self.notebook.add(...)` call."""
    tree = ast.parse(APP_LAYOUT.read_text(encoding="utf-8"))
    tabs = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_notebook_add = (
            isinstance(func, ast.Attribute)
            and func.attr == "add"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "notebook"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
        )
        if not is_notebook_add:
            continue
        for kw in node.keywords:
            if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                tabs.add(str(kw.value.value).strip())
    return tabs


def _window_line_counts():
    counts = {}
    for p in WINDOWS_DIR.glob("*.py"):
        if p.name == "__init__.py":
            continue
        counts[p.name] = sum(1 for _ in p.open(encoding="utf-8"))
    counts["dashboard_recap.py"] = sum(
        1 for _ in DASHBOARD_RECAP.open(encoding="utf-8")
    )
    return counts


class TestTkinterFreeze:
    def test_s1_window_module_surface_is_frozen(self):
        """No new tkinter window modules — a new window is a new feature."""
        assert _window_modules() == FROZEN_WINDOW_MODULES

    def test_s2_notebook_tabs_are_frozen(self):
        """The notebook tab set is frozen — a new/replaced tab is a new feature."""
        assert _notebook_tabs() == FROZEN_NOTEBOOK_TABS

    def test_s3_view_classes_stay_within_budget(self):
        """No tkinter view class may grow past its freeze-time line budget."""
        actual = _window_line_counts()
        assert set(actual) == set(FROZEN_LINE_BUDGETS), (
            "every tkinter window must carry a frozen budget in FROZEN_LINE_BUDGETS"
        )
        for name, budget in FROZEN_LINE_BUDGETS.items():
            assert actual[name] <= budget, (
                f"{name} grew past its frozen budget "
                f"({actual[name]} > {budget}): business logic belongs in src/ "
                "or the desktop bridge, not the tkinter view layer"
            )
