"""
tests/test_bridge_dataset_notifier.py
Behavioural tests for mtga_bridge.dataset_notifier — the silent post-boot
dataset refresh that mirrors the legacy Notifications.check_dataset() poller.

Every test runs check_dataset_updates synchronously (time.sleep patched), so
the 1.5s delay never blocks the suite. The toggle gate is read at call time,
so the disabled case must not even construct the DatasetUpdater.
"""

import os
import sys
from unittest.mock import MagicMock, patch

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

from src.configuration import Configuration

from mtga_bridge.dataset_notifier import EVENT_DATASETS_UPDATED, check_dataset_updates
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import DatasetsUpdatedVM, _VM


class Recorder:
    """Stands in for the Emitter.emit closure __init__.py builds."""

    def __init__(self):
        self.events = []

    def __call__(self, event, payload):
        self.events.append((event, payload))


@pytest.fixture
def runtime():
    rt = AppRuntime(config=Configuration())
    rt.config.settings.update_notifications_enabled = True
    return rt


@pytest.fixture
def emit():
    return Recorder()


def _patch_sleep_and_sync(monkeypatch, sync_mock):
    monkeypatch.setattr(
        "mtga_bridge.dataset_notifier.time.sleep", MagicMock()
    )
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", sync_mock
    )
    return sync_mock


def test_toggle_off_skips_the_sync(runtime, emit, monkeypatch):
    """The gate is read at call time, so a toggle-off before the delay elapses
    skips the check entirely. assert_not_called is the guard: the AssertionError
    side_effect alone would NOT catch a removed gate, because the notifier's
    try/except swallows it before the emit — the mock's call count is the only
    signal that survives."""
    runtime.config.settings.update_notifications_enabled = False
    sync = _patch_sleep_and_sync(
        monkeypatch,
        MagicMock(side_effect=AssertionError("sync must not run when disabled")),
    )

    check_dataset_updates(runtime, emit)

    sync.assert_not_called()
    assert emit.events == []


def test_emits_the_updated_count(runtime, emit, monkeypatch):
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=2))

    check_dataset_updates(runtime, emit)

    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=2))
    ]
    payload = emit.events[0][1]
    assert isinstance(payload, _VM)
    assert payload.updated_count == 2


def test_no_update_means_no_event(runtime, emit, monkeypatch):
    """With nothing to report (boot didn't sync and the fresh sync downloads
    nothing), the notifier stays silent — an updated_count of 0 is not an
    event."""
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=0))

    check_dataset_updates(runtime, emit)

    assert emit.events == []


def test_sleeps_before_syncing(runtime, emit, monkeypatch):
    """The delay defers the re-check ~1.5s after boot so it never races the
    boot-time sync the auto_sync_datasets setting already ran."""
    sleep = MagicMock()
    monkeypatch.setattr("mtga_bridge.dataset_notifier.time.sleep", sleep)
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=0)
    )

    check_dataset_updates(runtime, emit)

    sleep.assert_called_once_with(1.5)


def test_a_failed_sync_is_swallowed(runtime, emit, monkeypatch):
    """A network failure must not escape the daemon thread — the boot sequence
    already completed, so an unhandled exception here would be silent anyway."""
    _patch_sleep_and_sync(
        monkeypatch, MagicMock(side_effect=RuntimeError("network down"))
    )

    check_dataset_updates(runtime, emit)  # must not raise

    assert emit.events == []


def test_reports_boot_sync_count_without_re_syncing(runtime, emit, monkeypatch):
    """The boot-time auto-sync (bootstrap.load_data) already downloaded the
    datasets, so the notifier reports that count and does NOT run a redundant
    second sync — the AssertionError side_effect proves the sync is skipped."""
    sync = _patch_sleep_and_sync(
        monkeypatch,
        MagicMock(side_effect=AssertionError("must not re-sync after boot")),
    )

    check_dataset_updates(runtime, emit, boot_updated=3)

    sync.assert_not_called()
    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=3))
    ]


def test_falls_back_to_a_fresh_sync_when_boot_did_not(runtime, emit, monkeypatch):
    """When boot didn't download (auto-sync off, or its sync failed → count 0),
    the notifier still runs its own silent sync so the notification works."""
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=2))

    check_dataset_updates(runtime, emit, boot_updated=0)

    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=2))
    ]
