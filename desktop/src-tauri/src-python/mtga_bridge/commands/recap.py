"""Recap commands: post-draft analysis and draft-record lookup."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import recap as recap_svc
from mtga_bridge import snapshot
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import DraftRecordBody, DraftRecordVM, RecapVM

commands = Commands()


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
