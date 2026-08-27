"""Internal phase-switch capability for Amperfied Connect Solar wallboxes.

Register 501 selects one- or three-phase charging. Register 5001 reports
the actual state of the internal phase switch and returns 0 while a switch
is in progress.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import COMMAND_PHASE_SWITCH, DATA_PHASE_SWITCH_STATE
from ..exceptions import HeidelbergEnergyControlWriteError
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

_LOGGER = logging.getLogger(__name__)

REG_PHASE_SWITCH_CONTROL = 501
REG_PHASE_SWITCH_STATE = 5001

PHASE_ONE = 1
PHASE_THREE = 3
VALID_PHASE_COMMANDS = (PHASE_ONE, PHASE_THREE)
VALID_PHASE_STATES = (0, PHASE_ONE, PHASE_THREE)


class PhaseSwitchCapability(Capability):
    """Manual control and state feedback for the internal phase switch."""

    key = "phase_switch"
    min_layout_version = "2.0.1"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_PHASE_SWITCH_STATE, 1, RegisterType.INPUT),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Confirm that command and feedback registers are implemented.

        Layout 2.0.1 alone is not sufficient because Connect Home and
        Connect Business do not contain the internal phase-switch hardware.
        """
        try:
            command = await client.read_holding_registers(
                address=REG_PHASE_SWITCH_CONTROL, count=1, device_id=device_id
            )
            if (
                command.isError()
                or not command.registers
                or command.registers[0] not in VALID_PHASE_COMMANDS
            ):
                return False

            state = await client.read_input_registers(
                address=REG_PHASE_SWITCH_STATE, count=1, device_id=device_id
            )
            return bool(
                not state.isError()
                and state.registers
                and state.registers[0] in VALID_PHASE_STATES
            )
        except (ModbusException, OSError):
            return False

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        return {DATA_PHASE_SWITCH_STATE: registers[REG_PHASE_SWITCH_STATE]}

    def supports_write(self, key: str) -> bool:
        return key == COMMAND_PHASE_SWITCH

    async def async_write(
        self, client: Any, device_id: int, key: str, value: int
    ) -> bool:
        if key != COMMAND_PHASE_SWITCH or value not in VALID_PHASE_COMMANDS:
            raise HeidelbergEnergyControlWriteError(
                f"Invalid phase-switch command: {value!r}"
            )

        try:
            result = await client.write_register(
                address=REG_PHASE_SWITCH_CONTROL,
                value=int(value),
                device_id=device_id,
            )
            if result.isError():
                raise HeidelbergEnergyControlWriteError(
                    "Failed to write phase-switch control (register 501)"
                )
            return True
        except (ModbusException, OSError) as err:
            _LOGGER.error("Error writing phase-switch control: %s", err)
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write phase-switch control (register 501): {err}"
            ) from err
