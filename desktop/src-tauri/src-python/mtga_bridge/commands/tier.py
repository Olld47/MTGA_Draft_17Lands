"""Tier list commands: fetch, import, and delete user tier lists."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import tier_service
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.runtime import AppRuntime
from mtga_bridge.viewmodels import (
    TierActionVM,
    TierDeleteBody,
    TierFilterBody,
    TierImportBody,
    TierListsVM,
)

commands = Commands()


def _refresh_tier_views(runtime: AppRuntime) -> None:
    """Tier data feeds the draft-state math, so a change must recompute it —
    mirrors the settings page's update flow."""
    if runtime.orchestrator is not None:
        runtime.orchestrator.request_math_update()
    runtime.invalidate_state()


@commands.command()
async def get_tier_lists(body: TierFilterBody, runtime: RuntimeState) -> TierListsVM:
    return await anyio.to_thread.run_sync(
        lambda: tier_service.list_tier_lists(body.set_code)
    )


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
