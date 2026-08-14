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
    # Pin cwd/sys.path BEFORE any `src.*` import (src/constants derives its
    # data folders from the cwd in a source checkout).
    from mtga_bridge.paths import ensure_runtime_paths

    ensure_runtime_paths()

    from anyio.from_thread import start_blocking_portal
    from pydantic import BaseModel, RootModel
    from pytauri import Emitter, Manager, builder_factory, context_factory

    from src.configuration import read_configuration, set_error_notifier

    from mtga_bridge import boot
    from mtga_bridge.commands import commands
    from mtga_bridge.runtime import AppRuntime
    from mtga_bridge.viewmodels import AppError

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

        def emit(event: str, payload):
            """Thread-safe event emission usable from worker threads. Callers
            pass a _VM, whose camelCase aliases model_dump() applies because
            _VM sets serialize_by_alias=True."""
            try:
                body = payload.model_dump() if isinstance(payload, BaseModel) else payload
                Emitter.emit(app_handle, event, DictPayload(body))
            except Exception:
                logger.error(f"Failed to emit {event}", exc_info=True)

        # Config errors surface as a frontend event instead of a messagebox
        set_error_notifier(
            lambda title, msg: emit("app://error", AppError(message=f"{title}: {msg}"))
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
