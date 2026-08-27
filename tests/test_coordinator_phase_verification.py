"""Tests for the bounded phase-switch verification and one-time retry."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.amperfied_connect_modbus.const import (
    COMMAND_PHASE_SWITCH,
    CONF_PHASE_SWITCH_VERIFY,
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
)
from custom_components.amperfied_connect_modbus.coordinator import (
    HeidelbergEnergyControlCoordinator,
)
from custom_components.amperfied_connect_modbus.core.capabilities.phase_switch import (
    PHASE_ONE,
    PHASE_THREE,
)


def _make_coordinator(hass, mock_api):
    entry = MagicMock()
    entry.entry_id = "wallbox-entry"
    entry.options = {CONF_PHASE_SWITCH_VERIFY: True}
    mock_api.capabilities = [SimpleNamespace(key="phase_switch")]
    return HeidelbergEnergyControlCoordinator(
        hass=hass,
        api=mock_api,
        static_data={DATA_REG_LAYOUT_VER: "2.0.4", DATA_HW_MAX_CURR: 16},
        entry=entry,
    )


async def test_phase_command_schedules_verification(hass, mock_api):
    """Every manual phase command enters the same bounded verifier."""
    coord = _make_coordinator(hass, mock_api)
    coord._schedule_phase_verification = MagicMock()

    await coord.async_set_phase(PHASE_ONE, source="test")

    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_PHASE_SWITCH, PHASE_ONE
    )
    coord._schedule_phase_verification.assert_called_once_with(PHASE_ONE, "test")


async def test_mismatch_is_retried_once_then_succeeds(hass, mock_api):
    """A wrong actual state causes exactly one additional register write."""
    coord = _make_coordinator(hass, mock_api)
    coord._async_refresh_phase_state = AsyncMock(side_effect=[PHASE_ONE, PHASE_THREE])

    with (
        patch(
            "custom_components.amperfied_connect_modbus.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.amperfied_connect_modbus.coordinator."
            "persistent_notification.async_dismiss"
        ),
    ):
        await coord._async_verify_phase_switch(PHASE_THREE, "test")

    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_PHASE_SWITCH, PHASE_THREE
    )
    assert coord._async_refresh_phase_state.await_count == 2


async def test_switching_state_gets_one_grace_check_without_retry(hass, mock_api):
    """Feedback state zero gets one short grace read before any resend."""
    coord = _make_coordinator(hass, mock_api)
    coord._async_refresh_phase_state = AsyncMock(side_effect=[0, PHASE_THREE])

    with (
        patch(
            "custom_components.amperfied_connect_modbus.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.amperfied_connect_modbus.coordinator."
            "persistent_notification.async_dismiss"
        ),
    ):
        await coord._async_verify_phase_switch(PHASE_THREE, "test")

    mock_api.async_write_command.assert_not_awaited()
    assert coord._async_refresh_phase_state.await_count == 2


async def test_failed_retry_notifies_and_never_loops(hass, mock_api):
    """A second mismatch emits one notification and performs no third write."""
    coord = _make_coordinator(hass, mock_api)
    coord._async_refresh_phase_state = AsyncMock(side_effect=[PHASE_ONE, PHASE_ONE])

    with (
        patch(
            "custom_components.amperfied_connect_modbus.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.amperfied_connect_modbus.coordinator."
            "persistent_notification.async_create"
        ) as notify,
    ):
        await coord._async_verify_phase_switch(PHASE_THREE, "test")

    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_PHASE_SWITCH, PHASE_THREE
    )
    notify.assert_called_once()
    assert coord._async_refresh_phase_state.await_count == 2


async def test_unreadable_state_does_not_send_blind_retry(hass, mock_api):
    """A read failure reports the problem without another hardware command."""
    coord = _make_coordinator(hass, mock_api)
    coord._async_refresh_phase_state = AsyncMock(return_value=None)

    with (
        patch(
            "custom_components.amperfied_connect_modbus.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.amperfied_connect_modbus.coordinator."
            "persistent_notification.async_create"
        ) as notify,
    ):
        await coord._async_verify_phase_switch(PHASE_THREE, "test")

    mock_api.async_write_command.assert_not_awaited()
    notify.assert_called_once()
