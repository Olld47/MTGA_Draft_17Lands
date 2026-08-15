"""
tests/test_bridge_tier.py
Bridge-layer tests for the tier-list management port
(mtga_bridge.tier_service). Exercises list / import / delete against a real
on-disk tier folder and a mocked 17Lands API. No pytauri or tkinter.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Make the bridge package importable from the root test run
BRIDGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "desktop",
    "src-tauri",
    "src-python",
)
if BRIDGE_PATH not in sys.path:
    sys.path.insert(0, BRIDGE_PATH)

import src.tier_list as tier_list_mod
from src.tier_list import Meta, Rating, TierList, TIER_FILE_PREFIX

from mtga_bridge import tier_service
from mtga_bridge.viewmodels import TierActionVM, TierListsVM


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def tier_env(tmp_path, monkeypatch):
    """Point the tier module at a fresh temp folder and reset its file cache."""
    folder = tmp_path / "Tier"
    folder.mkdir()
    monkeypatch.setattr(tier_list_mod, "TIER_FOLDER", str(folder))
    monkeypatch.setattr(tier_service, "TIER_FOLDER", str(folder))
    # Invalidate the module-level file cache so each test starts clean
    monkeypatch.setattr(tier_list_mod, "_TIER_CACHE", {"mtime": 0.0, "files": []})
    return folder


def _write_tier(folder, set_code, label, date, stamp):
    tl = TierList(
        meta=Meta(collection_date=date, label=label, set=set_code, url="x"),
        ratings={"White Knight": Rating(rating="A ", comment="great")},
    )
    filename = f"{TIER_FILE_PREFIX}_{set_code}_{stamp}.txt"
    tl.to_file(os.path.join(str(folder), filename))
    return filename


# --- listing -----------------------------------------------------------------


def test_list_empty(tier_env):
    vm = tier_service.list_tier_lists()
    assert isinstance(vm, TierListsVM)
    assert vm.lists == []
    assert vm.sets == []


def test_list_sorted_newest_first(tier_env):
    _write_tier(tier_env, "TDM", "Older", "2026-01-01 10:00:00", 1000)
    _write_tier(tier_env, "TDM", "Newer", "2026-06-01 10:00:00", 2000)
    vm = tier_service.list_tier_lists()
    assert [e.label for e in vm.lists] == ["Newer", "Older"]
    assert vm.sets == ["TDM"]


def test_list_filter_by_set(tier_env):
    _write_tier(tier_env, "TDM", "Dragons", "2026-01-01 10:00:00", 1000)
    _write_tier(tier_env, "FIN", "Fantasy", "2026-02-01 10:00:00", 2000)
    vm = tier_service.list_tier_lists("FIN")
    assert [e.set_code for e in vm.lists] == ["FIN"]
    assert set(vm.sets) == {"TDM", "FIN"}
    assert vm.active_filter == "FIN"


def test_list_out_of_range_filter_resets(tier_env):
    _write_tier(tier_env, "TDM", "Dragons", "2026-01-01 10:00:00", 1000)
    vm = tier_service.list_tier_lists("NOPE")
    assert vm.active_filter == ""
    assert len(vm.lists) == 1


# --- import ------------------------------------------------------------------


def test_import_rejects_bad_url(tier_env):
    res = tier_service.import_tier_list("https://example.com/x", "Label")
    assert res.ok is False
    assert "17lands" in res.message.lower()


def test_import_rejects_missing_label(tier_env):
    res = tier_service.import_tier_list(
        "https://www.17lands.com/tier_list/abc", ""
    )
    assert res.ok is False
    assert "label" in res.message.lower()


def test_import_success(tier_env):
    fake = TierList(
        meta=Meta(collection_date="2026-06-01 10:00:00", label="api", set="TDM"),
        ratings={"White Knight": Rating(rating="A ")},
    )
    with patch.object(TierList, "from_api", return_value=fake):
        res = tier_service.import_tier_list(
            "https://www.17lands.com/tier_list/abc", "Pro Review"
        )
    assert res.ok
    # Persisted, indexed, and the custom label overrode the API name
    assert len(res.lists.lists) == 1
    assert res.lists.lists[0].label == "Pro Review"
    assert res.lists.lists[0].set_code == "TDM"


def test_import_api_failure(tier_env):
    with patch.object(TierList, "from_api", return_value=None):
        res = tier_service.import_tier_list(
            "https://www.17lands.com/tier_list/abc", "Pro Review"
        )
    assert res.ok is False
    assert res.lists.lists == []


# --- delete ------------------------------------------------------------------


def test_delete_removes_file(tier_env):
    name = _write_tier(tier_env, "TDM", "Dragons", "2026-01-01 10:00:00", 1000)
    res = tier_service.delete_tier_lists([name])
    assert res.ok
    assert res.lists.lists == []
    assert not os.path.exists(os.path.join(str(tier_env), name))


def test_delete_nothing_selected(tier_env):
    res = tier_service.delete_tier_lists([])
    assert res.ok is False


# --- serialization -----------------------------------------------------------


def test_action_serializes_camel_case(tier_env):
    _write_tier(tier_env, "TDM", "Dragons", "2026-01-01 10:00:00", 1000)
    dumped = tier_service.list_tier_lists().model_dump(by_alias=True)
    assert "activeFilter" in dumped
    assert "lists" in dumped
    assert "setCode" in dumped["lists"][0]
    assert "fileName" in dumped["lists"][0]
