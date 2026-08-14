"""Suggest deck (AI archetype builder) commands, driving the SuggestSession."""

import logging

import anyio.to_thread
from pydantic import BaseModel
from pytauri import Commands
from pytauri.ipc import JavaScriptChannelId, WebviewWindow

from mtga_bridge.commands._common import RuntimeState, _require_booted
from mtga_bridge.viewmodels import (
    DeckExportVM,
    DeckStateVM,
    SampleHandVM,
    SuggestProgress,
    SuggestSelectBody,
    SuggestStateVM,
)

logger = logging.getLogger(__name__)

commands = Commands()


@commands.command()
async def get_suggest_state(runtime: RuntimeState) -> SuggestStateVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.suggest_session().build_state()
    )


class SuggestCalculateBody(BaseModel):
    channel: JavaScriptChannelId[SuggestProgress]


@commands.command()
async def suggest_calculate(
    body: SuggestCalculateBody,
    runtime: RuntimeState,
    webview_window: WebviewWindow,
) -> SuggestStateVM:
    _require_booted(runtime)
    channel = body.channel.channel_on(webview_window.as_ref_webview())

    def send(kind: str, payload: dict):
        try:
            channel.send_model(SuggestProgress(kind=kind, **payload))
        except Exception as e:
            logger.debug(f"Suggest progress channel closed: {e}")

    def _run():
        session = runtime.suggest_session()
        # calculate() takes the scanner lock only while snapshotting inputs —
        # the engine run is too long to hold it across.
        session.calculate(progress=send)
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def suggest_select_archetype(
    body: SuggestSelectBody, runtime: RuntimeState
) -> SuggestStateVM:
    _require_booted(runtime)

    def _run():
        session = runtime.suggest_session()
        session.select(body.label)
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)


@commands.command()
async def suggest_sample_hand(runtime: RuntimeState) -> SampleHandVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(
        lambda: runtime.suggest_session().sample_hand()
    )


@commands.command()
async def suggest_export(runtime: RuntimeState) -> DeckExportVM:
    _require_booted(runtime)
    return await anyio.to_thread.run_sync(lambda: runtime.suggest_session().export())


@commands.command()
async def suggest_send_to_builder(runtime: RuntimeState) -> DeckStateVM:
    """Port of the panel's 'Custom Builder' button: hand the selected
    suggestion to the custom-deck session and switch to that page."""
    _require_booted(runtime)

    def _run():
        deck, sideboard = runtime.suggest_session().deck_lists()
        session = runtime.deck_session()
        session.import_deck(deck, sideboard)
        return session.build_state()

    return await anyio.to_thread.run_sync(_run)
