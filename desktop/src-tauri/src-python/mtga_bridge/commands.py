"""
mtga_bridge.commands
The pytauri IPC surface. Thin wrappers around the pure implementations in
services.py / snapshot.py / datasets.py — keep logic OUT of this module so it
stays testable without pytauri.
"""

import logging
from typing import Annotated, Optional

import anyio.to_thread
from pydantic import BaseModel
from pytauri import AppHandle, Commands, Manager, State
from pytauri.ipc import InvokeException, JavaScriptChannelId, WebviewWindow

from mtga_bridge import datasets as datasets_svc
from mtga_bridge import recap as recap_svc
from mtga_bridge import services
from mtga_bridge import snapshot
from mtga_bridge import tier_service
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import (
    Ack,
    AvailableSetsVM,
    BootStatusVM,
    DatasetListVM,
    DeleteDatasetBody,
    DownloadProgress,
    DownloadRequest,
    DownloadResult,
    DraftLogListVM,
    DraftRecordBody,
    DraftRecordVM,
    DraftStateVM,
    BasicLandBody,
    DeckExportVM,
    DeckStateVM,
    CompareAddBody,
    CompareRemoveBody,
    CompareStateVM,
    FilterOptionsVM,
    MoveCardBody,
    RecapVM,
    SampleHandVM,
    SealedActionVM,
    SealedDeckTechVM,
    SealedExportVM,
    SealedImportBody,
    SealedMoveBody,
    SealedRenameBody,
    SealedStateVM,
    SealedVariantBody,
    SelectDatasetBody,
    SetLogFileBody,
    SettingsPatch,
    SettingsVM,
    SimResultVM,
    TakenCardsVM,
    TierActionVM,
    TierDeleteBody,
    TierFilterBody,
    TierImportBody,
    TierListsVM,
)

logger = logging.getLogger(__name__)

commands: Commands = Commands()

RuntimeState = Annotated[AppRuntime, State()]


def _require_booted(runtime: AppRuntime):
    if not runtime.booted.is_set():
        raise InvokeException("Application is still booting")


# --- Boot / draft ------------------------------------------------------------


@commands.command()
async def get_boot_status(runtime: RuntimeState) -> BootStatusVM:
    return services.get_boot_status(runtime)


@commands.command()
async def get_draft_state(runtime: RuntimeState) -> DraftStateVM:
    _require_booted(runtime)
    cached = runtime.get_cached_state()
    if cached is not None:
        return cached
    state = await anyio.to_thread.run_sync(
        snapshot.build_draft_state, runtime.scanner, runtime.config
    )
    runtime.set_cached_state(state)
    return state


@commands.command()
async def get_taken_cards(runtime: RuntimeState) -> TakenCardsVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        snapshot.build_taken_cards, runtime.scanner, runtime.config
    )


@commands.command()
async def force_reload(runtime: RuntimeState) -> Ack:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(services.force_reload, runtime)


@commands.command()
async def set_log_file(body: SetLogFileBody, runtime: RuntimeState) -> Ack:
    _require_booted(runtime)
    return services.set_log_file(runtime, body.path)


@commands.command()
async def list_draft_logs(runtime: RuntimeState) -> DraftLogListVM:
    return services.list_draft_logs(runtime)


# --- Settings ----------------------------------------------------------------


@commands.command()
async def get_settings(runtime: RuntimeState) -> SettingsVM:
    return services.settings_vm(runtime.config)


@commands.command()
async def set_settings(body: SettingsPatch, runtime: RuntimeState) -> SettingsVM:
    return await anyio.to_thread.run_sync(
        services.apply_settings_patch, runtime, body
    )


@commands.command()
async def get_filter_options(runtime: RuntimeState) -> FilterOptionsVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(services.get_filter_options, runtime)


# --- Datasets ----------------------------------------------------------------


@commands.command()
async def list_datasets(runtime: RuntimeState) -> DatasetListVM:
    return await anyio.to_thread.run_sync(
        datasets_svc.list_local_datasets, runtime.config
    )


@commands.command()
async def list_available_sets(runtime: RuntimeState) -> AvailableSetsVM:
    _require_booted(runtime)
    return services.list_available_sets(runtime)


class DownloadBody(BaseModel):
    request: DownloadRequest
    channel: JavaScriptChannelId[DownloadProgress]


@commands.command()
async def download_dataset(
    body: DownloadBody,
    runtime: RuntimeState,
    webview_window: WebviewWindow,
) -> DownloadResult:
    _require_booted(runtime)
    channel = body.channel.channel_on(webview_window.as_ref_webview())

    def send(kind: str, value: float, text: str = ""):
        try:
            channel.send_model(DownloadProgress(kind=kind, value=value, text=text))
        except Exception as e:
            logger.debug(f"Progress channel closed: {e}")

    scanner = runtime.scanner
    set_list = getattr(scanner, "set_list", None)
    sets_data = getattr(set_list, "data", {}) or {}

    # Resolve the set key from either the display name or the 17Lands code
    set_key: Optional[str] = None
    wanted = body.request.set_code.upper()
    for name, info in sets_data.items():
        codes = [c.upper() for c in (getattr(info, "seventeenlands", []) or [])]
        if name.upper() == wanted or wanted in codes:
            set_key = name
            break
    if set_key is None:
        raise InvokeException(f"Unknown set: {body.request.set_code}")

    result = await anyio.to_thread.run_sync(
        datasets_svc.download_dataset_blocking,
        runtime.config,
        sets_data,
        set_key,
        body.request.event_type,
        body.request.user_group,
        send,
    )

    if result.ok and runtime.config.card_data.latest_dataset:
        # Load the freshly downloaded dataset and refresh views
        import os

        from src.constants import SETS_FOLDER

        path = os.path.join(SETS_FOLDER, runtime.config.card_data.latest_dataset)
        await anyio.to_thread.run_sync(
            datasets_svc.select_dataset_blocking, runtime.scanner, runtime.config, path
        )
        runtime.orchestrator.request_math_update()
        runtime.invalidate_state()

    return result


@commands.command()
async def select_dataset(body: SelectDatasetBody, runtime: RuntimeState) -> Ack:
    _require_booted(runtime)
    ok = await anyio.to_thread.run_sync(
        datasets_svc.select_dataset_blocking, runtime.scanner, runtime.config, body.path
    )
    if not ok:
        raise InvokeException(f"Dataset not found: {body.path}")
    runtime.orchestrator.request_math_update()
    runtime.invalidate_state()
    return Ack(message="Dataset loaded")


@commands.command()
async def delete_dataset(body: DeleteDatasetBody, runtime: RuntimeState) -> DatasetListVM:
    ok = await anyio.to_thread.run_sync(
        datasets_svc.delete_dataset, runtime.config, body.path
    )
    if not ok:
        raise InvokeException(f"Could not delete: {body.path}")
    return await anyio.to_thread.run_sync(
        datasets_svc.list_local_datasets, runtime.config
    )


# --- Recap -------------------------------------------------------------------


@commands.command()
async def get_recap(runtime: RuntimeState) -> RecapVM:
    _require_booted(runtime)

    def _build():
        taken, metrics, draft_id, event_type = snapshot.snapshot_recap_inputs(
            runtime.scanner
        )
        return recap_svc.build_recap(taken, metrics, draft_id, event_type)

    return await anyio.to_thread.run_sync(_build)


@commands.command()
async def get_draft_record(
    body: DraftRecordBody, runtime: RuntimeState
) -> DraftRecordVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(recap_svc.fetch_draft_record, body.draft_id)


# --- Custom deck builder -----------------------------------------------------


def _deck_state(runtime: AppRuntime) -> DeckStateVM:
    return runtime.deck_session().build_state()


@commands.command()
async def get_deck_state(runtime: RuntimeState) -> DeckStateVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(_deck_state, runtime)


@commands.command()
async def deck_refresh_pool(runtime: RuntimeState) -> DeckStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.deck_session()
        with session.scanner.lock:
            session.refresh_pool()
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def deck_move_card(body: MoveCardBody, runtime: RuntimeState) -> DeckStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.deck_session()
        session.move_card(body.card_name, body.to_sideboard)
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def deck_clear(runtime: RuntimeState) -> DeckStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.deck_session()
        session.clear_deck()
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def deck_add_basic(body: BasicLandBody, runtime: RuntimeState) -> DeckStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.deck_session()
        session.add_basic(body.color_name)
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def deck_remove_basic(body: BasicLandBody, runtime: RuntimeState) -> DeckStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.deck_session()
        session.remove_basic(body.color_name)
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def deck_simulate(runtime: RuntimeState) -> SimResultVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(lambda: runtime.deck_session().run_simulation())


@commands.command()
async def deck_auto_optimize(runtime: RuntimeState) -> SimResultVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(lambda: runtime.deck_session().auto_optimize())


@commands.command()
async def deck_auto_lands(runtime: RuntimeState) -> SimResultVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(lambda: runtime.deck_session().apply_auto_lands())


@commands.command()
async def deck_sample_hand(runtime: RuntimeState) -> SampleHandVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(lambda: runtime.deck_session().sample_hand())


@commands.command()
async def deck_export(runtime: RuntimeState) -> DeckExportVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(lambda: runtime.deck_session().export())


# --- Sealed studio -----------------------------------------------------------


@commands.command()
async def get_sealed_state(runtime: RuntimeState) -> SealedStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.sealed_session()
        with session.scanner.lock:
            session.ensure_pool()
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def sealed_reload_pool(runtime: RuntimeState) -> SealedStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.sealed_session()
        with session.scanner.lock:
            session.reload_pool()
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def sealed_auto_generate(runtime: RuntimeState) -> SealedActionVM:
    _require_booted(runtime)

    def _run():
        session = runtime.sealed_session()
        with session.scanner.lock:
            return session.auto_generate()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def sealed_select_variant(
    body: SealedVariantBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().select_variant(body.name)
    )


@commands.command()
async def sealed_create_variant(
    body: SealedVariantBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().create_variant(body.name, body.copy_from)
    )


@commands.command()
async def sealed_delete_variant(
    body: SealedVariantBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().delete_variant(body.name)
    )


@commands.command()
async def sealed_rename_variant(
    body: SealedRenameBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().rename_variant(body.old_name, body.new_name)
    )


@commands.command()
async def sealed_move_card(
    body: SealedMoveBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().move_card(
            body.card_name, body.to_sideboard, body.count
        )
    )


@commands.command()
async def sealed_clear_deck(runtime: RuntimeState) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().clear_deck()
    )


@commands.command()
async def sealed_auto_lands(runtime: RuntimeState) -> SealedActionVM:
    _require_booted(runtime)

    def _run():
        session = runtime.sealed_session()
        with session.scanner.lock:
            return session.apply_auto_lands()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def sealed_import_deck(
    body: SealedImportBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().import_deck(body.text)
    )


@commands.command()
async def sealed_export(runtime: RuntimeState) -> SealedExportVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().export()
    )


@commands.command()
async def sealed_export_sealeddeck(runtime: RuntimeState) -> SealedDeckTechVM:
    _require_booted(runtime)

    def _run():
        payload = runtime.sealed_session().export_payload()
        return services.export_to_sealeddeck_tech(payload)

    return await anyio.to_thread.run_sync(_run)


# --- Compare workspace -------------------------------------------------------


@commands.command()
async def get_compare_state(runtime: RuntimeState) -> CompareStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.compare_session()
        with session.scanner.lock:
            return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def compare_add_card(
    body: CompareAddBody, runtime: RuntimeState
) -> CompareStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.compare_session()
        with session.scanner.lock:
            session.add_card(body.name)
            return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def compare_remove_card(
    body: CompareRemoveBody, runtime: RuntimeState
) -> CompareStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.compare_session()
        with session.scanner.lock:
            session.remove_card(body.name)
            return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def compare_clear(runtime: RuntimeState) -> CompareStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.compare_session()
        with session.scanner.lock:
            session.clear()
            return session.build_state()

    return await anyio.to_thread.run_sync(_run)


# --- Tier lists --------------------------------------------------------------


@commands.command()
async def get_tier_lists(body: TierFilterBody, runtime: RuntimeState) -> TierListsVM:
    return await anyio.to_thread.run_sync(
        lambda: tier_service.list_tier_lists(body.set_code)
    )


def _refresh_tier_views(runtime: AppRuntime) -> None:
    """Tier data feeds the draft-state math, so a change must recompute it —
    mirrors the tkinter panel's on_update_callback."""
    if runtime.orchestrator is not None:
        runtime.orchestrator.request_math_update()
    runtime.invalidate_state()


@commands.command()
async def import_tier_list(
    body: TierImportBody, runtime: RuntimeState
) -> TierActionVM:
    _require_booted(runtime)
    result = await anyio.to_thread.run_sync(
        tier_service.import_tier_list, body.url, body.label
    )
    if result.ok:
        _refresh_tier_views(runtime)
    return result


@commands.command()
async def delete_tier_lists(
    body: TierDeleteBody, runtime: RuntimeState
) -> TierActionVM:
    result = await anyio.to_thread.run_sync(
        tier_service.delete_tier_lists, body.file_names
    )
    if result.ok:
        _refresh_tier_views(runtime)
    return result
