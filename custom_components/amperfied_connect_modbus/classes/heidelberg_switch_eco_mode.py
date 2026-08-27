"""Eco-mode switch entity for Amperfied Connect Modbus."""

from __future__ import annotations

from typing import Any

from .heidelberg_switch import HeidelbergSwitch


class HeidelbergEcoModeSwitch(HeidelbergSwitch):
    """Eco switch that restores three phases when Eco is disabled."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable automatic solar-management mode."""
        await self.coordinator.async_handle_eco_mode_change(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Eco mode and restore three-phase manual charging."""
        await self.coordinator.async_handle_eco_mode_change(False)
