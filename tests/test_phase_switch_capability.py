"""Tests for the optional Connect Solar phase-switch capability."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.exceptions import ModbusException

from custom_components.amperfied_connect_modbus.const import (
    COMMAND_ECO_MODE,
    COMMAND_PHASE_SWITCH,
    DATA_PHASE_SWITCH_STATE,
)
from custom_components.amperfied_connect_modbus.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.amperfied_connect_modbus.core.capabilities.phase_switch import (
    PHASE_ONE,
    PHASE_THREE,
    REG_PHASE_SWITCH_CONTROL,
    REG_PHASE_SWITCH_STATE,
    PhaseSwitchCapability,
)
from custom_components.amperfied_connect_modbus.core.exceptions import (
    HeidelbergEnergyControlWriteError,
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


def _phase_wallbox_client() -> MagicMock:
    """Return a client for a layout-2.0.4 wallbox with a phase switch."""
    client = MagicMock()
    client.connected = False

    async def _connect() -> bool:
        client.connected = True
        return True

    input_reads = {
        (4, 1): [0x204],
        (5, 14): [3, 0, 0, 0, 300, 230, 230, 230, 1, 0, 0, 0, 0, 100],
        (100, 2): [16, 6],
        (200, 1): [3],
        (203, 1): [3],
        (REG_PHASE_SWITCH_STATE, 1): [PHASE_THREE],
        (5002, 1): [0],
        (REG_PHASE_SWITCH_STATE, 2): [PHASE_THREE, 0],
    }
    holding_reads = {
        (259, 1): [1],
        (261, 1): [160],
        (REG_PHASE_SWITCH_CONTROL, 1): [PHASE_THREE],
    }

    client.connect = AsyncMock(side_effect=_connect)
    client.close = MagicMock()
    client.read_input_registers = AsyncMock(
        side_effect=lambda address, count, device_id: _response(
            input_reads.get((address, count)),
            error=(address, count) not in input_reads,
        )
    )
    client.read_holding_registers = AsyncMock(
        side_effect=lambda address, count, device_id: _response(
            holding_reads.get((address, count)),
            error=(address, count) not in holding_reads,
        )
    )
    return client


async def test_probe_accepts_supported_phase_switch():
    cap = PhaseSwitchCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(return_value=_response([PHASE_THREE]))
    client.read_input_registers = AsyncMock(return_value=_response([PHASE_THREE]))

    assert await cap.async_probe(client, device_id=1) is True
    client.read_holding_registers.assert_awaited_once_with(
        address=REG_PHASE_SWITCH_CONTROL, count=1, device_id=1
    )
    client.read_input_registers.assert_awaited_once_with(
        address=REG_PHASE_SWITCH_STATE, count=1, device_id=1
    )


async def test_probe_rejects_missing_command_register():
    cap = PhaseSwitchCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(return_value=_response(error=True))

    assert await cap.async_probe(client, device_id=1) is False


async def test_probe_rejects_modbus_exception():
    cap = PhaseSwitchCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=ModbusException("boom"))

    assert await cap.async_probe(client, device_id=1) is False


async def test_api_loads_and_polls_phase_switch_together_with_eco_mode():
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._client = _phase_wallbox_client()

    await api.async_get_static_data()

    loaded = {cap.key for cap in api.capabilities}
    assert "phase_switch" in loaded
    assert "eco_mode" in loaded
    data = await api.async_get_data()
    assert data[DATA_PHASE_SWITCH_STATE] == PHASE_THREE
    assert data[COMMAND_ECO_MODE] is False


def test_decode_phase_switch_state():
    cap = PhaseSwitchCapability()

    assert cap.decode_polled({REG_PHASE_SWITCH_STATE: PHASE_ONE}) == {
        DATA_PHASE_SWITCH_STATE: PHASE_ONE
    }
    assert cap.decode_polled({REG_PHASE_SWITCH_STATE: 0}) == {
        DATA_PHASE_SWITCH_STATE: 0
    }


def test_phase_switch_declares_actual_state_register():
    assert PhaseSwitchCapability.polled_definitions == (
        RegisterDefinition(REG_PHASE_SWITCH_STATE, 1, RegisterType.INPUT),
    )


async def test_write_phase_switch_command():
    cap = PhaseSwitchCapability()
    client = MagicMock()
    client.write_register = AsyncMock(return_value=_response([PHASE_THREE]))

    assert await cap.async_write(client, 1, COMMAND_PHASE_SWITCH, PHASE_THREE) is True
    client.write_register.assert_awaited_once_with(
        address=REG_PHASE_SWITCH_CONTROL,
        value=PHASE_THREE,
        device_id=1,
    )


async def test_rejects_invalid_phase_switch_value():
    cap = PhaseSwitchCapability()
    client = MagicMock()

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await cap.async_write(client, 1, COMMAND_PHASE_SWITCH, 2)
