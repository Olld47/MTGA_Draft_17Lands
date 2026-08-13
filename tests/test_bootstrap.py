"""
tests/test_bootstrap.py
Guards for src/bootstrap.py — specifically the boot-time dataset-sync outcome
that flows to the desktop background notifier (mtga_bridge/dataset_notifier)
so it can toast "N datasets updated" for what boot actually downloaded.
"""

import pytest
from unittest.mock import MagicMock

from src import constants
from src.boot_sync import BOOT_NOT_ATTEMPTED, BOOT_SKIPPED_TODAY
from src.bootstrap import _sync_cloud_datasets
from src.configuration import Configuration


@pytest.fixture(autouse=True)
def _no_config_writes(monkeypatch):
    """The once-per-day gate persists its UTC date via write_configuration;
    keep every test hermetic regardless of which branch it exercises."""
    monkeypatch.setattr("src.bootstrap.write_configuration", MagicMock())
    monkeypatch.setattr("src.dataset_updater.write_configuration", MagicMock())


def test_sync_cloud_datasets_returns_the_download_count(monkeypatch):
    """sync_datasets now returns a count; bootstrap must forward it so the
    desktop notifier can report what boot downloaded. A dropped return (or a
    boolean collapse) fails this assertion."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION  # not upgraded
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=3)
    )

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome.attempted is True
    assert outcome.downloaded == 3


def test_sync_cloud_datasets_returns_not_attempted_when_disabled(monkeypatch):
    """Auto-sync off and not an upgrade → boot never attempts a sync, so the
    outcome must be the not-attempted state, not a synced-0. The desktop
    notifier reads not-attempted as 'boot did not sync → run a fresh silent
    sync'; a synced-0 would be misread as 'boot synced, nothing to report' and
    skip the notification entirely.
    assert_not_called guards the gate: a removed gate would fall through to a
    network sync, which the mock's AssertionError side_effect makes explode."""
    config = Configuration()
    config.settings.auto_sync_datasets = False
    config.settings.last_run_version = constants.APPLICATION_VERSION
    sync = MagicMock(side_effect=AssertionError("must not sync when disabled"))
    monkeypatch.setattr("src.dataset_updater.DatasetUpdater.sync_datasets", sync)

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome == BOOT_NOT_ATTEMPTED
    assert outcome.attempted is False
    sync.assert_not_called()


def test_sync_cloud_datasets_returns_zero_when_sync_ran_but_nothing_changed(
    monkeypatch,
):
    """Auto-sync on and the sync ran but downloaded nothing → a synced-0
    outcome, NOT not-attempted. The notifier distinguishes the two:
    not-attempted means 'boot didn't sync → run a fresh sync', synced-0 means
    'boot synced, nothing to report → stay silent'. A careless not-attempted
    here would re-sync 1.5s after a successful no-op boot sync."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=0)
    )

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome.attempted is True
    assert outcome.downloaded == 0


def test_sync_cloud_datasets_returns_zero_when_upgrade_sync_raised(monkeypatch):
    """The one-time upgrade migration forces a sync even with auto-sync off;
    if that sync raises, the function must still return a synced-0 outcome
    (never not-attempted / never propagate) so the notifier sees 'boot synced'
    and skips the redundant 1.5s re-sync."""
    config = Configuration()
    config.settings.auto_sync_datasets = False
    config.settings.last_run_version = "0.0.0"  # != APPLICATION_VERSION → upgraded
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets",
        MagicMock(side_effect=RuntimeError("sync failed")),
    )

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome.attempted is True
    assert outcome.downloaded == 0


def test_sync_cloud_datasets_returns_zero_when_sync_ran_but_raised(monkeypatch):
    """Auto-sync on but the sync itself blew up → a synced-0 outcome, NOT
    not-attempted and NOT an uncaught exception. The notifier reads any
    attempted outcome as 'boot synced → no 1.5s re-sync'; a propagated
    exception or a not-attempted return would re-sync 1.5s after a boot that
    already attempted and failed the sync."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets",
        MagicMock(side_effect=RuntimeError("sync failed")),
    )

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome.attempted is True
    assert outcome.downloaded == 0


def test_sync_cloud_datasets_skips_when_already_synced_today(monkeypatch):
    """Boot must not re-sync when today's auto-sync already ran (once-per-UTC-day
    gate). It returns the skipped-today outcome, not a not-attempted one — the
    desktop notifier keys on the difference so a skipped boot does NOT trigger a
    fresh silent sync ~1.5s later. assert_not_called guards the gate: removing
    the skip would fall through to a network sync, which the mock's AssertionError
    side_effect makes explode."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION  # not upgraded
    config.card_data.last_auto_sync_date = "2026-08-13"
    monkeypatch.setattr("src.dataset_updater.utc_date_today", lambda: "2026-08-13")
    sync = MagicMock(side_effect=AssertionError("must not sync when already synced today"))
    monkeypatch.setattr("src.dataset_updater.DatasetUpdater.sync_datasets", sync)

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome == BOOT_SKIPPED_TODAY
    assert outcome.attempted is False
    sync.assert_not_called()


def test_sync_cloud_datasets_syncs_and_stamps_on_a_new_day(monkeypatch):
    """A new UTC day (last auto-sync was yesterday) → boot runs the sync and
    records today's date so a later boot today skips. A dropped stamp would leave
    the date at yesterday and re-sync on the next launch."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION
    config.card_data.last_auto_sync_date = "2026-08-12"
    monkeypatch.setattr("src.dataset_updater.utc_date_today", lambda: "2026-08-13")
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=2)
    )

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome.attempted is True
    assert outcome.downloaded == 2
    assert config.card_data.last_auto_sync_date == "2026-08-13"


def test_sync_cloud_datasets_upgrade_forces_sync_even_when_already_synced_today(
    monkeypatch,
):
    """The one-time upgrade migration must bypass the day-gate: a new app version
    forces a corrected-data refresh even if auto-sync already ran today (and even
    with auto-sync off). Gating the upgrade branch would skip the migration."""
    config = Configuration()
    config.settings.auto_sync_datasets = False
    config.settings.last_run_version = "0.0.0"  # != APPLICATION_VERSION → upgraded
    config.card_data.last_auto_sync_date = "2026-08-13"
    monkeypatch.setattr("src.dataset_updater.utc_date_today", lambda: "2026-08-13")
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=1)
    )

    outcome = _sync_cloud_datasets(config, lambda msg: None)

    assert outcome.attempted is True
    assert outcome.downloaded == 1
