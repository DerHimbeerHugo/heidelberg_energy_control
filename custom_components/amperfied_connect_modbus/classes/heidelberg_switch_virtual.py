"""Virtual switch entity for Amperfied Connect Modbus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from ..classes.heidelberg_entity_base import HeidelbergEntityBase


class HeidelbergSwitchVirtual(HeidelbergEntityBase, SwitchEntity):
    """Generic representation of a virtual logic switch."""

    @property
    def is_on(self) -> bool:
        """Return the state from the central coordinator data store."""
        return self.coordinator.data.get(self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on request to coordinator."""
        await self.coordinator.async_handle_switch_state_change(
            self.entity_description.key, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off request to coordinator."""
        await self.coordinator.async_handle_switch_state_change(
            self.entity_description.key, False
        )
