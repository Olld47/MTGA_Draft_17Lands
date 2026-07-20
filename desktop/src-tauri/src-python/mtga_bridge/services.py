"""
mtga_bridge.services
Pure command implementations (no pytauri imports) so they can be unit-tested
directly. The commands package wraps these with the pytauri IPC glue.
"""

import logging
import os
from typing import Optional

from src import constants
from src.card_logic import filter_options
from src.configuration import write_configuration

from mtga_bridge.viewmodels import (
    Ack,
    AvailableSetsVM,
    AvailableSetVM,
    BootStatusVM,
    DraftLogListVM,
    DraftLogVM,
    FilterOptionsVM,
    SealedDeckTechVM,
    SettingsPatch,
    SettingsVM,
)

logger = logging.getLogger(__name__)


# --- Boot / draft ------------------------------------------------------------


def get_boot_status(runtime) -> BootStatusVM:
    return BootStatusVM(
        booted=runtime.booted.is_set(),
        last_message=runtime.last_boot_message,
        error=runtime.boot_error,
    )


def force_reload(runtime) -> Ack:
    """Port of AppController.force_reload: wipes state and demands a deep scan."""
    scanner = runtime.scanner
    with scanner.lock:
        scanner.clear_draft(True)
        if getattr(scanner, "set_data", None):
            scanner.set_data.unknown_id_cache.clear()
    runtime.orchestrator.trigger_full_scan()
    return Ack(message="Deep scan scheduled")


def set_log_file(runtime, path: str) -> Ack:
    if not path or not os.path.exists(path):
        return Ack(ok=False, message=f"File not found: {path}")
    runtime.orchestrator.set_file_and_scan(path)
    return Ack(message=os.path.basename(path))


def list_draft_logs(runtime) -> DraftLogListVM:
    logs = []
    folder = constants.DRAFT_LOG_FOLDER
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.startswith("DraftLog_") and f.endswith(".log"):
                path = os.path.join(folder, f)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    mtime = 0.0
                logs.append(DraftLogVM(path=path, file_name=f, modified=mtime))
    logs.sort(key=lambda log: log.modified, reverse=True)
    current = ""
    if runtime.scanner is not None and runtime.scanner.arena_file:
        current = os.path.basename(runtime.scanner.arena_file)
    return DraftLogListVM(logs=logs, current=current)


# --- Settings ----------------------------------------------------------------


def settings_vm(config) -> SettingsVM:
    s = config.settings
    return SettingsVM(
        deck_filter=s.deck_filter,
        filter_format=s.filter_format,
        result_format=s.result_format,
        ui_size=s.ui_size,
        card_colors_enabled=s.card_colors_enabled,
        draft_log_enabled=s.draft_log_enabled,
        update_notifications_enabled=s.update_notifications_enabled,
        missing_notifications_enabled=s.missing_notifications_enabled,
        auto_sync_datasets=s.auto_sync_datasets,
        arena_log_location=s.arena_log_location,
        database_location=s.database_location,
        column_configs=dict(s.column_configs),
    )


def apply_settings_patch(runtime, patch: SettingsPatch) -> SettingsVM:
    """Applies a partial settings update, persists, and wires side effects the
    tkinter app handled in DraftApp._open_settings._on_settings_changed."""
    config = runtime.config
    s = config.settings
    changed = patch.model_dump(exclude_none=True)

    for key, value in changed.items():
        setattr(s, key, value)
    write_configuration(config)

    scanner = runtime.scanner
    orchestrator = runtime.orchestrator

    if "draft_log_enabled" in changed and scanner is not None:
        scanner.log_enable(s.draft_log_enabled)

    if (
        "arena_log_location" in changed
        and s.arena_log_location
        and os.path.exists(s.arena_log_location)
        and orchestrator is not None
    ):
        orchestrator.set_file_and_scan(s.arena_log_location)

    if (
        "database_location" in changed
        and s.database_location
        and os.path.exists(s.database_location)
        and scanner is not None
    ):
        scanner.set_data.db_path = s.database_location
        scanner.set_data.unknown_id_cache.clear()

    # Any display-affecting change should recompute state on the next fetch
    math_keys = {
        "deck_filter",
        "filter_format",
        "result_format",
        "card_colors_enabled",
        "database_location",
    }
    if math_keys & changed.keys():
        if orchestrator is not None:
            orchestrator.request_math_update()
        runtime.invalidate_state()

    return settings_vm(config)


def get_filter_options(runtime) -> FilterOptionsVM:
    config = runtime.config
    scanner = runtime.scanner
    auto_detected = ""
    if scanner is not None:
        with scanner.lock:
            metrics = scanner.retrieve_set_metrics()
            taken = scanner.retrieve_taken_cards()
        detected = filter_options(
            taken, constants.FILTER_OPTION_AUTO, metrics, config
        )
        auto_detected = detected[0] if detected else ""
    return FilterOptionsVM(
        options=list(constants.DECK_FILTERS),
        active=config.settings.deck_filter,
        auto_detected=auto_detected,
    )


def list_available_sets(runtime) -> AvailableSetsVM:
    """Sets available for download, from the scanner's LimitedSets data."""
    sets = []
    scanner = runtime.scanner
    set_list = getattr(scanner, "set_list", None) if scanner else None
    data = getattr(set_list, "data", {}) or {}
    for name, info in data.items():
        codes = getattr(info, "seventeenlands", []) or []
        sets.append(AvailableSetVM(code=codes[0] if codes else name, name=name))
    return AvailableSetsVM(sets=sets)


def export_to_sealeddeck_tech(payload: str) -> SealedDeckTechVM:
    """Blocking POST of an MTGA deck payload to sealeddeck.tech. Returns the
    shareable URL, or the payload for clipboard fallback on failure. Call off
    the event loop. Port of SealedStudio._export_to_sealeddeck_tech."""
    if not payload.strip():
        return SealedDeckTechVM(ok=False, message="Deck is empty.")
    import requests

    try:
        response = requests.post(
            "https://sealeddeck.tech/api/pools",
            json={"pool": payload},
            timeout=10,
        )
        if response.status_code == 200:
            url = response.json().get("url")
            if url:
                return SealedDeckTechVM(ok=True, url=url, text=payload)
            raise ValueError("No URL returned from API")
        raise RuntimeError(f"HTTP {response.status_code}")
    except Exception as exc:
        logger.warning("sealeddeck.tech export failed: %s", exc)
        return SealedDeckTechVM(
            ok=False,
            text=payload,
            message=(
                "Could not reach sealeddeck.tech. The deck has been copied to your "
                "clipboard; paste it manually at sealeddeck.tech."
            ),
        )
