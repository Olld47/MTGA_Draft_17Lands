"""Shared command-layer helpers (not a feature module — skipped by the
registry reflection tests)."""

from typing import Annotated

from pytauri import State
from pytauri.ipc import InvokeException

from mtga_bridge.runtime import AppRuntime

RuntimeState = Annotated[AppRuntime, State()]


def _require_booted(runtime: AppRuntime):
    if not runtime.booted.is_set():
        raise InvokeException("Application is still booting")
