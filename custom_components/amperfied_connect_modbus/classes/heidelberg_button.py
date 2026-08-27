"""Action button entities for Amperfied Connect Modbus."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from ..const import DATA_IS_PLUGGED
from .heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergStopChargingButton(HeidelbergEntityBase, ButtonEntity):
    """Button that ends the current charging session."""

    @property
    def available(self) -> bool:
        """Only allow the action while a vehicle is connected."""
        return super().available and bool(
            self.coordinator.data.get(DATA_IS_PLUGGED, False)
        )

    async def async_press(self) -> None:
        """Stop charging; disconnect detection will re-arm the next session."""
        await self.coordinator.async_stop_charging()
