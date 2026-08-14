"""Seam S1 (ticket 07): src.constants split into domain modules.

The 79 callers import specific names via `from src.constants import X`, so the
package aggregator must re-export the full public surface with no cross-module
name collisions. Values below are independent known literals from the domain
(MTGA log strings, WUBRG order, 17Lands API field names), not recomputed from
the code under test.
"""

import importlib
import pkgutil
import tomllib
from pathlib import Path

import pytest

import src.constants

REPO_ROOT = Path(__file__).resolve().parent.parent


def _submodules() -> list[str]:
    """Every non-private module in the src.constants package."""
    assert hasattr(src.constants, "__path__"), "src.constants must be a package"
    return sorted(
        m.name
        for m in pkgutil.iter_modules(src.constants.__path__)
        if not m.name.startswith("_")
    )


def _load(module: str):
    return importlib.import_module(f"src.constants.{module}")


# --- Aggregator structure ---------------------------------------------------


def test_every_domain_module_defines_all():
    """Star imports in the aggregator would otherwise leak `os`, `next`, etc."""
    for name in _submodules():
        mod = _load(name)
        assert hasattr(mod, "__all__"), f"src.constants.{name} is missing __all__"
        assert mod.__all__, f"src.constants.{name} has an empty __all__"


def test_no_name_collisions_across_domain_modules():
    """A name exported by two modules would silently shadow in the aggregator."""
    seen: dict[str, str] = {}
    for name in _submodules():
        for attr in _load(name).__all__:
            assert attr not in seen, (
                f"{attr} exported by both {seen[attr]} and src.constants.{name}"
            )
            seen[attr] = name


def test_aggregator_reexports_every_domain_name():
    """79 importers rely on `from src.constants import X`; nothing may fall out."""
    missing = [
        attr
        for name in _submodules()
        for attr in _load(name).__all__
        if not hasattr(src.constants, attr)
    ]
    assert not missing, f"not re-exported from src.constants: {missing}"


def test_version_single_source_matches_pyproject():
    """AGENTS.md: tkinter APPLICATION_VERSION is edited in constants AND
    pyproject.toml. The split must keep them coupled."""
    from src.constants.versions import APPLICATION_VERSION

    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        project_version = tomllib.load(handle)["tool"]["poetry"]["version"]
    assert APPLICATION_VERSION == project_version


# --- Canonical domain literals ----------------------------------------------


@pytest.mark.parametrize(
    ("module", "attr", "expected"),
    [
        # versions
        ("versions", "OLD_APPLICATION_VERSION", "4.17"),
        # colors — WUBRG ordering is a documented repo invariant
        ("colors", "CARD_COLOR_SYMBOL_WHITE", "W"),
        ("colors", "CARD_COLORS", ["W", "U", "B", "R", "G"]),
        ("colors", "CARD_COLOR_LABEL_GREEN", "Green"),
        # limited types
        ("limited", "LIMITED_TYPE_SEALED", 5),
        ("limited", "LIMITED_TYPE_DRAFT_PICK_TWO", 7),
        ("limited", "LIMITED_TYPE_STRING_DRAFT_QUICK", "QuickDraft"),
        # log event strings (fuzzy-matched by ArenaScanner)
        ("event_strings", "DRAFT_LOG_PREFIX", "DraftLog_"),
        ("event_strings", "DRAFT_START_STRING_PREMIER", "[UnityCrossThreadLogger]==> Event_Join "),
        ("event_strings", "DRAFT_PICK_STRING_QUICK", "[UnityCrossThreadLogger]==> BotDraft_DraftPick "),
        ("event_strings", "PICK_TWO_EVENT_STRING", "PickTwo"),
        # paths / platform
        ("paths", "LOG_NAME", "Player.log"),
        ("paths", "PLATFORM_ID_OSX", "darwin"),
        ("paths", "PLATFORM_ID_WINDOWS", "win32"),
        # local MTGA database schema
        ("database", "LOCAL_DATABASE_TABLE_CARDS", "Cards"),
        # 17Lands data fields
        ("data_fields", "DATA_FIELD_GIHWR", "gihwr"),
        ("data_fields", "DATA_FIELD_17LANDS_GIHWR", "ever_drawn_win_rate"),
        ("data_fields", "TIME_PERIOD_DEFAULT", "ALL_TIME"),
        ("data_fields", "TIME_PERIOD_DEFAULT_LABEL", "All Time"),
        ("data_fields", "COLUMN_FIELD_LABELS", {"value": "VALUE: Advisor Tactical Score", "wheel": "WHEEL: Probability of Wheeling"}),
        # sets
        ("sets", "SET_LIST_17LANDS", "17Lands"),
        ("sets", "SET_SELECTION_ALL", "ALL"),
        # cards
        ("cards", "CARD_TYPE_LAND", "Land"),
        ("cards", "CARD_RARITY_MYTHIC", "mythic"),
        ("cards", "CARD_TYPE_SELECTION_ALL", "All Cards"),
        # ui defaults
        ("ui", "DESKTOP_THEME_DEFAULT", "System"),
        ("ui", "UI_SIZE_DEFAULT", "100%"),
        ("ui", "DEFAULT_UI_DEFAULT", "desktop"),
        ("ui", "LETTER_GRADE_A_PLUS", "A+"),
        # dataset / remote
        ("datasets", "SEVENTEENLANDS_DATA_FILTERS_URL", "https://www.17lands.com/data/filters"),
        ("datasets", "DATASET_DOWNLOAD_RATE_LIMIT_SEC", 60),
        ("datasets", "CARD_RATINGS_ATTEMPT_MAX", 5),
    ],
)
def test_domain_module_literal(module: str, attr: str, expected):
    actual = getattr(_load(module), attr)
    if isinstance(expected, dict):
        assert expected.items() <= actual.items(), f"{module}.{attr} missing {expected}"
    else:
        assert actual == expected


def test_wheel_coefficients_are_six_cubics():
    """One cubic per pack, fed to np.polyval with ALSA."""
    from src.constants.wheel import WHEEL_COEFFICIENTS

    assert len(WHEEL_COEFFICIENTS) == 6
    assert all(len(cubic) == 4 for cubic in WHEEL_COEFFICIENTS)


def test_fixing_keywords_are_lowercase():
    """Scanned case-insensitively against oracle text (constants comment). The
    `up to X` placeholder carries a literal uppercase X by design."""
    from src.constants.fixing import FIXING_KEYWORDS, FIXING_NAMES

    assert all(kw == kw.lower() for kw in FIXING_KEYWORDS if "X" not in kw)
    assert all(name == name.lower() for name in FIXING_NAMES)
