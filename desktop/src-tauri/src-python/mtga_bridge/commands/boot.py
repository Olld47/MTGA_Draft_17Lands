"""Boot / draft-state commands: scanner state snapshots and log-file control."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import services
from mtga_bridge import snapshot
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import (
    Ack,
    BootStatusVM,
    DraftLogListVM,
    DraftStateVM,
    FilterOptionsVM,
    FrontendErrorBody,
    SetLogFileBody,
    TakenCardsVM,
)

commands = Commands()


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


@commands.command()
async def report_frontend_error(body: FrontendErrorBody) -> Ack:
    """Uncaught JS errors land in the same log as the Python side."""
    return services.report_frontend_error(body)


@commands.command()
async def get_filter_options(runtime: RuntimeState) -> FilterOptionsVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(services.get_filter_options, runtime)
