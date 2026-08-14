"""Compare workspace commands, driving the CompareSession."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import CompareAddBody, CompareRemoveBody, CompareStateVM

commands = Commands()


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
