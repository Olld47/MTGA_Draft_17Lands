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


def test_sync_cloud_datasets_reports_zero_when_disabled(monkeypatch):
    """Auto-sync off and not an upgrade → nothing downloads → count 0.
    assert_not_called guards the gate: a removed gate would fall through to a
    network sync, which the mock's AssertionError side_effect makes explode."""
    config = Configuration()
    config.settings.auto_sync_datasets = False
    config.settings.last_run_version = constants.APPLICATION_VERSION
    sync = MagicMock(side_effect=AssertionError("must not sync when disabled"))
    monkeypatch.setattr("src.dataset_updater.DatasetUpdater.sync_datasets", sync)

    assert _sync_cloud_datasets(config, lambda msg: None) == 0
    sync.assert_not_called()
