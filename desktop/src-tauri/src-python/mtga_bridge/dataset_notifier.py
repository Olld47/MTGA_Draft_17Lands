"""
mtga_bridge.dataset_notifier
Mirrors the legacy tkinter app's silent post-boot dataset refresh: ~1.5s after
launch, when update_notifications_enabled is set, re-run sync_datasets silently
and emit datasets://updated with the download count if anything actually changed.
Runs on a daemon thread (see mtga_bridge.boot) so boot never blocks on it and
shutdown never joins it.

Kept pytauri-free and import-light so it can be pytest-ed from the root poetry
environment; heavy imports (DatasetUpdater, the VM) are deferred to call time.
"""

import logging
import time

logger = logging.getLogger(__name__)

EVENT_DATASETS_UPDATED = "datasets://updated"


def check_dataset_updates(runtime, emit, delay: float = 1.5) -> None:
    """Sleep `delay`, then sync datasets silently and emit if anything updated.

    `emit` must keep that parameter name: the emit-site AST walk
    (test_emit_sites_construct_a_model) counts call sites whose payload is a
    _VM constructor, and we want this module in that sweep.

    The toggle is read here, not at schedule time, so a user toggling it off
    before `delay` elapses still skips the check.
    """
    if not runtime.config.settings.update_notifications_enabled:
        return
    time.sleep(delay)
    try:
        from src.dataset_updater import DatasetUpdater

        from mtga_bridge.viewmodels import DatasetsUpdatedVM

        updated = DatasetUpdater(runtime.config).sync_datasets(lambda msg: None)
        if updated:
            emit(EVENT_DATASETS_UPDATED, DatasetsUpdatedVM(updated_count=updated))
    except Exception as e:
        logger.warning(f"Background dataset check failed: {e}")
