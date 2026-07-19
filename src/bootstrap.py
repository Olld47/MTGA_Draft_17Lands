"""
src/bootstrap.py
Headless application bootstrap shared by every UI entry point (tkinter, pytauri).
Contains the robust log/database discovery and dataset sync logic that used to
live in main.py, with progress reported through a plain callback.
"""

import logging
import os
import time

from src import constants
from src.configuration import write_configuration
from src.limited_sets import LimitedSets
from src.log_scanner import ArenaScanner
from src.file_extractor import search_arena_log_locations, retrieve_arena_directory

logger = logging.getLogger(__name__)


def cleanup_old_draft_logs(max_age_seconds: int = 2592000):
    """Removes DraftLog_*.log files older than max_age_seconds (default 30 days)."""
    if not os.path.exists(constants.DRAFT_LOG_FOLDER):
        return
    try:
        now = time.time()
        for f in os.listdir(constants.DRAFT_LOG_FOLDER):
            if f.startswith("DraftLog_") and f.endswith(".log"):
                filepath = os.path.join(constants.DRAFT_LOG_FOLDER, f)
                try:
                    if now - os.path.getmtime(filepath) > max_age_seconds:
                        os.remove(filepath)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Failed cleaning old draft logs: {e}")


def load_data(args, config, progress_callback):
    """Background Task: Robustly locate logs and index current dataset."""

    # Setup a temporary log handler to pipe backend processes to the splash screen
    class SplashLogHandler(logging.Handler):
        def emit(self, record):
            msg = record.getMessage()
            # Clean up long log lines so they fit nicely on the splash screen
            if len(msg) > 75:
                msg = msg[:72] + "..."
            progress_callback(msg)

    splash_handler = SplashLogHandler()
    splash_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(splash_handler)

    try:
        # 1. ROBUST LOG SEARCH
        # We prioritize: 1. Manual Flag (-f), 2. System Default (Real Path), 3. Config Fallback
        progress_callback("Locating Arena Logs...")
        log_path = search_arena_log_locations(
            args.file,  # Manual override
            config.settings.arena_log_location,  # Stored fallback
        )

        if log_path:
            logger.info(f"Using log file: {log_path}")
            config.settings.arena_log_location = log_path
            # Persist the valid path immediately
            write_configuration(config)

        # 2. GAME FILE INDEXING
        progress_callback("Checking Game Files...")

        # Keep user's manually set location if it exists and is valid
        db_loc = config.settings.database_location
        if db_loc and os.path.exists(os.path.join(db_loc, "Downloads", "Raw")):
            pass
        else:
            db_loc = args.data or (
                retrieve_arena_directory(log_path) if log_path else None
            )
            if db_loc:
                config.settings.database_location = db_loc
                write_configuration(config)

        # 3. SYNC OFFICIAL DATASETS
        upgraded = config.settings.last_run_version != constants.APPLICATION_VERSION
        if upgraded:
            # One-time migration after an update. v4.18 corrects 17Lands stats
            # that were previously limited to a single day of data, so force a
            # refresh even if auto-sync is off and clear the now-orphaned raw
            # cache (keyed by the retired start_date/end_date scheme).
            progress_callback("Applying corrected 17Lands data (one-time update)...")
            try:
                from src.utils import purge_raw_cache

                purge_raw_cache()
            except Exception as purge_e:
                logger.debug(f"Raw cache purge skipped (non-fatal): {purge_e}")

            from src.dataset_updater import DatasetUpdater

            DatasetUpdater(config).sync_datasets(progress_callback)

            config.settings.last_run_version = constants.APPLICATION_VERSION
            write_configuration(config)
        elif config.settings.auto_sync_datasets:
            from src.dataset_updater import DatasetUpdater

            updater = DatasetUpdater(config)
            updater.sync_datasets(progress_callback)
        else:
            progress_callback("Cloud sync disabled by user...")

        # 4. METADATA REFRESH
        progress_callback("Checking 17Lands for New Sets...")
        limited_sets = LimitedSets().retrieve_limited_sets()

        # 5. SCANNER INITIALIZATION
        progress_callback("Initializing Scanner...")
        scanner = ArenaScanner(
            filename=log_path,
            set_list=limited_sets,
            retrieve_unknown=True,
            db_path=config.settings.database_location,
        )

        # 6. DRAFT DISCOVERY (Deep Scan)
        # We scan the logs while the splash is active to prevent the main UI from hanging.
        progress_callback("Searching for active draft...")
        if scanner.draft_start_search():
            # Identify the event
            e_set, e_type = scanner.retrieve_current_limited_event()
            progress_callback(f"Found {e_set} {e_type}...")

            # Auto-load the correct dataset for this draft
            sources = scanner.retrieve_data_sources()
            for label, path in sources.items():
                if f"[{e_set.upper()}]" in label.upper():
                    scanner.retrieve_set_data(path)
                    config.card_data.latest_dataset = os.path.basename(path)
                    break

            # Deep-scan for the current pack/pick state
            scanner.draft_data_search()
            pk, pi = scanner.retrieve_current_pack_and_pick()
            if pk > 0:
                progress_callback(f"Loading {e_set} - Pack {pk} Pick {pi}...")
        else:
            # Fallback 1: Check if we successfully recovered a draft state from a previous session
            e_set, e_type = scanner.retrieve_current_limited_event()
            if e_set:
                progress_callback(f"Recovered Session: {e_set} {e_type}...")
                sources = scanner.retrieve_data_sources()
                for label, path in sources.items():
                    if f"[{e_set.upper()}]" in label.upper():
                        scanner.retrieve_set_data(path)
                        config.card_data.latest_dataset = os.path.basename(path)
                        break

                # Deep-scan to catch up on any missed picks while the application was closed/restarting
                scanner.draft_data_search()
                pk, pi = scanner.retrieve_current_pack_and_pick()
                if pk > 0:
                    progress_callback(f"Loading {e_set} - Pack {pk} Pick {pi}...")
            else:
                # Fallback 2: Look for the most recent log in Logs/ and load it automatically
                progress_callback("Checking for past drafts...")
                past_logs = []
                if os.path.exists(constants.DRAFT_LOG_FOLDER):
                    for f in os.listdir(constants.DRAFT_LOG_FOLDER):
                        if f.startswith("DraftLog_") and f.endswith(".log"):
                            past_logs.append(
                                os.path.join(constants.DRAFT_LOG_FOLDER, f)
                            )

                if past_logs:
                    past_logs.sort(key=os.path.getmtime, reverse=True)
                    most_recent_log = past_logs[0]
                    progress_callback("Loading most recent draft...")

                    scanner.set_arena_file(most_recent_log)
                    if scanner.draft_start_search():
                        e_set, e_type = scanner.retrieve_current_limited_event()
                        sources = scanner.retrieve_data_sources()
                        for label, path in sources.items():
                            if f"[{e_set.upper()}]" in label.upper():
                                scanner.retrieve_set_data(path)
                                config.card_data.latest_dataset = os.path.basename(path)
                                break
                        scanner.draft_data_search()
                else:
                    # Absolute fallback: load the most recently used dataset
                    last_dataset = config.card_data.latest_dataset
                    if last_dataset:
                        progress_callback(f"Indexing {last_dataset.split('_')[0]}...")
                        sources = scanner.retrieve_data_sources()
                        for label, path in sources.items():
                            if os.path.basename(path) == last_dataset:
                                scanner.retrieve_set_data(path)
                                break

        return {"scanner": scanner, "config": config}
    finally:
        logging.getLogger().removeHandler(splash_handler)
