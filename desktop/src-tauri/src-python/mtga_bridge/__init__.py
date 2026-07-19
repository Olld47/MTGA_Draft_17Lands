"""
mtga_bridge
pytauri entry point for the MTGA Draft Tool. Reuses the shared draft logic in
the repo-root `src/` package; only the UI layer is new.

Keep this module import-light: submodules like snapshot/services/datasets are
unit-tested from the root poetry environment where pytauri isn't installed.
"""

import logging

logger = logging.getLogger(__name__)


def main() -> int:
    # Pin cwd/sys.path BEFORE any `src.*` import (src/constants.py derives its
    # data folders from os.getcwd()).
    from mtga_bridge.paths import ensure_cwd

    ensure_cwd()

    from anyio.from_thread import start_blocking_portal
    from pydantic import RootModel
    from pytauri import Emitter, Manager, builder_factory, context_factory

    from src.configuration import read_configuration, set_error_notifier

    from mtga_bridge import boot
    from mtga_bridge.commands import commands
    from mtga_bridge.runtime import AppRuntime

    logging.basicConfig(level=logging.INFO)

    config, _ = read_configuration()
    runtime = AppRuntime(config=config)

    DictPayload = RootModel[dict]

    with start_blocking_portal("asyncio") as portal:
        app = builder_factory().build(
            context=context_factory(),
            invoke_handler=commands.generate_handler(portal),
        )
        app_handle = app.handle()
        Manager.manage(app_handle, runtime)

        def emit(event: str, payload: dict):
            """Thread-safe event emission usable from worker threads."""
            try:
                Emitter.emit(app_handle, event, DictPayload(payload))
            except Exception:
                logger.error(f"Failed to emit {event}", exc_info=True)

        # Config errors surface as a frontend event instead of a messagebox
        set_error_notifier(
            lambda title, msg: emit("app://error", {"message": f"{title}: {msg}"})
        )

        portal.start_task_soon(boot.run_boot, runtime, emit)

        try:
            exit_code = app.run_return()
        finally:
            if runtime.adapter is not None:
                runtime.adapter.stop()
            if runtime.orchestrator is not None:
                runtime.orchestrator.stop()
        return exit_code
