"""Select entity for Amperfied Connect Modbus."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from ..const import COMMAND_ECO_MODE, DATA_PHASE_SWITCH_STATE
from ..core.capabilities.phase_switch import PHASE_ONE, PHASE_THREE
from .heidelberg_entity_base import HeidelbergEntityBase

OPTION_ONE_PHASE = "one_phase"
OPTION_THREE_PHASES = "three_phases"

OPTION_TO_VALUE = {
    OPTION_ONE_PHASE: PHASE_ONE,
    OPTION_THREE_PHASES: PHASE_THREE,
}
VALUE_TO_OPTION = {value: option for option, value in OPTION_TO_VALUE.items()}


class HeidelbergPhaseSelect(HeidelbergEntityBase, SelectEntity):
    """Select one- or three-phase charging through register 501."""

    @property
    def available(self) -> bool:
        """Prevent manual phase commands while Eco owns phase control."""
        return super().available and not bool(
            self.coordinator.data.get(COMMAND_ECO_MODE, False)
        )

    @property
    def current_option(self) -> str | None:
        """Return the actual phase-switch state from register 5001."""
        value = self.coordinator.data.get(DATA_PHASE_SWITCH_STATE)
        return VALUE_TO_OPTION.get(value)

    async def async_select_option(self, option: str) -> None:
        """Write the requested phase count and refresh actual state."""
        value = OPTION_TO_VALUE.get(option)
        if value is None:
            raise HomeAssistantError(f"Unsupported phase option: {option}")

        await self.coordinator.async_set_phase(value, source="Home Assistant")
