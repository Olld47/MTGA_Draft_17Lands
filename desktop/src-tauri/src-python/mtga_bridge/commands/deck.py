"""Custom deck builder commands, driving the DeckSession."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import (
    BasicLandBody,
    DeckExportVM,
    DeckStateVM,
    MoveCardBody,
    SampleHandVM,
    SimResultVM,
)

commands = Commands()


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
