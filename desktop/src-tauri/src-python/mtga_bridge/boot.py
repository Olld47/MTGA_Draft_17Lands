"""
mtga_bridge.boot
Headless boot sequence: runs src/bootstrap.py::load_data in a worker thread,
streams progress to the webview, then starts the DraftOrchestrator and its
event adapter.
"""

import argparse
import logging
import sys
import threading

import anyio.to_thread

logger = logging.getLogger(__name__)

# Event names shared with the frontend
EVENT_PROGRESS = "boot://progress"
EVENT_COMPLETE = "boot://complete"
EVENT_ERROR = "boot://error"


def _parse_cli_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Path to Player.log")
    parser.add_argument("-d", "--data", help="Path to MTGA Data")
    args, _ = parser.parse_known_args()
    return args


def _boot_blocking(runtime, emit):
    """Runs on a worker thread. `emit(event, payload)` must be thread-safe."""
    from src.bootstrap import cleanup_old_draft_logs, load_data
    from src.boot_sync import BOOT_NOT_ATTEMPTED
    from src.ui.orchestrator import DraftOrchestrator

    from mtga_bridge.orchestrator_adapter import OrchestratorAdapter
    from mtga_bridge.snapshot import build_draft_state
    from mtga_bridge.viewmodels import BootComplete, BootProgress

    def progress(msg: str):
        runtime.last_boot_message = msg
        emit(EVENT_PROGRESS, BootProgress(message=msg))

    cleanup_old_draft_logs()

    data = load_data(_parse_cli_args(), runtime.config, progress)
    scanner = data["scanner"]
    runtime.scanner = scanner
    scanner.log_enable(runtime.config.settings.draft_log_enabled)

    # Start the background watchdog + event adapter
    orchestrator = DraftOrchestrator(scanner, runtime.config, lambda: None)
    runtime.orchestrator = orchestrator
    adapter = OrchestratorAdapter(orchestrator, runtime, emit)
    runtime.adapter = adapter
    orchestrator.start()
    adapter.start()

    # Warm the numba JIT and prime the state cache so the first
    # get_draft_state after boot://complete is instant.
    progress("Preparing draft engine...")
    try:
        runtime.bump_refresh()
        state = build_draft_state(scanner, runtime.config)
        runtime.set_cached_state(state)
    except Exception as e:
        logger.error(f"Initial state build failed (non-fatal): {e}", exc_info=True)
        state = None

    runtime.booted.set()
    event_set, event_type = scanner.retrieve_current_limited_event()
    pack, pick = scanner.retrieve_current_pack_and_pick()
    emit(
        EVENT_COMPLETE,
        BootComplete(
            found_draft=bool(event_set),
            event_set=event_set or "",
            event_type=event_type or "",
            pack=pack,
            pick=pick,
            has_dataset=bool(runtime.config.card_data.latest_dataset),
        ),
    )

    # Legacy Notifications.check_dataset() ran a silent 17Lands refresh ~1.5s
    # after launch, gated by update_notifications_enabled. Mirror it on a daemon
    # thread so boot never blocks on it and shutdown never joins it. Hand it the
    # boot-time sync outcome so the toast reports what bootstrap.load_data
    # already downloaded instead of re-syncing (which would find nothing). The
    # outcome is a typed BootSyncOutcome: attempted=True (with the download
    # count) means boot synced; BOOT_NOT_ATTEMPTED (auto-sync off) means boot
    # never attempted, so the notifier runs its own sync.
    from mtga_bridge.dataset_notifier import check_dataset_updates

    threading.Thread(
        target=check_dataset_updates,
        args=(runtime, emit),
        kwargs={"boot_outcome": data.get("boot_sync_outcome", BOOT_NOT_ATTEMPTED)},
        daemon=True,
    ).start()


async def run_boot(runtime, emit):
    """Portal task: executes the blocking boot on a thread, surfacing errors."""
    from mtga_bridge.viewmodels import BootError

    try:
        await anyio.to_thread.run_sync(_boot_blocking, runtime, emit)
    except Exception as e:
        logger.error(f"Boot failed: {e}", exc_info=True)
        runtime.boot_error = str(e)
        try:
            emit(EVENT_ERROR, BootError(message=str(e)))
        except Exception:
            pass
