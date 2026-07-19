"""
tests/test_bridge_snapshot.py
Bridge-layer tests for the pytauri UI: exercises mtga_bridge's pure modules
(snapshot, services, datasets shims, orchestrator adapter) against a real
ArenaScanner with mock data. No pytauri or tkinter required.
"""

import json
import os
import queue
import sys
import threading
import time
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

from src import constants
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src.log_scanner import ArenaScanner
from src.utils import Result

from mtga_bridge.snapshot import (
    build_draft_state,
    build_taken_cards,
    card_to_vm,
    pool_summary_vm,
)
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.orchestrator_adapter import (
    EVENT_REFRESH,
    EVENT_STATUS,
    OrchestratorAdapter,
)
from mtga_bridge import services
from mtga_bridge.viewmodels import SettingsPatch


# --- Fixtures ----------------------------------------------------------------


def _mock_dataset():
    return {
        "meta": {"version": 3.0, "game_count": 10000},
        "card_ratings": {
            "101": {
                "name": "Green Hulk",
                "cmc": 6,
                "types": ["Creature"],
                "colors": ["G"],
                "rarity": "rare",
                "mana_cost": "{4}{G}{G}",
                "image": ["https://example.com/hulk.jpg"],
                "deck_colors": {
                    "All Decks": {"gihwr": 62.0, "alsa": 2.0, "gih": 5000},
                },
            },
            "102": {
                "name": "Red Bomb Double Pip",
                "cmc": 4,
                "types": ["Creature"],
                "colors": ["R"],
                "rarity": "mythic",
                "mana_cost": "{2}{R}{R}",
                "deck_colors": {"All Decks": {"gihwr": 68.0, "alsa": 1.5}},
            },
            "103": {
                "name": "Black Removal Single Pip",
                "cmc": 2,
                "types": ["Instant"],
                "colors": ["B"],
                "rarity": "common",
                "mana_cost": "{1}{B}",
                "deck_colors": {"All Decks": {"gihwr": 58.0, "alsa": 3.0}},
            },
        },
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    sets_dir = tmp_path / "Sets"
    sets_dir.mkdir()
    logs_dir = tmp_path / "Logs"
    logs_dir.mkdir()
    temp_dir = tmp_path / "Temp"
    temp_dir.mkdir()

    monkeypatch.setattr("src.constants.SETS_FOLDER", str(sets_dir))
    monkeypatch.setattr("src.constants.DRAFT_LOG_FOLDER", str(logs_dir))
    monkeypatch.setattr("src.constants.TEMP_FOLDER", str(temp_dir))

    log_file = tmp_path / "Player.log"
    log_file.write_text("MTGA Log Start\n")

    dataset_path = sets_dir / "TEST_PremierDraft_All_Data.json"
    data = _mock_dataset()
    dataset_path.write_text(json.dumps(data))

    mock_sets = SetDictionary(
        data={
            "Test Set": SetInfo(
                arena=["TEST"], seventeenlands=["TEST"], set_code="TEST"
            )
        }
    )

    config = Configuration()
    config.settings.arena_log_location = str(log_file)
    config.card_data.latest_dataset = os.path.basename(str(dataset_path))

    with patch(
        "src.dataset.check_file_integrity",
        return_value=(Result.VALID, data),
    ):
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))
        scanner.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
        scanner.number_of_players = 8
        yield {"scanner": scanner, "config": config, "log": log_file}


# --- card_to_vm --------------------------------------------------------------


def test_card_to_vm_basic(env):
    scanner = env["scanner"]
    card = scanner.set_data.get_data_by_name(["Green Hulk"])[0]
    vm = card_to_vm(card, "All Decks")
    assert vm.name == "Green Hulk"
    assert vm.mana_cost == "{4}{G}{G}"
    assert vm.cmc == 6.0
    assert vm.colors == ["G"]
    assert vm.stats.gihwr == 62.0
    assert vm.stats.alsa == 2.0
    assert vm.stats.gih == 5000
    assert vm.recommendation is None
    assert not vm.is_picked


def test_card_to_vm_missing_filter_stats(env):
    scanner = env["scanner"]
    card = scanner.set_data.get_data_by_name(["Green Hulk"])[0]
    vm = card_to_vm(card, "WU")  # no stats recorded for this filter
    assert vm.stats.gihwr is None
    assert vm.stats.alsa is None


def test_card_to_vm_picked_flag(env):
    scanner = env["scanner"]
    card = scanner.set_data.get_data_by_name(["Green Hulk"])[0]
    vm = card_to_vm(card, "All Decks", picked_names={"Green Hulk"})
    assert vm.is_picked


def test_card_to_vm_camel_case_serialization(env):
    scanner = env["scanner"]
    card = scanner.set_data.get_data_by_name(["Red Bomb Double Pip"])[0]
    dumped = card_to_vm(card, "All Decks").model_dump(by_alias=True)
    assert "manaCost" in dumped
    assert "isPicked" in dumped
    assert dumped["manaCost"] == "{2}{R}{R}"


# --- pool summary ------------------------------------------------------------


def test_pool_summary(env):
    scanner = env["scanner"]
    pool = [
        scanner.set_data.get_data_by_name(["Green Hulk"])[0],
        scanner.set_data.get_data_by_name(["Black Removal Single Pip"])[0],
    ]
    vm = pool_summary_vm(pool)
    assert vm.card_count == 2
    assert vm.creature_count == 1
    assert vm.noncreature_count == 1
    assert len(vm.cmc_distribution) == 8
    assert vm.color_pips["G"] == 1
    assert vm.color_pips["B"] == 1


# --- build_draft_state -------------------------------------------------------


def test_build_draft_state_empty(env):
    state = build_draft_state(env["scanner"], env["config"])
    assert state.booted
    assert state.pack == 0
    assert state.pack_cards == []
    assert set(state.signals.scores.keys()) == set(constants.CARD_COLORS)
    assert state.log_source == "live"
    assert state.dataset_name == env["config"].card_data.latest_dataset


def test_build_draft_state_with_pool(env):
    scanner = env["scanner"]
    scanner.taken_cards = ["101", "101", "103"]
    state = build_draft_state(scanner, env["config"])
    assert state.taken_count == 3
    assert state.pool_summary is not None
    assert state.pool_summary.card_count == 3


def test_build_taken_cards_dedup(env):
    scanner = env["scanner"]
    scanner.taken_cards = ["101", "101", "103"]
    vm = build_taken_cards(scanner, env["config"])
    names = {c.name: c.count for c in vm.cards}
    assert names["Green Hulk"] == 2
    assert names["Black Removal Single Pip"] == 1
    assert vm.pool_summary.card_count == 3


# --- orchestrator adapter ----------------------------------------------------


class _FakeOrchestrator:
    def __init__(self, arena_file):
        self.update_queue = queue.Queue()
        self.scanner = type("S", (), {"arena_file": arena_file})()


def test_adapter_forwards_events(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("x")
    orch = _FakeOrchestrator(str(log))
    runtime = AppRuntime()
    events = []
    adapter = OrchestratorAdapter(orch, runtime, lambda e, p: events.append((e, p)))
    adapter.start()

    orch.update_queue.put({"status": "Scanning Log..."})
    orch.update_queue.put("REFRESH")
    time.sleep(0.5)
    adapter.stop()
    adapter.join(timeout=2)

    kinds = [e for e, _ in events]
    assert EVENT_STATUS in kinds
    assert EVENT_REFRESH in kinds
    status_payload = next(p for e, p in events if e == EVENT_STATUS)
    assert status_payload == {"text": "Scanning Log..."}
    refresh_payload = next(p for e, p in events if e == EVENT_REFRESH)
    assert refresh_payload["seq"] == 1
    assert runtime.current_seq == 1


def test_adapter_emit_errors_do_not_kill_thread(tmp_path):
    log = tmp_path / "Player.log"
    log.write_text("x")
    orch = _FakeOrchestrator(str(log))
    runtime = AppRuntime()

    def bad_emit(event, payload):
        raise RuntimeError("boom")

    adapter = OrchestratorAdapter(orch, runtime, bad_emit)
    adapter.start()
    orch.update_queue.put("REFRESH")
    time.sleep(0.3)
    assert adapter.is_alive()
    adapter.stop()
    adapter.join(timeout=2)


# --- services: settings ------------------------------------------------------


def test_apply_settings_patch(env, tmp_path):
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    class _Orch:
        def __init__(self):
            self.math_requested = False

        def request_math_update(self):
            self.math_requested = True

        def set_file_and_scan(self, path):
            self.swapped = path

    runtime.orchestrator = _Orch()

    with patch("mtga_bridge.services.write_configuration"):
        vm = services.apply_settings_patch(
            runtime, SettingsPatch(deck_filter="WU", card_colors_enabled=True)
        )

    assert vm.deck_filter == "WU"
    assert vm.card_colors_enabled is True
    assert env["config"].settings.deck_filter == "WU"
    assert runtime.orchestrator.math_requested
    # Cache must be invalidated so the next get_draft_state recomputes
    assert runtime.get_cached_state() is None


def test_settings_vm_round_trip(env):
    vm = services.settings_vm(env["config"])
    dumped = vm.model_dump(by_alias=True)
    assert "deckFilter" in dumped
    assert "arenaLogLocation" in dumped


# --- runtime cache -----------------------------------------------------------


def test_runtime_state_cache():
    runtime = AppRuntime()
    seq = runtime.bump_refresh()
    assert seq == 1
    assert runtime.get_cached_state() is None
    runtime.set_cached_state("STATE")
    assert runtime.get_cached_state() == "STATE"
    runtime.bump_refresh()
    assert runtime.get_cached_state() is None  # invalidated by new seq


# --- dataset shims -----------------------------------------------------------


def test_uiprogress_shims_cross_thread():
    """The duck-typed shims must satisfy UIProgress from a worker thread."""
    from src.ui_progress import UIProgress

    from mtga_bridge.datasets import ChannelProgress, ChannelStatus, ImmediateUI

    received = []

    def send(kind, value, text=""):
        received.append((kind, value, text))

    status = ChannelStatus(send)
    progress = ChannelProgress(send)
    ui = ImmediateUI()
    uip = UIProgress(progress=progress, status=status, ui=ui)

    def worker():
        uip._update_status("downloading...")
        uip._update_progress(25.0)
        uip._update_progress(25.0)

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=2)

    kinds = [k for k, _, _ in received]
    assert "status" in kinds
    assert kinds.count("percent") == 2
    # Increment mode accumulates
    assert received[-1][1] == 50.0
    text = next(t for k, _, t in received if k == "status")
    assert text == "downloading..."
