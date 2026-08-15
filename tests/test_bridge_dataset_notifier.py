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

from src.boot_sync import BOOT_NOT_ATTEMPTED, BOOT_SKIPPED_TODAY, BootSyncOutcome
from src.configuration import Configuration
from src.dataset_updater import SyncResult

from mtga_bridge.dataset_notifier import (
    EVENT_DATASETS_SYNC_FAILED,
    EVENT_DATASETS_UPDATED,
    check_dataset_updates,
)
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import DatasetSyncFailedVM, DatasetsUpdatedVM, _VM


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


@pytest.fixture(autouse=True)
def _no_config_write(monkeypatch):
    """The fresh-sync path now stamps the once-per-day date via
    write_configuration; keep every notifier test hermetic."""
    monkeypatch.setattr("src.dataset_updater.write_configuration", MagicMock())


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
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=SyncResult(succeeded=True, downloaded=2)))

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
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=SyncResult(succeeded=True, downloaded=0)))

    check_dataset_updates(runtime, emit, boot_outcome=BOOT_NOT_ATTEMPTED)

    assert emit.events == []


def test_sleeps_before_syncing(runtime, emit, monkeypatch):
    """The delay defers the re-check ~1.5s after boot so it never races the
    boot-time sync the auto_sync_datasets setting already ran."""
    sleep = MagicMock()
    monkeypatch.setattr("mtga_bridge.dataset_notifier.time.sleep", sleep)
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=SyncResult(succeeded=True, downloaded=0))
    )

    check_dataset_updates(runtime, emit)

    sleep.assert_called_once_with(1.5)


def test_a_failed_sync_is_swallowed_but_surfaces(runtime, emit, monkeypatch):
    """A sync that raises must not escape the daemon thread — but the failure is
    now surfaced as a datasets://syncFailed event instead of dying silently."""
    _patch_sleep_and_sync(
        monkeypatch, MagicMock(side_effect=RuntimeError("network down"))
    )

    check_dataset_updates(runtime, emit)  # must not raise

    assert emit.events == [(EVENT_DATASETS_SYNC_FAILED, DatasetSyncFailedVM())]
    payload = emit.events[0][1]
    assert isinstance(payload, _VM)


def test_reports_boot_sync_count_without_re_syncing(runtime, emit, monkeypatch):
    """The boot-time auto-sync (bootstrap.load_data) already downloaded the
    datasets, so the notifier reports that count and does NOT run a redundant
    second sync — the AssertionError side_effect proves the sync is skipped."""
    sync = _patch_sleep_and_sync(
        monkeypatch,
        MagicMock(side_effect=AssertionError("must not re-sync after boot")),
    )

    check_dataset_updates(
        runtime, emit, boot_outcome=BootSyncOutcome(attempted=True, downloaded=3)
    )

    sync.assert_not_called()
    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=3))
    ]


def test_boot_synced_nothing_stays_silent(runtime, emit, monkeypatch):
    """An attempted boot sync that downloaded nothing — the notifier reports
    the count (0 → no event) and must NOT trigger a second sync. The
    AssertionError side_effect proves the fresh-sync path is skipped."""
    sync = _patch_sleep_and_sync(
        monkeypatch,
        MagicMock(side_effect=AssertionError("must not re-sync after boot")),
    )

    check_dataset_updates(
        runtime, emit, boot_outcome=BootSyncOutcome(attempted=True, downloaded=0)
    )

    sync.assert_not_called()
    assert emit.events == []


def test_falls_back_to_a_fresh_sync_when_boot_did_not(runtime, emit, monkeypatch):
    """A not-attempted outcome means boot never synced (auto-sync off), so the
    notifier runs its own silent sync to keep the notification working."""
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=SyncResult(succeeded=True, downloaded=2)))

    check_dataset_updates(runtime, emit, boot_outcome=BOOT_NOT_ATTEMPTED)

    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=2))
    ]


def test_a_falsy_default_is_rejected_not_silently_accepted(runtime, emit, monkeypatch):
    """Why the tri-state became a named type: a bare Optional[int] let a falsy
    default like 0 type-check as a valid outcome and silently mean 'boot synced
    nothing' — skipping the report and any re-sync. A BootSyncOutcome has no
    falsy stand-in: 0 carries no `.attempted`, so the mistake fails loudly
    instead of misbehaving."""
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=SyncResult(succeeded=True, downloaded=2)))

    with pytest.raises(AttributeError):
        check_dataset_updates(runtime, emit, boot_outcome=0)


def test_skipped_today_outcome_reports_nothing_and_does_not_resync(
    runtime, emit, monkeypatch
):
    """Boot skipped because today's auto-sync already ran — the notifier must
    report nothing AND NOT run the fresh silent sync a not-attempted outcome
    would trigger (that would defeat the once-per-day limit). The AssertionError
    side_effect proves the fresh-sync path is skipped."""
    sync = _patch_sleep_and_sync(
        monkeypatch,
        MagicMock(side_effect=AssertionError("must not re-sync after a skipped boot")),
    )

    check_dataset_updates(runtime, emit, boot_outcome=BOOT_SKIPPED_TODAY)

    sync.assert_not_called()
    assert emit.events == []


def test_fresh_sync_is_gated_to_once_per_day(runtime, emit, monkeypatch):
    """A not-attempted boot (auto-sync off) on a NEW UTC day → the notifier runs
    its own silent sync and stamps today's date so a later boot today skips."""
    runtime.config.card_data.last_auto_sync_date = "2026-08-12"
    monkeypatch.setattr("src.dataset_updater.utc_date_today", lambda: "2026-08-13")
    _patch_sleep_and_sync(monkeypatch, MagicMock(return_value=SyncResult(succeeded=True, downloaded=2)))

    check_dataset_updates(runtime, emit, boot_outcome=BOOT_NOT_ATTEMPTED)

    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=2))
    ]
    assert runtime.config.card_data.last_auto_sync_date == "2026-08-13"


def test_fresh_sync_skips_when_already_synced_today(runtime, emit, monkeypatch):
    """A not-attempted boot (auto-sync off) on a day that was already auto-synced
    (e.g. the notifier ran this morning and the user rebooted) → no second silent
    sync. The AssertionError side_effect proves the sync is skipped."""
    runtime.config.card_data.last_auto_sync_date = "2026-08-13"
    monkeypatch.setattr("src.dataset_updater.utc_date_today", lambda: "2026-08-13")
    sync = _patch_sleep_and_sync(
        monkeypatch,
        MagicMock(side_effect=AssertionError("must not re-sync when already synced today")),
    )

    check_dataset_updates(runtime, emit, boot_outcome=BOOT_NOT_ATTEMPTED)

    sync.assert_not_called()
    assert emit.events == []


def test_boot_sync_failure_retries_once_after_the_delay(runtime, emit, monkeypatch):
    """Boot's sync failed → the notifier treats it like not-attempted and runs
    a fresh silent sync ~1.5s later (the short retry window). If that succeeds
    it reports the downloaded count and stamps today so a later boot skips."""
    sync = _patch_sleep_and_sync(
        monkeypatch, MagicMock(return_value=SyncResult(succeeded=True, downloaded=2))
    )
    runtime.config.card_data.last_auto_sync_date = "2026-08-12"
    monkeypatch.setattr("src.dataset_updater.utc_date_today", lambda: "2026-08-13")

    check_dataset_updates(
        runtime,
        emit,
        boot_outcome=BootSyncOutcome(attempted=True, downloaded=0, failed=True),
    )

    sync.assert_called_once()
    assert emit.events == [
        (EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=2))
    ]
    assert runtime.config.card_data.last_auto_sync_date == "2026-08-13"


def test_boot_sync_failure_that_fails_again_emits_sync_failed(
    runtime, emit, monkeypatch
):
    """The retry (1.5s after boot) failing again must be observable: emit
    datasets://syncFailed and leave the date unstamped so the next launch
    retries."""
    _patch_sleep_and_sync(
        monkeypatch, MagicMock(return_value=SyncResult(succeeded=False))
    )
    runtime.config.card_data.last_auto_sync_date = "2026-08-12"

    check_dataset_updates(
        runtime,
        emit,
        boot_outcome=BootSyncOutcome(attempted=True, downloaded=0, failed=True),
    )

    assert emit.events == [(EVENT_DATASETS_SYNC_FAILED, DatasetSyncFailedVM())]
    assert runtime.config.card_data.last_auto_sync_date == "2026-08-12"
