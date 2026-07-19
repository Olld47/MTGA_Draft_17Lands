"""
mtga_bridge.orchestrator_adapter
Drains DraftOrchestrator.update_queue (the same thread-safe protocol the
tkinter AppController polls with .after) and forwards each message to the
webview as a Tauri event. Replaces the 100ms tkinter poll loop with a
blocking-get daemon thread.
"""

import logging
import os
import queue
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Event names shared with the frontend
EVENT_STATUS = "draft://status"
EVENT_REFRESH = "draft://refresh"
EVENT_HEARTBEAT = "draft://heartbeat"

HEARTBEAT_INTERVAL = 2.0


class OrchestratorAdapter(threading.Thread):
    """emit(event_name, payload_dict) is any thread-safe callable — in
    production an Emitter.emit bound to the AppHandle, in tests a recorder."""

    def __init__(self, orchestrator, runtime, emit: Callable[[str, dict], None]):
        super().__init__(daemon=True, name="OrchestratorAdapter")
        self.orchestrator = orchestrator
        self.runtime = runtime
        self.emit = emit
        self._stop_event = threading.Event()
        self._last_heartbeat = 0.0

    def stop(self):
        self._stop_event.set()

    def _emit_safe(self, event: str, payload: dict):
        try:
            self.emit(event, payload)
        except Exception as e:
            logger.error(f"Event emit failed ({event}): {e}")

    def _maybe_heartbeat(self):
        now = time.monotonic()
        if now - self._last_heartbeat < HEARTBEAT_INTERVAL:
            return
        self._last_heartbeat = now
        try:
            arena_file = self.orchestrator.scanner.arena_file
            mtime = os.stat(arena_file).st_mtime
            self._emit_safe(
                EVENT_HEARTBEAT,
                {"logMtime": mtime, "logName": os.path.basename(arena_file)},
            )
        except Exception:
            pass

    def run(self):
        logger.info("Orchestrator adapter started.")
        while not self._stop_event.is_set():
            try:
                msg = self.orchestrator.update_queue.get(timeout=0.5)
            except queue.Empty:
                self._maybe_heartbeat()
                continue

            if isinstance(msg, dict) and "status" in msg:
                self.runtime.last_boot_message = msg["status"]
                self._emit_safe(EVENT_STATUS, {"text": msg["status"]})
            elif msg == "REFRESH":
                seq = self.runtime.bump_refresh()
                self._emit_safe(EVENT_REFRESH, {"seq": seq})

            self._maybe_heartbeat()
        logger.info("Orchestrator adapter stopped.")
