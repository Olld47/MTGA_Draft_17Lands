"""mtga_bridge.commands — the pytauri IPC surface, split by feature (ticket 07).

Each feature module owns a `Commands()` instance and registers its handlers
next to the session/service it drives; this aggregator merges them into the
single `commands` object that pytauri's invoke_handler consumes. New commands
land in the matching feature module — never appended here.
"""

from pytauri import Commands

from mtga_bridge.commands import boot
from mtga_bridge.commands import compare
from mtga_bridge.commands import datasets
from mtga_bridge.commands import deck
from mtga_bridge.commands import practice
from mtga_bridge.commands import recap
from mtga_bridge.commands import sealed
from mtga_bridge.commands import settings
from mtga_bridge.commands import suggest
from mtga_bridge.commands import tier
from mtga_bridge.commands import tools

commands: Commands = Commands()
for _feature in (
    boot,
    compare,
    datasets,
    deck,
    practice,
    recap,
    sealed,
    settings,
    suggest,
    tier,
    tools,
):
    commands.data.update(_feature.commands.data)
