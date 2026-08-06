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
    card_stats_vm,
    card_to_vm,
    compute_signals,
    pool_summary_vm,
    recommendation_vm,
)
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.orchestrator_adapter import (
    EVENT_HEARTBEAT,
    EVENT_REFRESH,
    EVENT_STATUS,
    OrchestratorAdapter,
)
from mtga_bridge import services
from mtga_bridge.viewmodels import (
    HeartbeatEvent,
    RefreshEvent,
    SettingsPatch,
    StatusEvent,
)


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
                    "All Decks": {"gihwr": 62.0, "alsa": 2.0, "ata": 2.5, "gih": 5000},
                },
            },
            "102": {
                "name": "Red Bomb Double Pip",
                "cmc": 4,
                "types": ["Creature"],
                "colors": ["R"],
                "rarity": "mythic",
                "mana_cost": "{2}{R}{R}",
                "deck_colors": {"All Decks": {"gihwr": 68.0, "alsa": 1.5, "ata": 1.5}},
            },
            "103": {
                "name": "Black Removal Single Pip",
                "cmc": 2,
                "types": ["Instant"],
                "colors": ["B"],
                "rarity": "common",
                "mana_cost": "{1}{B}",
                "deck_colors": {"All Decks": {"gihwr": 58.0, "alsa": 3.0, "ata": 3.0}},
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


def test_pool_summary_type_counts():
    """typeCounts follows the legacy POOL BALANCE priority: a card counts once,
    into its first matching type in the order Creature → … → Land; basic lands
    are excluded; the card's count field multiplies."""
    pool = [
        {"name": "Goose", "cmc": 1, "types": ["Creature"], "colors": ["G"], "count": 2},
        {"name": "Sword", "cmc": 2, "types": ["Artifact", "Creature"], "colors": ["C"], "count": 1},
        {"name": "Shock", "cmc": 1, "types": ["Instant"], "colors": ["R"], "count": 3},
        {"name": "Wrath", "cmc": 4, "types": ["Sorcery"], "colors": ["W"], "count": 1},
        {"name": "Aura", "cmc": 2, "types": ["Enchantment"], "colors": ["W"], "count": 1},
        {"name": "Walker", "cmc": 4, "types": ["Planeswalker"], "colors": ["G"], "count": 1},
        {"name": "Cave", "cmc": 0, "types": ["Land", "Basic"], "colors": ["W"], "count": 1},
        {"name": "Forest", "cmc": 0, "types": ["Basic", "Land"], "colors": ["G"], "count": 5},
    ]
    vm = pool_summary_vm(pool)
    # Creature: Goose ×2 + Sword (Artifact Creature falls into Creature first)
    assert vm.type_counts["Creature"] == 3
    assert vm.type_counts["Planeswalker"] == 1
    assert vm.type_counts["Battle"] == 0
    assert vm.type_counts["Instant"] == 3
    assert vm.type_counts["Sorcery"] == 1
    assert vm.type_counts["Enchantment"] == 1
    assert vm.type_counts["Artifact"] == 0  # consumed by the Creature priority
    assert vm.type_counts["Land"] == 0  # basics excluded
    assert sum(vm.type_counts.values()) == 9
    # camelCase alias ships to the frontend
    dumped = vm.model_dump(by_alias=True)
    assert dumped["typeCounts"]["Creature"] == 3


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


def test_draft_state_filter_label_carries_the_name_and_rate(env):
    """The masthead's `filterLabel`. Before this it read "Auto (WU)" where the
    tkinter top bar read "(Auto: Azorius 56.3%)"."""
    scanner = env["scanner"]
    scanner.set_data._dataset["color_ratings"] = {"All Decks": 54.0}
    env["config"].settings.deck_filter = constants.FILTER_OPTION_AUTO
    env["config"].settings.filter_format = constants.DECK_FILTER_FORMAT_NAMES

    state = build_draft_state(scanner, env["config"])

    assert state.active_filter == "All Decks"
    assert state.filter_label == "Auto (All Decks 54.0%)"


def test_draft_state_filter_label_without_auto_omits_the_prefix(env):
    scanner = env["scanner"]
    scanner.set_data._dataset["color_ratings"] = {"WU": 56.3}
    env["config"].settings.deck_filter = "WU"
    env["config"].settings.filter_format = constants.DECK_FILTER_FORMAT_NAMES

    state = build_draft_state(scanner, env["config"])

    assert state.filter_label == "Azorius (56.3%)"


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
    assert isinstance(status_payload, StatusEvent)
    assert status_payload.text == "Scanning Log..."
    refresh_payload = next(p for e, p in events if e == EVENT_REFRESH)
    assert isinstance(refresh_payload, RefreshEvent)
    assert refresh_payload.seq == 1
    assert runtime.current_seq == 1


def test_adapter_heartbeat_is_a_view_model(tmp_path):
    """The heartbeat carries logName, which the log switcher reads to follow the
    orchestrator's auto-snap-back. Nothing covered its payload shape before."""
    log = tmp_path / "Player.log"
    log.write_text("x")
    orch = _FakeOrchestrator(str(log))
    runtime = AppRuntime()
    events = []
    adapter = OrchestratorAdapter(orch, runtime, lambda e, p: events.append((e, p)))
    adapter.start()
    time.sleep(0.3)
    adapter.stop()
    adapter.join(timeout=2)

    beat = next(p for e, p in events if e == EVENT_HEARTBEAT)
    assert isinstance(beat, HeartbeatEvent)
    assert beat.log_name == "Player.log"
    assert beat.log_mtime > 0
    assert beat.model_dump() == {"logMtime": beat.log_mtime, "logName": "Player.log"}


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
    assert dumped["desktopTheme"] == constants.DESKTOP_THEME_DEFAULT


def test_settings_vm_includes_deck_mid_distribution(env):
    """The MANA CURVE ideal overlay needs the config's mid-range deck curve;
    it must reach the frontend as deckMidDistribution, or the overlay renders
    empty."""
    vm = services.settings_vm(env["config"])
    dumped = vm.model_dump(by_alias=True)
    assert dumped["deckMidDistribution"] == [0, 0, 4, 3, 2, 1, 0]
    # A config with no card_logic must not crash — the field defaults to [].
    env["config"].card_logic = None
    vm = services.settings_vm(env["config"])
    assert vm.deck_mid_distribution == []


def test_desktop_theme_patch_leaves_tkinter_theme_alone(env):
    """The desktop themes independently of the tkinter app: both read the same
    config.json, and `theme` is a ttkbootstrap palette name (Forest, Vapor, ...)
    that the React UI cannot represent. Narrowing it here would silently strip
    a tkinter user's choice with nothing to restore it."""
    s = env["config"].settings
    s.theme = "Forest"
    runtime = AppRuntime(config=env["config"])

    with patch("mtga_bridge.services.write_configuration"):
        vm = services.apply_settings_patch(
            runtime, SettingsPatch(desktop_theme=constants.DESKTOP_THEME_LIGHT)
        )

    assert vm.desktop_theme == constants.DESKTOP_THEME_LIGHT
    assert s.desktop_theme == constants.DESKTOP_THEME_LIGHT
    assert s.theme == "Forest"
    assert s.theme_base == "clam"
    assert s.theme_custom_path == ""


def test_desktop_theme_does_not_trigger_recompute(env):
    """Appearance is display-only — it must not land in apply_settings_patch's
    math_keys, or every toggle would invalidate the cached draft state."""
    runtime = AppRuntime(config=env["config"])
    runtime.set_cached_state(object())

    class _Orch:
        math_requested = False

        def request_math_update(self):
            self.math_requested = True

    runtime.orchestrator = _Orch()

    with patch("mtga_bridge.services.write_configuration"):
        services.apply_settings_patch(
            runtime, SettingsPatch(desktop_theme=constants.DESKTOP_THEME_DARK)
        )

    assert not runtime.orchestrator.math_requested
    assert runtime.get_cached_state() is not None


# --- services: draft-log list ------------------------------------------------


def _write_log(folder, name, mtime):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x")
    os.utime(path, (mtime, mtime))
    return path


def test_list_draft_logs_orders_newest_first_and_labels(env, tmp_path):
    folder = constants.DRAFT_LOG_FOLDER
    _write_log(folder, "DraftLog_TEST_PremierDraft_aaa.log", 1_700_000_000)
    _write_log(folder, "DraftLog_DSK_QuickDraft_bbb.log", 1_700_009_000)
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.list_draft_logs(runtime)
    history = [log for log in result.logs if not log.is_live]

    assert [log.file_name for log in history] == [
        "DraftLog_DSK_QuickDraft_bbb.log",
        "DraftLog_TEST_PremierDraft_aaa.log",
    ]
    assert history[0].label.startswith("📂 DSK QuickDraft (")
    assert history[1].label.startswith("📂 TEST PremierDraft (")


def test_list_draft_logs_labels_a_malformed_name(env):
    """A name that doesn't carry set/event still has to render — the legacy
    dropdown fell back to UNKNOWN/Draft rather than dropping the entry."""
    _write_log(constants.DRAFT_LOG_FOLDER, "DraftLog_weird.log", 1_700_000_000)
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    entry = next(
        log
        for log in services.list_draft_logs(runtime).logs
        if log.file_name == "DraftLog_weird.log"
    )
    assert entry.label.startswith("📂 UNKNOWN Draft (")


def test_list_draft_logs_puts_the_live_log_first(env):
    _write_log(constants.DRAFT_LOG_FOLDER, "DraftLog_TEST_PremierDraft_a.log", 1_700_1)
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.list_draft_logs(runtime)

    assert result.logs[0].is_live
    assert result.logs[0].file_name == os.path.basename(str(env["log"]))
    assert result.logs[0].label.startswith("🔴 Live:")
    assert result.current == os.path.basename(str(env["log"]))


def test_list_draft_logs_omits_a_missing_live_log(env):
    env["config"].settings.arena_log_location = "/tmp/does-not-exist/Player.log"
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    assert not any(log.is_live for log in services.list_draft_logs(runtime).logs)


def test_list_draft_logs_survives_a_null_scanner(env):
    """The command carries no _require_booted, so it can be called pre-boot."""
    runtime = AppRuntime(config=env["config"], scanner=None)

    result = services.list_draft_logs(runtime)

    assert result.current == ""
    assert result.logs[0].label == "🔴 Live: Arena"


def test_list_draft_logs_resolves_the_live_set_display_name(env):
    """The live entry names the set the way the set list does ("Test Set"),
    not the raw code — the legacy dropdown did the same lookup."""
    scanner = env["scanner"]
    scanner.draft_sets = ["TEST"]
    runtime = AppRuntime(config=env["config"], scanner=scanner)

    assert services.list_draft_logs(runtime).logs[0].label == "🔴 Live: Test Set"


# --- services: filter options ------------------------------------------------


def _option(result, key):
    return next(o for o in result.options if o.key == key)


def _patch_color_ratings(scanner, ratings):
    """The fixture dataset carries no color_ratings block, so every rate would
    otherwise be None and the win-rate assertions would pass vacuously."""
    scanner.set_data._dataset["color_ratings"] = ratings


def test_get_filter_options_returns_every_deck_filter(env):
    """SettingsPage renders this list verbatim, so it must be the full set
    rather than the abridged copy the page used to hardcode."""
    env["config"].settings.deck_filter = "WU"
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.get_filter_options(runtime)

    assert [o.key for o in result.options] == list(constants.DECK_FILTERS)
    assert len(result.options) == 33
    assert result.active == "WU"


def test_filter_options_label_under_the_colors_format(env):
    """The Colors format shows the raw key, which is what the page rendered
    before `filter_format` had any UI."""
    env["config"].settings.filter_format = constants.DECK_FILTER_FORMAT_COLORS
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.get_filter_options(runtime)

    assert _option(result, "WU").label == "WU"


def test_filter_options_label_under_the_names_format(env):
    """The Names format is the legacy retrieve_color_win_rate behaviour: the
    guild name, not the color pair."""
    env["config"].settings.filter_format = constants.DECK_FILTER_FORMAT_NAMES
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.get_filter_options(runtime)

    assert _option(result, "WU").label == "Azorius"
    # Auto and All Decks are absent from COLOR_NAMES_DICT and must pass through
    # rather than falling back to something empty.
    assert _option(result, "Auto").label == "Auto"
    assert _option(result, "All Decks").label == "All Decks"


def test_filter_options_carry_the_archetype_win_rate(env):
    """The gap this closes: FilterOptionsVM shipped no winrate, so the desktop
    dropdown read `WU` where the tkinter one read `WU (56.3%)`."""
    _patch_color_ratings(env["scanner"], {"WU": 56.3})
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.get_filter_options(runtime)

    assert _option(result, "WU").win_rate == 56.3


def test_filter_options_win_rate_is_none_when_17lands_has_no_rating(env):
    """None rather than 0.0: an archetype can genuinely round to zero, and the
    dropdown has to tell "no data" from "terrible"."""
    _patch_color_ratings(env["scanner"], {"WU": 56.3})
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.get_filter_options(runtime)

    assert _option(result, "UB").win_rate is None


def test_filter_options_auto_detected_label_combines_name_and_rate(env):
    """SettingsPage's `Auto: ...` hint reads this field."""
    _patch_color_ratings(env["scanner"], {"All Decks": 54.0})
    env["config"].settings.filter_format = constants.DECK_FILTER_FORMAT_NAMES
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.get_filter_options(runtime)

    # An empty pool detects as All Decks, which has a rating in this fixture.
    assert result.auto_detected == "All Decks"
    assert result.auto_detected_label == "All Decks (54.0%)"


def test_filter_options_without_a_scanner_reports_no_rates(env):
    """get_filter_options runs before boot completes, when runtime.scanner is
    still None — it must still return the full option list."""
    runtime = AppRuntime(config=env["config"], scanner=None)

    result = services.get_filter_options(runtime)

    assert len(result.options) == 33
    assert all(o.win_rate is None for o in result.options)
    assert result.auto_detected_label == ""


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


# --- card_stats_vm -----------------------------------------------------------


def test_card_stats_reads_the_active_filter():
    """Every rate on the Dashboard is filter-scoped; reading the wrong lane
    shows a card's mono-color numbers under a two-color deck."""
    card = {
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {"gihwr": 55.0, "alsa": 4.0},
            "WU": {"gihwr": 62.5, "alsa": 2.0},
        }
    }
    assert card_stats_vm(card, "WU").gihwr == 62.5
    assert card_stats_vm(card, "All Decks").gihwr == 55.0


def test_card_stats_are_all_none_for_an_unknown_filter():
    card = {constants.DATA_FIELD_DECK_COLORS: {"All Decks": {"gihwr": 55.0}}}
    stats = card_stats_vm(card, "BG")

    assert stats.gihwr is None
    assert stats.alsa is None
    assert stats.gih is None


def test_card_stats_round_the_rate_fields():
    card = {constants.DATA_FIELD_DECK_COLORS: {"All Decks": {"gihwr": 55.6789}}}
    assert card_stats_vm(card, "All Decks").gihwr == 55.7


def test_card_stats_coerce_sample_counts_to_int():
    """gih/ngp arrive as floats from the 17Lands JSON but are sample counts;
    the UI renders them as bare integers."""
    card = {
        constants.DATA_FIELD_DECK_COLORS: {"All Decks": {"gih": 5000.0, "ngp": 1200.7}}
    }
    stats = card_stats_vm(card, "All Decks")

    assert stats.gih == 5000
    assert stats.ngp == 1200
    assert isinstance(stats.gih, int)


def test_card_stats_treat_a_blank_string_as_missing():
    """The dataset uses "" for a stat with no data. Coerced to a number it
    would render as a real 0% win rate."""
    card = {constants.DATA_FIELD_DECK_COLORS: {"All Decks": {"gihwr": "", "gih": ""}}}
    stats = card_stats_vm(card, "All Decks")

    assert stats.gihwr is None
    assert stats.gih is None


def test_card_stats_survive_an_unparseable_value():
    card = {constants.DATA_FIELD_DECK_COLORS: {"All Decks": {"gihwr": "N/A"}}}
    assert card_stats_vm(card, "All Decks").gihwr is None


def test_card_stats_handle_a_card_with_no_deck_colors():
    assert card_stats_vm({}, "All Decks").gihwr is None


# --- recommendation_vm -------------------------------------------------------


def test_recommendation_vm_carries_every_field():
    from src.advisor.schema import Recommendation

    rec = Recommendation(
        card_name="Green Hulk",
        base_win_rate=62.0,
        contextual_score=88.5,
        z_score=1.4,
        cast_probability=0.92,
        wheel_chance=15.0,
        functional_cmc=6.0,
        reasoning=["Elite bomb", "Wheels 15%"],
        is_elite=True,
        archetype_fit="GW Aggro",
        tags=["bomb"],
    )
    vm = recommendation_vm(rec)

    assert vm.card_name == "Green Hulk"
    assert vm.contextual_score == 88.5
    assert vm.reasoning == ["Elite bomb", "Wheels 15%"]
    assert vm.is_elite is True
    assert vm.archetype_fit == "GW Aggro"
    assert vm.tags == ["bomb"]


def test_recommendation_vm_serializes_as_camel_case():
    from src.advisor.schema import Recommendation

    dumped = recommendation_vm(
        Recommendation(
            card_name="Green Hulk",
            base_win_rate=62.0,
            contextual_score=88.5,
            z_score=1.4,
            cast_probability=0.92,
            wheel_chance=15.0,
            functional_cmc=6.0,
            reasoning=[],
        )
    ).model_dump()

    assert "cardName" in dumped
    assert "card_name" not in dumped


# --- compute_signals ---------------------------------------------------------


def _signal_scanner(env, history):
    scanner = env["scanner"]
    scanner.draft_history = history
    return scanner


# The fixture's baseline (SetMetrics over the three cards) is 62.67, and
# calculate_pack_signals ignores any card at or below it. Only Red Bomb (id 102,
# gihwr 68.0, ata 1.5) clears that bar — Green Hulk at 62.0 scores 0.0 no matter
# how late it is seen. Every test below therefore passes 102, or the whole
# section reads as "signals work" while measuring nothing.
SCORING_CARD = 102


def test_signals_start_at_zero_for_every_color(env):
    scores = compute_signals(_signal_scanner(env, []))

    assert set(scores) == set(constants.CARD_COLORS)
    assert set(scores.values()) == {0.0}


def test_signals_accumulate_across_packs(env):
    """Each pack contributes to the running lane score, so the same pack seen
    twice must count twice — a per-pack overwrite would make only the latest
    pack visible."""
    one = compute_signals(
        _signal_scanner(env, [{"Pack": 1, "Pick": 6, "Cards": [SCORING_CARD]}])
    )
    two = compute_signals(
        _signal_scanner(
            env,
            [
                {"Pack": 1, "Pick": 6, "Cards": [SCORING_CARD]},
                {"Pack": 3, "Pick": 6, "Cards": [SCORING_CARD]},
            ],
        )
    )

    assert one["R"] > 0.0
    assert two["R"] == pytest.approx(one["R"] * 2)


def test_signals_skip_pack_two(env):
    """Pack 2 passes come from the opposite direction, so its lateness tells
    you nothing about the lane packs 1 and 3 feed."""
    scores = compute_signals(
        _signal_scanner(env, [{"Pack": 2, "Pick": 6, "Cards": [SCORING_CARD]}])
    )

    assert set(scores.values()) == {0.0}


def test_signals_score_the_colors_actually_seen(env):
    scores = compute_signals(
        _signal_scanner(env, [{"Pack": 1, "Pick": 8, "Cards": [SCORING_CARD]}])
    )

    assert scores["R"] > 0.0
    assert scores["W"] == 0.0
    assert scores["G"] == 0.0


def test_signals_ignore_a_card_at_or_below_the_baseline(env):
    """A card whose win rate is average is not evidence of an open lane, no
    matter how late it wheels — this is the guard that made three of the tests
    above vacuous when the fixture carried no above-baseline card."""
    scores = compute_signals(
        _signal_scanner(env, [{"Pack": 1, "Pick": 12, "Cards": [101, 103]}])
    )

    assert set(scores.values()) == {0.0}


def test_signals_grow_with_lateness(env):
    """The score is lateness x quality, so the same card seen later is a
    stronger signal. Equal scores would mean the pick number is unread."""
    early = compute_signals(
        _signal_scanner(env, [{"Pack": 1, "Pick": 4, "Cards": [SCORING_CARD]}])
    )
    late = compute_signals(
        _signal_scanner(env, [{"Pack": 1, "Pick": 10, "Cards": [SCORING_CARD]}])
    )

    assert late["R"] > early["R"] > 0.0


def test_signals_ignore_a_card_seen_before_its_average_pick(env):
    """Lateness is pick - ata; a card taken earlier than average has passed
    nobody, so a negative lateness must not subtract from the lane."""
    scores = compute_signals(
        _signal_scanner(env, [{"Pack": 1, "Pick": 1, "Cards": [SCORING_CARD]}])
    )

    assert scores["R"] == 0.0


# --- services.get_boot_status ------------------------------------------------


def test_boot_status_before_boot_completes():
    runtime = AppRuntime(config=Configuration())
    runtime.last_boot_message = "Locating Player.log..."

    status = services.get_boot_status(runtime)

    assert status.booted is False
    assert status.last_message == "Locating Player.log..."
    assert status.error is None


def test_boot_status_after_boot_completes():
    """The webview can attach after boot://complete already fired, so this is
    the only way a late subscriber learns boot finished."""
    runtime = AppRuntime(config=Configuration())
    runtime.booted.set()

    assert services.get_boot_status(runtime).booted is True


def test_boot_status_reports_a_failure():
    runtime = AppRuntime(config=Configuration())
    runtime.boot_error = "Player.log not found"

    status = services.get_boot_status(runtime)

    assert status.booted is False
    assert status.error == "Player.log not found"


# --- services.list_available_sets --------------------------------------------


def test_available_sets_come_from_the_scanner(env):
    runtime = AppRuntime(config=env["config"], scanner=env["scanner"])

    result = services.list_available_sets(runtime)

    assert [(s.code, s.name) for s in result.sets] == [("TEST", "Test Set")]


def test_available_sets_fall_back_to_the_name_without_a_code(env):
    """A set with no 17Lands code still has to be selectable in the Datasets
    dropdown, which keys on code."""
    scanner = env["scanner"]
    scanner.set_list = SetDictionary(
        data={"Mystery Set": SetInfo(arena=["MYS"], seventeenlands=[])}
    )
    runtime = AppRuntime(config=env["config"], scanner=scanner)

    assert services.list_available_sets(runtime).sets[0].code == "Mystery Set"


def test_available_sets_are_empty_before_the_scanner_exists():
    """list_available_sets is reachable from the Datasets page while boot is
    still running, so a None scanner is a normal state, not an error."""
    runtime = AppRuntime(config=Configuration())

    assert services.list_available_sets(runtime).sets == []


# --- services.export_to_sealeddeck_tech --------------------------------------


def test_sealeddeck_export_rejects_an_empty_deck():
    result = services.export_to_sealeddeck_tech("   ")

    assert result.ok is False
    assert result.message == "Deck is empty."


def test_sealeddeck_export_returns_the_share_url():
    payload = "4 Green Hulk\n"
    with patch("requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"url": "https://sealeddeck.tech/abc123"}
        result = services.export_to_sealeddeck_tech(payload)

    assert result.ok is True
    assert result.url == "https://sealeddeck.tech/abc123"
    assert post.call_args.kwargs["json"] == {"pool": payload}


def test_sealeddeck_export_falls_back_to_the_clipboard_on_a_network_error():
    """The deck itself must survive the failure — the fallback text is what
    the user pastes manually."""
    payload = "4 Green Hulk\n"
    with patch("requests.post", side_effect=OSError("no route to host")):
        result = services.export_to_sealeddeck_tech(payload)

    assert result.ok is False
    assert result.text == payload
    assert "clipboard" in result.message


def test_sealeddeck_export_treats_a_missing_url_as_a_failure():
    """HTTP 200 with no url is a successful request that produced nothing
    shareable; reporting ok would leave the button looking like it worked."""
    with patch("requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {}
        result = services.export_to_sealeddeck_tech("4 Green Hulk\n")

    assert result.ok is False
    # SealedPage.tsx:188 gates the share link on `shareUrl &&`, so the failure
    # value has to be falsy — SealedDeckTechVM.url defaults to "", not None.
    assert result.url == ""


def test_sealeddeck_export_treats_a_non_200_as_a_failure():
    with patch("requests.post") as post:
        post.return_value.status_code = 503
        result = services.export_to_sealeddeck_tech("4 Green Hulk\n")

    assert result.ok is False
