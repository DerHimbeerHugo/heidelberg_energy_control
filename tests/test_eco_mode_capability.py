"""Tests for the optional Connect-series Eco-mode capability."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.amperfied_connect_modbus.const import COMMAND_ECO_MODE
from custom_components.amperfied_connect_modbus.core.capabilities.eco_mode import (
    REG_COMMAND_ECO_MODE,
    REG_STATUS_ECO_MODE,
    EcoModeCapability,
)
from custom_components.amperfied_connect_modbus.core.registers import (
    RegisterDefinition,
    RegisterType,
)


def _response(registers: list[int] | None = None, *, error: bool = False):
    result = MagicMock()
    result.isError = MagicMock(return_value=error)
    result.registers = registers or []
    return result


async def test_probe_accepts_supported_eco_mode():
    cap = EcoModeCapability()
    client = MagicMock()
    client.read_input_registers = AsyncMock(return_value=_response([1]))

    assert await cap.async_probe(client, device_id=1) is True
    client.read_input_registers.assert_awaited_once_with(
        address=REG_STATUS_ECO_MODE, count=1, device_id=1
    )


async def test_probe_rejects_missing_eco_mode():
    cap = EcoModeCapability()
    client = MagicMock()
    client.read_input_registers = AsyncMock(return_value=_response(error=True))

    assert await cap.async_probe(client, device_id=1) is False


def test_decode_eco_mode_status():
    cap = EcoModeCapability()

    assert cap.decode_polled({REG_STATUS_ECO_MODE: 1}) == {COMMAND_ECO_MODE: True}
    assert cap.decode_polled({REG_STATUS_ECO_MODE: 0}) == {COMMAND_ECO_MODE: False}


def test_eco_mode_declares_status_register():
    assert EcoModeCapability.polled_definitions == (
        RegisterDefinition(REG_STATUS_ECO_MODE, 1, RegisterType.INPUT),
    )


async def test_write_eco_mode_on_and_off():
    cap = EcoModeCapability()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_response())

    assert await cap.async_write(client, 1, COMMAND_ECO_MODE, 1) is True
    client.write_register.assert_awaited_with(
        address=REG_COMMAND_ECO_MODE, value=1, device_id=1
    )

    assert await cap.async_write(client, 1, COMMAND_ECO_MODE, 0) is True
    client.write_register.assert_awaited_with(
        address=REG_COMMAND_ECO_MODE, value=0, device_id=1
    )
