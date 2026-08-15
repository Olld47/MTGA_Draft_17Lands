"""Practice pool commands (random / imported sealed)."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import practice as practice_svc
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import PracticeSetsVM, PracticeStartBody, SealedActionVM

commands = Commands()


@commands.command()
async def list_practice_sets(runtime: RuntimeState) -> PracticeSetsVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        practice_svc.list_practice_sets, runtime.scanner
    )


@commands.command()
async def start_practice(
    body: PracticeStartBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)

    def _run():
        return practice_svc.start_practice(
            runtime.scanner,
            runtime.config,
            runtime.sealed_session(),
            body.set_code,
            body.import_text,
        )

    result = await anyio.to_thread.run_sync(_run)
    if result.ok:
        # The practice set's dataset is now the active one for every view.
        runtime.orchestrator.request_math_update()
        runtime.invalidate_state()
    return result
