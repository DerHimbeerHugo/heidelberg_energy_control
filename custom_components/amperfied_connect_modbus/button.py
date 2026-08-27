"""Button platform for Amperfied Connect Modbus."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_button import HeidelbergStopChargingButton
from .const import BUTTON_STOP_CHARGING


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up action buttons when register 261 control is supported."""
    coordinator = entry.runtime_data
    if not coordinator.supports_virtual_logic:
        return

    async_add_entities(
        [
            HeidelbergStopChargingButton(
                coordinator,
                entry,
                ButtonEntityDescription(
                    key=BUTTON_STOP_CHARGING,
                    translation_key=BUTTON_STOP_CHARGING,
                    icon="mdi:stop-circle-outline",
                ),
            )
        ]
    )
