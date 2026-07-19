"""
mtga_bridge.runtime
Process-wide application state shared between the boot task and IPC commands.
Kept pytauri-free so the pure logic can be unit-tested.
"""

import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AppRuntime:
    """Managed via pytauri Manager.manage(); commands retrieve it by type."""

    config: Any = None
    scanner: Any = None
    orchestrator: Any = None
    adapter: Any = None
    booted: threading.Event = field(default_factory=threading.Event)
    boot_error: Optional[str] = None
    last_boot_message: str = ""

    # Draft-state cache keyed by refresh sequence
    _state_lock: threading.Lock = field(default_factory=threading.Lock)
    _refresh_seq: Any = field(default_factory=lambda: itertools.count(1))
    current_seq: int = 0
    _cached_state: Any = None
    _cached_seq: int = -1

    def bump_refresh(self) -> int:
        self.current_seq = next(self._refresh_seq)
        return self.current_seq

    def get_cached_state(self):
        with self._state_lock:
            if self._cached_seq == self.current_seq:
                return self._cached_state
        return None

    def set_cached_state(self, state):
        with self._state_lock:
            self._cached_state = state
            self._cached_seq = self.current_seq

    def invalidate_state(self):
        self.bump_refresh()
