"""Built-in solar-management (Eco mode) capability for connect-series units.

The connect-series register layout exposes the charging-management command on
holding register 502 and its active status on input register 5002:

  - 0 = default/manual charging management
  - 1 = automatic solar management (Eco mode)

Both registers are available from register-layout version 2.0.2 onward.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import COMMAND_ECO_MODE
from ..exceptions import HeidelbergEnergyControlWriteError
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

_LOGGER = logging.getLogger(__name__)

REG_COMMAND_ECO_MODE = 502
REG_STATUS_ECO_MODE = 5002

_MANUAL_MODE = 0
_ECO_MODE = 1


class EcoModeCapability(Capability):
    """Automatic solar-management control for connect-series wallboxes."""

    key = "eco_mode"
    min_layout_version = "2.0.2"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_STATUS_ECO_MODE, 1, RegisterType.INPUT),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Confirm that the Eco-mode status register is implemented."""
        try:
            result = await client.read_input_registers(
                address=REG_STATUS_ECO_MODE, count=1, device_id=device_id
            )
        except (ModbusException, OSError):
            return False
        return bool(
            not result.isError()
            and result.registers
            and result.registers[0] in (_MANUAL_MODE, _ECO_MODE)
        )

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        return {COMMAND_ECO_MODE: registers[REG_STATUS_ECO_MODE] == _ECO_MODE}

    def supports_write(self, key: str) -> bool:
        return key == COMMAND_ECO_MODE

    async def async_write(
        self, client: Any, device_id: int, key: str, value: int
    ) -> bool:
        if key != COMMAND_ECO_MODE:
            raise HeidelbergEnergyControlWriteError(
                f"Eco mode does not own command {key!r}"
            )

        register_value = _ECO_MODE if int(value) == _ECO_MODE else _MANUAL_MODE
        try:
            result = await client.write_register(
                address=REG_COMMAND_ECO_MODE,
                value=register_value,
                device_id=device_id,
            )
            if result.isError():
                raise HeidelbergEnergyControlWriteError(
                    "Failed to write Eco-mode command (register 502)"
                )
            return True
        except (ModbusException, OSError) as err:
            _LOGGER.error("Error writing Eco mode (register 502): %s", err)
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write Eco-mode command (register 502): {err}"
            ) from err
