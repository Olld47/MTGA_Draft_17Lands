"""Dataset commands: list/switch/download/delete cloud datasets and set metrics."""

import logging
from typing import Annotated, Optional

import anyio.to_thread
from pydantic import BaseModel
from pytauri import Commands
from pytauri.ipc import InvokeException, JavaScriptChannelId, WebviewWindow

from mtga_bridge import datasets as datasets_svc
from mtga_bridge import services
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import (
    Ack,
    AvailableSetsVM,
    DatasetListVM,
    DatasetSwitcherVM,
    DeleteDatasetBody,
    DownloadProgress,
    DownloadRequest,
    DownloadResult,
    SelectDatasetBody,
    SetMetricsVM,
)

logger = logging.getLogger(__name__)

commands = Commands()


@commands.command()
async def list_datasets(runtime: RuntimeState) -> DatasetListVM:
    return await anyio.to_thread.run_sync(
        datasets_svc.list_local_datasets, runtime.config
    )


@commands.command()
async def get_set_metrics(runtime: RuntimeState) -> SetMetricsVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        datasets_svc.build_set_metrics_vm, runtime.scanner
    )


@commands.command()
async def get_dataset_switcher(runtime: RuntimeState) -> DatasetSwitcherVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        datasets_svc.build_dataset_switcher_vm, runtime.scanner, runtime.config
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
