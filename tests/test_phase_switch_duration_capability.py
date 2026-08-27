"""Tests for the optional register-503 phase-switch duration capability."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.amperfied_connect_modbus.const import (
    DATA_PHASE_SWITCH_DURATION,
)
from custom_components.amperfied_connect_modbus.core.capabilities.phase_switch_duration import (
    REG_PHASE_SWITCH_DURATION,
    PhaseSwitchDurationCapability,
)


def _response(value: int | None):
    response = MagicMock()
    response.isError.return_value = value is None
    response.registers = [] if value is None else [value]
    return response


async def test_duration_probe_accepts_documented_range():
    cap = PhaseSwitchDurationCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(return_value=_response(90))

    assert await cap.async_probe(client, device_id=1) is True
    client.read_holding_registers.assert_awaited_once_with(
        address=REG_PHASE_SWITCH_DURATION,
        count=1,
        device_id=1,
    )


async def test_duration_probe_rejects_missing_or_invalid_values():
    cap = PhaseSwitchDurationCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(return_value=_response(0))

    assert await cap.async_probe(client, device_id=1) is False


def test_duration_decode_exposes_seconds():
    cap = PhaseSwitchDurationCapability()

    assert cap.decode_polled({REG_PHASE_SWITCH_DURATION: 120}) == {
        DATA_PHASE_SWITCH_DURATION: 120
    }
