"""Sealed studio commands, driving the SealedSession."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import services
from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import (
    BasicLandBody,
    SealedActionVM,
    SealedDeckTechVM,
    SealedExportVM,
    SealedImportBody,
    SealedMoveBody,
    SealedRenameBody,
    SealedStateVM,
    SealedVariantBody,
)

commands = Commands()


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
async def sealed_add_basic(
    body: BasicLandBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().add_basic(body.color_name)
    )


@commands.command()
async def sealed_remove_basic(
    body: BasicLandBody, runtime: RuntimeState
) -> SealedActionVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.sealed_session().remove_basic(body.color_name)
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
