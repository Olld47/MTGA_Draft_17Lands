"""Settings commands: read, patch, and restore the persisted config."""

import anyio.to_thread
from pytauri import Commands

from mtga_bridge import services
from mtga_bridge.commands._common import RuntimeState
from mtga_bridge.viewmodels import SettingsPatch, SettingsVM

commands = Commands()


@commands.command()
async def get_settings(runtime: RuntimeState) -> SettingsVM:
    return services.settings_vm(runtime.config)


@commands.command()
async def set_settings(body: SettingsPatch, runtime: RuntimeState) -> SettingsVM:
    return await anyio.to_thread.run_sync(
        services.apply_settings_patch, runtime, body
    )


@commands.command()
async def reset_settings(runtime: RuntimeState) -> SettingsVM:
    """Restore Defaults: write the baseline config and return it (legacy
    settings.py "Restore Defaults" button)."""
    return await anyio.to_thread.run_sync(services.reset_settings, runtime)
