"""
tests/test_bridge_boot.py
Behavioural tests for mtga_bridge.boot — the headless boot sequence.

plan.md excused this module from testing on the grounds that it "imports
pytauri". It does not: boot.py imports argparse/logging/sys/anyio only, and
defers every other import into the function bodies. So it sat at 97 lines and
zero tests behind a reason that was never true.

Everything boot.py touches is imported lazily inside _boot_blocking, so the
patch targets here are the *callee's own module* (src.bootstrap.load_data),
not an attribute of mtga_bridge.boot.
"""

import os
import sys
import threading
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import anyio
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

from src.boot_sync import BOOT_NOT_ATTEMPTED, BootSyncOutcome
from src.configuration import Configuration

from mtga_bridge import boot
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import BootComplete, BootError, BootProgress


# --- Fixtures ----------------------------------------------------------------


def _mock_scanner(event=("TEST", "PremierDraft"), pack=2, pick=7):
    scanner = MagicMock()
    scanner.retrieve_current_limited_event.return_value = event
    scanner.retrieve_current_pack_and_pick.return_value = (pack, pick)
    return scanner


class Recorder:
    """Stands in for the Emitter.emit closure __init__.py builds."""

    def __init__(self):
        self.events = []

    def __call__(self, event, payload):
        self.events.append((event, payload))

    def payload(self, event):
        for name, payload in self.events:
            if name == event:
                return payload
        return None

    def names(self):
        return [name for name, _ in self.events]


@pytest.fixture
def runtime():
    rt = AppRuntime(config=Configuration())
    rt.config.settings.draft_log_enabled = True
    rt.config.card_data.latest_dataset = "TEST_PremierDraft_All_Data.json"
    return rt


@pytest.fixture
def booted(runtime, monkeypatch):
    """Patches every collaborator _boot_blocking reaches.

    DraftOrchestrator and OrchestratorAdapter are both real threading.Thread
    subclasses whose run() loops until stopped, so they are patched as classes
    rather than started — an unpatched start() here would leak a filesystem-
    polling thread into the rest of the session.
    """
    scanner = _mock_scanner()
    emit = Recorder()

    # boot.py calls _parse_cli_args(), which reads sys.argv; under pytest that
    # holds test paths. parse_known_args tolerates them, but pin it anyway.
    monkeypatch.setattr(sys, "argv", ["mtga-draft-desktop"])

    # _boot_blocking now spawns a real daemon thread for the post-boot dataset
    # notifier — stub it so no test leaks a thread that later hits the network.
    thread_cls = MagicMock()
    monkeypatch.setattr(threading, "Thread", thread_cls)

    with patch("src.bootstrap.cleanup_old_draft_logs") as cleanup, patch(
        "src.bootstrap.load_data", return_value={"scanner": scanner}
    ) as load_data, patch(
        "src.ui.orchestrator.DraftOrchestrator"
    ) as orchestrator_cls, patch(
        "mtga_bridge.orchestrator_adapter.OrchestratorAdapter"
    ) as adapter_cls, patch(
        "mtga_bridge.snapshot.build_draft_state", return_value="STATE"
    ) as build_state:
        yield SimpleNamespace(
            runtime=runtime,
            scanner=scanner,
            emit=emit,
            cleanup=cleanup,
            load_data=load_data,
            orchestrator_cls=orchestrator_cls,
            adapter_cls=adapter_cls,
            build_state=build_state,
            thread_cls=thread_cls,
        )


# --- _boot_blocking: the happy path ------------------------------------------


def test_boot_wires_the_runtime(booted):
    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.runtime.scanner is booted.scanner
    assert booted.runtime.orchestrator is booted.orchestrator_cls.return_value
    assert booted.runtime.adapter is booted.adapter_cls.return_value
    assert booted.runtime.booted.is_set()


def test_boot_starts_both_background_threads(booted):
    boot._boot_blocking(booted.runtime, booted.emit)

    booted.orchestrator_cls.return_value.start.assert_called_once_with()
    booted.adapter_cls.return_value.start.assert_called_once_with()


def test_boot_prunes_stale_draft_logs_first(booted):
    boot._boot_blocking(booted.runtime, booted.emit)
    booted.cleanup.assert_called_once_with()


def test_boot_passes_the_config_to_load_data(booted):
    boot._boot_blocking(booted.runtime, booted.emit)

    _args, config, progress = booted.load_data.call_args[0]
    assert config is booted.runtime.config
    assert callable(progress)


def test_boot_forwards_the_cli_log_override(booted, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["app", "-f", "/tmp/Player.log", "-d", "/tmp/Data"])
    boot._boot_blocking(booted.runtime, booted.emit)

    args = booted.load_data.call_args[0][0]
    assert args.file == "/tmp/Player.log"
    assert args.data == "/tmp/Data"


def test_boot_ignores_unknown_cli_args(booted, monkeypatch):
    """_parse_cli_args uses parse_known_args, so pytest's own argv can't
    SystemExit the boot thread."""
    monkeypatch.setattr(sys, "argv", ["app", "tests/test_bridge_boot.py", "-q"])
    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.runtime.booted.is_set()


@pytest.mark.parametrize("enabled", [True, False])
def test_draft_logging_follows_the_setting(booted, enabled):
    booted.runtime.config.settings.draft_log_enabled = enabled
    boot._boot_blocking(booted.runtime, booted.emit)

    booted.scanner.log_enable.assert_called_once_with(enabled)


def test_boot_primes_the_state_cache(booted):
    """The first get_draft_state after boot://complete should be a cache hit,
    which is the whole reason build_draft_state runs here."""
    boot._boot_blocking(booted.runtime, booted.emit)

    booted.build_state.assert_called_once_with(booted.scanner, booted.runtime.config)
    assert booted.runtime.get_cached_state() == "STATE"


# --- Progress events ---------------------------------------------------------


def test_progress_emits_a_view_model_not_a_dict(booted):
    """v0.14 replaced hand-written camelCase dicts with view-models across
    every emit site — the drift that produced the v0.6 blank window. The ast
    walk in test_bridge_serialization.py checks the shape; this checks the
    payload that actually reaches Emitter.emit."""
    boot._boot_blocking(booted.runtime, booted.emit)

    progress = booted.emit.payload(boot.EVENT_PROGRESS)
    assert isinstance(progress, BootProgress)


def test_progress_records_the_last_message_for_late_subscribers(booted):
    """get_boot_status reads last_boot_message, so a webview that attaches
    after boot started still has something to render."""
    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.runtime.last_boot_message == "Preparing draft engine..."


def test_load_data_progress_is_forwarded(booted):
    booted.load_data.side_effect = lambda _a, _c, progress: (
        progress("Locating Player.log..."),
        {"scanner": booted.scanner},
    )[1]

    boot._boot_blocking(booted.runtime, booted.emit)

    messages = [
        payload.message
        for name, payload in booted.emit.events
        if name == boot.EVENT_PROGRESS
    ]
    assert "Locating Player.log..." in messages


def test_progress_precedes_complete(booted):
    boot._boot_blocking(booted.runtime, booted.emit)

    names = booted.emit.names()
    assert names.index(boot.EVENT_PROGRESS) < names.index(boot.EVENT_COMPLETE)


# --- The boot://complete payload ---------------------------------------------


def test_complete_reports_the_recovered_draft(booted):
    boot._boot_blocking(booted.runtime, booted.emit)

    complete = booted.emit.payload(boot.EVENT_COMPLETE)
    assert isinstance(complete, BootComplete)
    assert complete.found_draft is True
    assert complete.event_set == "TEST"
    assert complete.event_type == "PremierDraft"
    assert complete.pack == 2
    assert complete.pick == 7


def test_complete_reports_no_draft_when_the_scan_found_none(booted):
    booted.scanner.retrieve_current_limited_event.return_value = ("", "")

    boot._boot_blocking(booted.runtime, booted.emit)

    complete = booted.emit.payload(boot.EVENT_COMPLETE)
    assert complete.found_draft is False
    assert complete.event_set == ""
    assert complete.event_type == ""


def test_complete_tolerates_a_none_event(booted):
    """retrieve_current_limited_event returns None rather than "" on some
    paths; the `or ""` guards a pydantic validation error that would kill boot
    after the orchestrator already started."""
    booted.scanner.retrieve_current_limited_event.return_value = (None, None)

    boot._boot_blocking(booted.runtime, booted.emit)

    complete = booted.emit.payload(boot.EVENT_COMPLETE)
    assert complete.found_draft is False
    assert complete.event_set == ""


@pytest.mark.parametrize(
    "dataset, expected", [("TEST_PremierDraft_All_Data.json", True), ("", False)]
)
def test_complete_reports_whether_a_dataset_is_loaded(booted, dataset, expected):
    """The frontend routes a first-run user to the Datasets page off this
    flag, so a wrong value strands them on an empty Dashboard."""
    booted.runtime.config.card_data.latest_dataset = dataset

    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.emit.payload(boot.EVENT_COMPLETE).has_dataset is expected


# --- Non-fatal warm-up failure -----------------------------------------------


def test_a_failed_warmup_does_not_abort_boot(booted, caplog):
    """boot.py marks the state build non-fatal on purpose: a dataset that
    can't produce a snapshot should still leave a usable app, not a splash
    screen that never resolves."""
    booted.build_state.side_effect = RuntimeError("no set data")

    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.runtime.booted.is_set()
    assert booted.emit.payload(boot.EVENT_COMPLETE) is not None
    assert boot.EVENT_ERROR not in booted.emit.names()


def test_a_failed_warmup_leaves_the_cache_empty(booted):
    booted.build_state.side_effect = RuntimeError("no set data")

    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.runtime.get_cached_state() is None


# --- run_boot ----------------------------------------------------------------


def test_run_boot_executes_the_blocking_half(booted):
    anyio.run(boot.run_boot, booted.runtime, booted.emit)

    assert booted.runtime.booted.is_set()
    assert booted.runtime.boot_error is None


def test_run_boot_surfaces_a_failure(runtime):
    emit = Recorder()
    with patch.object(boot, "_boot_blocking", side_effect=RuntimeError("no log file")):
        anyio.run(boot.run_boot, runtime, emit)

    assert runtime.boot_error == "no log file"
    error = emit.payload(boot.EVENT_ERROR)
    assert isinstance(error, BootError)
    assert error.message == "no log file"


def test_run_boot_does_not_propagate(runtime):
    """A raised exception here escapes into the anyio portal task that
    __init__.py starts with start_task_soon, where nothing catches it."""
    with patch.object(boot, "_boot_blocking", side_effect=RuntimeError("boom")):
        anyio.run(boot.run_boot, runtime, Recorder())  # must not raise


def test_run_boot_survives_a_failing_emitter(runtime):
    """Both halves can fail together: if the webview is already gone, the
    error emit throws too. boot.py swallows that second failure so the task
    still exits cleanly."""

    def broken_emit(_event, _payload):
        raise RuntimeError("webview closed")

    with patch.object(boot, "_boot_blocking", side_effect=RuntimeError("boom")):
        anyio.run(boot.run_boot, runtime, broken_emit)

    assert runtime.boot_error == "boom"


# --- Post-boot dataset notifier thread ----------------------------------------


def test_boot_spawns_the_dataset_notifier_thread(booted):
    """_boot_blocking hands the post-boot dataset refresh to a daemon thread
    (the legacy Notifications.check_dataset() mirror). It must be daemon so
    boot never blocks on it and shutdown never joins it. When load_data's
    return carries no outcome key, boot defaults to the not-attempted state."""
    boot._boot_blocking(booted.runtime, booted.emit)

    booted.thread_cls.assert_called_once_with(
        target=ANY,
        args=(booted.runtime, booted.emit),
        kwargs={"boot_outcome": BOOT_NOT_ATTEMPTED},
        daemon=True,
    )
    target = booted.thread_cls.call_args.kwargs["target"]
    assert target.__name__ == "check_dataset_updates"
    assert booted.thread_cls.return_value.start.call_count == 1


def test_boot_forwards_the_boot_sync_outcome_to_the_notifier(booted):
    """load_data's return now carries a BootSyncOutcome describing what the
    boot-time sync did; boot passes it to the notifier so the toast reports
    those downloads instead of triggering a redundant re-sync."""
    booted.load_data.return_value = {
        "scanner": booted.scanner,
        "boot_sync_outcome": BootSyncOutcome(attempted=True, downloaded=4),
    }

    boot._boot_blocking(booted.runtime, booted.emit)

    assert booted.thread_cls.call_args.kwargs["kwargs"] == {
        "boot_outcome": BootSyncOutcome(attempted=True, downloaded=4)
    }
