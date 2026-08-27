"""Configured duration of the wallbox's internal phase switch."""

from __future__ import annotations

from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import DATA_PHASE_SWITCH_DURATION
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

REG_PHASE_SWITCH_DURATION = 503
MIN_PHASE_SWITCH_DURATION = 15
MAX_PHASE_SWITCH_DURATION = 900


class PhaseSwitchDurationCapability(Capability):
    """Read the configured phase-switch duration when register 503 exists."""

    key = "phase_switch_duration"
    min_layout_version = "2.0.2"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_PHASE_SWITCH_DURATION, 1, RegisterType.HOLDING),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Confirm that the optional duration register is readable and valid."""
        try:
            result = await client.read_holding_registers(
                address=REG_PHASE_SWITCH_DURATION, count=1, device_id=device_id
            )
        except (ModbusException, OSError):
            return False

        return bool(
            not result.isError()
            and result.registers
            and MIN_PHASE_SWITCH_DURATION
            <= result.registers[0]
            <= MAX_PHASE_SWITCH_DURATION
        )

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        """Return the configured switch duration in seconds."""
        return {DATA_PHASE_SWITCH_DURATION: registers[REG_PHASE_SWITCH_DURATION]}
