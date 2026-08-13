"""
tests/test_bootstrap.py
Guards for src/bootstrap.py — specifically the boot-time dataset-sync count that
flows to the desktop background notifier (mtga_bridge/dataset_notifier) so it
can toast "N datasets updated" for what boot actually downloaded.
"""

from unittest.mock import MagicMock

from src import constants
from src.bootstrap import _sync_cloud_datasets
from src.configuration import Configuration


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

    assert _sync_cloud_datasets(config, lambda msg: None) == 3


def test_sync_cloud_datasets_returns_none_when_disabled(monkeypatch):
    """Auto-sync off and not an upgrade → boot never attempts a sync, so the
    result must be None (not 0). The desktop notifier reads None as 'boot did
    not sync → run a fresh silent sync'; a 0 would be misread as 'boot synced,
    nothing to report' and skip the notification entirely.
    assert_not_called guards the gate: a removed gate would fall through to a
    network sync, which the mock's AssertionError side_effect makes explode."""
    config = Configuration()
    config.settings.auto_sync_datasets = False
    config.settings.last_run_version = constants.APPLICATION_VERSION
    sync = MagicMock(side_effect=AssertionError("must not sync when disabled"))
    monkeypatch.setattr("src.dataset_updater.DatasetUpdater.sync_datasets", sync)

    assert _sync_cloud_datasets(config, lambda msg: None) is None
    sync.assert_not_called()


def test_sync_cloud_datasets_returns_zero_when_sync_ran_but_nothing_changed(
    monkeypatch,
):
    """Auto-sync on and the sync ran but downloaded nothing → 0, NOT None.
    The notifier distinguishes the two: None means 'boot didn't sync → run a
    fresh sync', 0 means 'boot synced, nothing to report → stay silent'. A
    careless None here would re-sync 1.5s after a successful no-op boot sync."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets", MagicMock(return_value=0)
    )

    assert _sync_cloud_datasets(config, lambda msg: None) == 0


def test_sync_cloud_datasets_returns_zero_when_upgrade_sync_raised(monkeypatch):
    """The one-time upgrade migration forces a sync even with auto-sync off;
    if that sync raises, the function must still return 0 (never None / never
    propagate) so the notifier sees 'boot synced' and skips the redundant
    1.5s re-sync."""
    config = Configuration()
    config.settings.auto_sync_datasets = False
    config.settings.last_run_version = "0.0.0"  # != APPLICATION_VERSION → upgraded
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets",
        MagicMock(side_effect=RuntimeError("sync failed")),
    )

    assert _sync_cloud_datasets(config, lambda msg: None) == 0


def test_sync_cloud_datasets_returns_zero_when_sync_ran_but_raised(monkeypatch):
    """Auto-sync on but the sync itself blew up → 0, NOT None and NOT an
    uncaught exception. The notifier reads any int as 'boot synced → no 1.5s
    re-sync'; a propagated exception or a None return would re-sync 1.5s after
    a boot that already attempted and failed the sync."""
    config = Configuration()
    config.settings.auto_sync_datasets = True
    config.settings.last_run_version = constants.APPLICATION_VERSION
    monkeypatch.setattr(
        "src.dataset_updater.DatasetUpdater.sync_datasets",
        MagicMock(side_effect=RuntimeError("sync failed")),
    )

    assert _sync_cloud_datasets(config, lambda msg: None) == 0
