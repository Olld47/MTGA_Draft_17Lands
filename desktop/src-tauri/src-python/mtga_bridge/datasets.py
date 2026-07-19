"""
mtga_bridge.datasets
Headless dataset management: listing, selecting, deleting, and downloading
17Lands datasets. Reuses FileExtractor via duck-typed UIProgress shims so the
existing download pipeline runs unchanged without tkinter.
"""

import logging
import os
import threading
from datetime import date
from typing import Callable, Optional

from src import constants
from src.configuration import write_configuration
from src.file_extractor import FileExtractor
from src.utils import read_local_manifest, retrieve_local_set_list

from mtga_bridge.viewmodels import (
    DatasetInfoVM,
    DatasetListVM,
    DownloadResult,
)

logger = logging.getLogger(__name__)


# --- Duck-typed shims that stand in for the tkinter widgets UIProgress drives ---


class ChannelStatus:
    """Duck-types tkinter.StringVar for UIProgress.status."""

    def __init__(self, send: Callable[[str, float, str], None]):
        self._send = send
        self._value = ""

    def set(self, message: str):
        self._value = message
        self._send("status", 0.0, message)

    def get(self) -> str:
        return self._value


class ChannelProgress:
    """Duck-types the ttk.Progressbar dict interface for UIProgress.progress."""

    def __init__(self, send: Callable[[str, float, str], None]):
        self._send = send
        self._value = 0.0

    def winfo_exists(self) -> bool:
        return True

    def __setitem__(self, key, value):
        if key == "value":
            self._value = float(value)
            self._send("percent", self._value, "")

    def __getitem__(self, key):
        return self._value


class ImmediateUI:
    """Duck-types the widget UIProgress uses for thread marshaling: off-main-thread
    updates are queued via ui.after(0, cb) — here we just run them inline since
    our sinks are already thread-safe."""

    def winfo_exists(self) -> bool:
        return True

    def after(self, _delay, callback):
        callback()

    def update_idletasks(self):
        pass


# --- Listing -----------------------------------------------------------------


def list_local_datasets(config) -> DatasetListVM:
    file_list, _ = retrieve_local_set_list()
    active = config.card_data.latest_dataset or None
    datasets = []
    for row in file_list or []:
        set_code, event_type, user_group, path = row[0], row[1], row[2], row[6]
        file_name = os.path.basename(path)
        try:
            stat = os.stat(path)
            size, mtime = stat.st_size, stat.st_mtime
        except OSError:
            size, mtime = 0, 0.0
        datasets.append(
            DatasetInfoVM(
                label=f"[{set_code}] {event_type} ({user_group})",
                path=path,
                file_name=file_name,
                size_bytes=size,
                modified=mtime,
                is_active=file_name == active,
            )
        )
    return DatasetListVM(datasets=datasets, active_dataset=active)


def _resolve_start_date(sets_data, set_key: str) -> str:
    """Port of DownloadWindow._resolve_start_date (src/ui/windows/download.py:341)."""
    s_info = sets_data.get(set_key)
    if s_info and s_info.start_date != constants.START_DATE_DEFAULT:
        return s_info.start_date

    codes = {c.upper() for c in (s_info.seventeenlands if s_info else [])}
    manifest_dates = [
        entry["start_date"]
        for key, entry in read_local_manifest().get("datasets", {}).items()
        if key.split("_")[0].upper() in codes and entry.get("start_date")
    ]
    if manifest_dates:
        return min(manifest_dates)
    return constants.START_DATE_DEFAULT


_download_lock = threading.Lock()


def download_dataset_blocking(
    config,
    sets_data,
    set_key: str,
    event_type: str,
    user_group: str,
    send: Callable[[str, float, str], None],
    threshold: int = 500,
) -> DownloadResult:
    """Runs the FileExtractor download recipe headlessly. `send(kind, value, text)`
    receives progress; must be thread-safe. Port of _run_download_process
    (src/ui/windows/download.py:474)."""
    if set_key not in sets_data:
        return DownloadResult(ok=False, message=f"Unknown set: {set_key}")

    if not _download_lock.acquire(blocking=False):
        return DownloadResult(ok=False, message="A download is already in progress")

    try:
        status = ChannelStatus(send)
        progress = ChannelProgress(send)

        extractor = FileExtractor(
            config.settings.database_location,
            progress,
            status,
            ImmediateUI(),
            threshold=threshold,
        )
        extractor.clear_data()
        extractor.select_sets(sets_data[set_key])
        extractor.set_draft_type(event_type)
        extractor.set_start_date(_resolve_start_date(sets_data, set_key))
        extractor.set_end_date(str(date.today()))
        extractor.set_time_period(constants.TIME_PERIOD_DEFAULT)
        extractor.set_user_group(user_group or "All")
        extractor.set_version(3.0)

        success, _ = extractor.retrieve_17lands_color_ratings()
        if not success:
            return DownloadResult(ok=False, message="17Lands Connection Failed")

        success, msg, _ = extractor.download_card_data(0)
        if not success:
            return DownloadResult(ok=False, message=msg)

        config.card_data.latest_dataset = extractor.export_card_data()
        write_configuration(config)
        return DownloadResult(ok=True, message=msg)
    except Exception as e:
        logger.error(f"Dataset download failed: {e}", exc_info=True)
        return DownloadResult(ok=False, message=str(e))
    finally:
        _download_lock.release()


def select_dataset_blocking(scanner, config, path: str) -> bool:
    """Port of AppController.on_dataset_update: loads a dataset and clears caches."""
    if not os.path.exists(path):
        return False
    with scanner.lock:
        scanner.retrieve_set_data(path)
    from src.card_logic import clear_deck_cache

    clear_deck_cache()
    config.card_data.latest_dataset = os.path.basename(path)
    write_configuration(config)
    return True


def delete_dataset(config, path: str) -> bool:
    """Deletes a dataset file after validating it lives inside SETS_FOLDER."""
    sets_folder = os.path.abspath(constants.SETS_FOLDER)
    target = os.path.abspath(path)
    if not target.startswith(sets_folder + os.sep):
        logger.error(f"Refusing to delete outside Sets folder: {path}")
        return False
    if not os.path.exists(target):
        return False
    os.remove(target)
    if config.card_data.latest_dataset == os.path.basename(target):
        config.card_data.latest_dataset = ""
        write_configuration(config)
    # Invalidate the cached set list so the next listing reflects the removal
    from src.utils import invalidate_local_set_cache

    invalidate_local_set_cache()
    return True
