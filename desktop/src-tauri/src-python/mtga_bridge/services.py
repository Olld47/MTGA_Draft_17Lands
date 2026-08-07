"""
mtga_bridge.services
Pure command implementations (no pytauri imports) so they can be unit-tested
directly. The commands package wraps these with the pytauri IPC glue.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from src import constants
from src.card_logic import (
    filter_display_name,
    filter_options,
    filter_win_rate,
    format_filter_label,
)
from src.configuration import write_configuration

from mtga_bridge.viewmodels import (
    Ack,
    AvailableSetsVM,
    AvailableSetVM,
    BootStatusVM,
    DraftLogListVM,
    DraftLogVM,
    FilterOptionVM,
    FilterOptionsVM,
    FrontendErrorBody,
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


def _live_log_label(scanner) -> str:
    """Port of top_bar.update_history_dropdown's live entry: the set's display
    name when the set list resolves it, else the raw code."""
    set_display = "Arena"
    if scanner is None:
        return f"🔴 Live: {set_display}"
    try:
        event_set, _ = scanner.retrieve_current_limited_event()
    except Exception:
        event_set = ""
    if event_set:
        set_display = event_set
        data = getattr(getattr(scanner, "set_list", None), "data", None) or {}
        for name, info in data.items():
            if getattr(info, "set_code", None) == event_set:
                set_display = name
                break
    return f"🔴 Live: {set_display}"


def _history_log_label(file_name: str, modified: float) -> str:
    """DraftLog_<set>_<event>_<draftid>.log — the name log_scanner.py:140 writes."""
    parts = file_name[: -len(".log")].split("_")
    card_set, event = (parts[1], parts[2]) if len(parts) >= 4 else ("UNKNOWN", "Draft")
    stamp = datetime.fromtimestamp(modified).strftime("%m-%d %H:%M")
    return f"📂 {card_set} {event} ({stamp})"


def list_draft_logs(runtime) -> DraftLogListVM:
    """The live Arena log plus every saved draft log, newest first. Feeds the
    masthead switcher, whose selection is handed back to set_log_file."""
    logs = []
    folder = constants.DRAFT_LOG_FOLDER
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.startswith(constants.DRAFT_LOG_PREFIX) and f.endswith(".log"):
                path = os.path.join(folder, f)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    mtime = 0.0
                logs.append(
                    DraftLogVM(
                        path=path,
                        file_name=f,
                        modified=mtime,
                        label=_history_log_label(f, mtime),
                    )
                )
    logs.sort(key=lambda log: log.modified, reverse=True)

    live_path = runtime.config.settings.arena_log_location if runtime.config else ""
    if live_path and os.path.exists(live_path):
        try:
            live_mtime = os.path.getmtime(live_path)
        except OSError:
            live_mtime = 0.0
        logs.insert(
            0,
            DraftLogVM(
                path=live_path,
                file_name=os.path.basename(live_path),
                modified=live_mtime,
                label=_live_log_label(runtime.scanner),
                is_live=True,
            ),
        )

    current = ""
    if runtime.scanner is not None and runtime.scanner.arena_file:
        current = os.path.basename(runtime.scanner.arena_file)
    return DraftLogListVM(logs=logs, current=current)


def report_frontend_error(error: FrontendErrorBody) -> Ack:
    """Mirrors an uncaught JS error into the Python log. The bundled webview has
    no devtools, so without this a render failure leaves no trace anywhere."""
    logger.error(
        "Frontend error (%s): %s\n%s",
        error.source or "unknown",
        error.message,
        error.stack,
    )
    return Ack(message="logged")


# --- Settings ----------------------------------------------------------------


def settings_vm(config) -> SettingsVM:
    s = config.settings
    return SettingsVM(
        deck_filter=s.deck_filter,
        filter_format=s.filter_format,
        result_format=s.result_format,
        ui_size=s.ui_size,
        desktop_theme=s.desktop_theme,
        card_colors_enabled=s.card_colors_enabled,
        draft_log_enabled=s.draft_log_enabled,
        update_notifications_enabled=s.update_notifications_enabled,
        missing_notifications_enabled=s.missing_notifications_enabled,
        auto_sync_datasets=s.auto_sync_datasets,
        arena_log_location=s.arena_log_location,
        database_location=s.database_location,
        column_configs=dict(s.column_configs),
        deck_mid_distribution=list(
            (config.card_logic.deck_mid.distribution if config.card_logic else []) or []
        ),
        overlay_geometry=s.overlay_geometry,
    )


def apply_settings_patch(runtime, patch: SettingsPatch) -> SettingsVM:
    """Applies a partial settings update, persists, and wires side effects the
    tkinter app handled in DraftApp._open_settings._on_settings_changed."""
    config = runtime.config
    s = config.settings
    # by_alias=False — these keys are setattr'd onto the snake_case Settings
    # model, whereas _VM defaults to serializing with its camelCase aliases.
    changed = patch.model_dump(exclude_none=True, by_alias=False)

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


def reset_settings(runtime) -> SettingsVM:
    """Restores the baseline config — the legacy settings window's "Restore
    Defaults" (settings.py:245) wrote a fresh Configuration via
    reset_configuration(), re-read it, and refreshed the UI."""
    from src.configuration import read_configuration, reset_configuration

    reset_configuration()
    fresh_config, _ = read_configuration()
    runtime.config = fresh_config
    return settings_vm(fresh_config)


def get_filter_options(runtime) -> FilterOptionsVM:
    config = runtime.config
    scanner = runtime.scanner
    filter_format = config.settings.filter_format
    auto_detected = ""
    color_ratings = {}
    if scanner is not None:
        with scanner.lock:
            metrics = scanner.retrieve_set_metrics()
            taken = scanner.retrieve_taken_cards()
            color_ratings = scanner.set_data.get_color_ratings()
        detected = filter_options(
            taken, constants.FILTER_OPTION_AUTO, metrics, config
        )
        auto_detected = detected[0] if detected else ""
    return FilterOptionsVM(
        options=[
            FilterOptionVM(
                key=key,
                label=filter_display_name(key, filter_format),
                win_rate=filter_win_rate(key, color_ratings),
            )
            for key in constants.DECK_FILTERS
        ],
        active=config.settings.deck_filter,
        auto_detected=auto_detected,
        auto_detected_label=(
            format_filter_label(auto_detected, filter_format, color_ratings)
            if auto_detected
            else ""
        ),
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
