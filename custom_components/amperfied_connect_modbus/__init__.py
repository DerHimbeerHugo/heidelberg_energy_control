"""The Amperfied Connect Modbus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import HeidelbergEnergyControlCoordinator
from .core.api import HeidelbergEnergyControlAPI
from .core.exceptions import (
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
)

type HeidelbergEnergyControlConfigEntry = ConfigEntry[
    HeidelbergEnergyControlCoordinator
]


async def async_setup_entry(
    hass: HomeAssistant, entry: HeidelbergEnergyControlConfigEntry
) -> bool:
    """Set up Amperfied Connect Modbus from a config entry."""

    entry.async_on_unload(entry.add_update_listener(update_listener))

    api = HeidelbergEnergyControlAPI(
        host=entry.data["host"],
        port=entry.data["port"],
        device_id=entry.data["device_id"],
    )

    try:
        static_data = await api.async_get_static_data()
        if static_data is None:
            await api.disconnect()
            raise ConfigEntryNotReady(
                "Wallbox connected but did not respond to requests"
            )

    except HeidelbergEnergyControlConnectionError as err:
        raise ConfigEntryNotReady(f"Unable to connect to wallbox: {err}") from err
    except HeidelbergEnergyControlReadError as err:
        await api.disconnect()
        raise ConfigEntryNotReady(f"Failed to read static data: {err}") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Error communicating with wallbox: {err}") from err

    coordinator = HeidelbergEnergyControlCoordinator(
        hass=hass, api=api, static_data=static_data, entry=entry
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HeidelbergEnergyControlConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
        await entry.runtime_data.api.disconnect()
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
