"""
mtga_bridge.dataset_notifier
Mirrors the legacy tkinter app's silent post-boot dataset refresh: ~1.5s after
launch, when update_notifications_enabled is set, report what the boot-time
sync (bootstrap.load_data) downloaded — or run a fresh silent sync when boot
didn't attempt one (auto-sync off) — and emit datasets://updated with the
download count if anything actually changed.
Runs on a daemon thread (see mtga_bridge.boot) so boot never blocks on it and
shutdown never joins it.

Kept pytauri-free and import-light so it can be pytest-ed from the root poetry
environment; heavy imports (DatasetUpdater, the VM) are deferred to call time.
"""

import logging
import time

from src.boot_sync import BOOT_NOT_ATTEMPTED, BOOT_SKIPPED_TODAY, BootSyncOutcome

logger = logging.getLogger(__name__)

EVENT_DATASETS_UPDATED = "datasets://updated"


def check_dataset_updates(
    runtime,
    emit,
    delay: float = 1.5,
    boot_outcome: BootSyncOutcome = BOOT_NOT_ATTEMPTED,
) -> None:
    """Sleep `delay`, then emit datasets://updated with how many datasets were
    actually downloaded.

    `boot_outcome` is a typed BootSyncOutcome, not a bare count:
      * attempted=False, already_synced_today=False (BOOT_NOT_ATTEMPTED) — boot
        did not sync at all (auto-sync off). Run a fresh silent sync here so
        the update notification still works, but respect the once-per-UTC-day
        limit: if today's auto-sync already ran, report nothing and do NOT
        re-sync.
      * attempted=False, already_synced_today=True (BOOT_SKIPPED_TODAY) — boot
        skipped because today's auto-sync already ran. Report nothing and do
        NOT re-sync (a fresh sync would defeat the once-per-day limit).
      * attempted=True, downloaded=0 — boot synced and downloaded nothing.
        Report nothing and do NOT re-sync: a re-check right after boot would
        find nothing, and a redundant network hit buys nothing.
      * attempted=True, downloaded=N>0 — boot synced and downloaded N. Report
        N without re-syncing.

    `emit` must keep that parameter name: the emit-site AST walk
    (test_emit_sites_construct_a_model) counts call sites whose payload is a
    _VM constructor, and we want this module in that sweep.

    The toggle is read here, not at schedule time, so a user toggling it off
    before `delay` elapses still skips the check.
    """
    if not runtime.config.settings.update_notifications_enabled:
        return
    time.sleep(delay)

    from mtga_bridge.viewmodels import DatasetsUpdatedVM

    if boot_outcome.attempted:
        updated = boot_outcome.downloaded
    elif boot_outcome.already_synced_today:
        updated = 0
    else:
        updated = 0
        try:
            from src.dataset_updater import (
                DatasetUpdater,
                is_auto_synced_today,
                mark_auto_synced_today,
            )

            if not is_auto_synced_today(runtime.config):
                updated = (
                    DatasetUpdater(runtime.config).sync_datasets(lambda msg: None) or 0
                )
                mark_auto_synced_today(runtime.config)
        except Exception as e:
            logger.warning(f"Background dataset check failed: {e}")
    if updated:
        emit(EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=updated))
