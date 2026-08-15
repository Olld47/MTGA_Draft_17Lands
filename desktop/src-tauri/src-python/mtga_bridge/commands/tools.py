"""File-menu tool commands: draft export, save dialogs, URL opening, and
locating the MTGA data directory."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import services
from mtga_bridge import tools as tools_svc
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import (
    Ack,
    DraftExportBody,
    DraftExportVM,
    LocateDataBody,
    LocateDataVM,
    OpenUrlBody,
    SaveFileBody,
)

commands = Commands()


@commands.command()
async def export_draft(body: DraftExportBody, runtime: RuntimeState) -> DraftExportVM:
    """Serializes the draft history; the frontend picks the save path natively."""
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        tools_svc.export_draft, runtime.scanner, body.format
    )


@commands.command()
async def save_export_file(body: SaveFileBody) -> Ack:
    return await anyio.to_thread.run_sync(
        tools_svc.save_text_file, body.path, body.text
    )


@commands.command()
async def open_url(body: OpenUrlBody) -> Ack:
    """Opens a URL in the system browser (src.utils.open_file routes to the
    platform default app) — the context-menu 'View on Scryfall' action."""
    from src.utils import open_file

    await anyio.to_thread.run_sync(open_file, body.url)
    return Ack(message="Opened")


@commands.command()
async def locate_mtga_data(
    body: LocateDataBody, runtime: RuntimeState
) -> LocateDataVM:
    _require_booted(runtime)
    result = await anyio.to_thread.run_sync(
        tools_svc.locate_mtga_data, runtime, body.folder
    )
    if result.ok:
        # Card names now resolve against a different database.
        if runtime.orchestrator is not None:
            runtime.orchestrator.request_math_update()
        runtime.invalidate_state()
    return result
