"""Tests for stop-charging and one-shot charge-enable re-arming."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from custom_components.amperfied_connect_modbus.const import (
    COMMAND_TARGET_CURRENT,
    CONF_REARM_ON_DISCONNECT,
    DATA_HW_MAX_CURR,
    DATA_IS_PLUGGED,
    DATA_REG_LAYOUT_VER,
    VIRTUAL_ENABLE,
)
from custom_components.amperfied_connect_modbus.coordinator import (
    HeidelbergEnergyControlCoordinator,
)


def _make_coordinator(hass, mock_api, *, rearm: bool = True):
    entry = MagicMock()
    entry.entry_id = "wallbox-entry"
    entry.options = {CONF_REARM_ON_DISCONNECT: rearm}
    mock_api.capabilities = []
    return HeidelbergEnergyControlCoordinator(
        hass=hass,
        api=mock_api,
        static_data={DATA_REG_LAYOUT_VER: "2.0.4", DATA_HW_MAX_CURR: 16},
        entry=entry,
    )


async def test_disconnect_rearms_charge_enable_exactly_once(hass, mock_api):
    """Only the connected-to-disconnected edge writes the saved current."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.side_effect = [
        {COMMAND_TARGET_CURRENT: 0, DATA_IS_PLUGGED: True},
        {COMMAND_TARGET_CURRENT: 0, DATA_IS_PLUGGED: False},
        {COMMAND_TARGET_CURRENT: 160, DATA_IS_PLUGGED: False},
    ]

    await coord._async_update_data()
    await coord._async_update_data()
    await coord._async_update_data()

    mock_api.async_write_command.assert_awaited_once_with(COMMAND_TARGET_CURRENT, 160)
    assert coord.logic_enabled is True
    assert coord.data[VIRTUAL_ENABLE] is True


async def test_startup_disconnected_rearms_leftover_disabled_state(hass, mock_api):
    """A disabled register left behind across an HA restart is restored once."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0,
        DATA_IS_PLUGGED: False,
    }

    result = await coord._async_update_data()

    mock_api.async_write_command.assert_awaited_once_with(COMMAND_TARGET_CURRENT, 160)
    assert result[VIRTUAL_ENABLE] is True
    assert result[COMMAND_TARGET_CURRENT] == 160


async def test_rearm_can_be_disabled_in_options(hass, mock_api):
    """The integration option suppresses both startup and edge re-arming."""
    coord = _make_coordinator(hass, mock_api, rearm=False)
    mock_api.async_get_data.side_effect = [
        {COMMAND_TARGET_CURRENT: 0, DATA_IS_PLUGGED: True},
        {COMMAND_TARGET_CURRENT: 0, DATA_IS_PLUGGED: False},
    ]

    await coord._async_update_data()
    await coord._async_update_data()

    mock_api.async_write_command.assert_not_awaited()
    assert coord.logic_enabled is False


async def test_stop_button_then_disconnect_prepares_next_session(hass, mock_api):
    """Stop writes zero; staying connected does not rearm; unplugging does."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 160,
        DATA_IS_PLUGGED: True,
    }
    await coord._async_update_data()
    mock_api.async_write_command.reset_mock()

    await coord.async_stop_charging()
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0,
        DATA_IS_PLUGGED: True,
    }
    await coord._async_update_data()
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0,
        DATA_IS_PLUGGED: False,
    }
    await coord._async_update_data()

    assert mock_api.async_write_command.await_args_list == [
        call(COMMAND_TARGET_CURRENT, 0),
        call(COMMAND_TARGET_CURRENT, 160),
    ]


async def test_vehicle_stop_does_not_require_a_rearm_write(hass, mock_api):
    """If register 261 remained enabled, unplugging causes no redundant write."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.side_effect = [
        {COMMAND_TARGET_CURRENT: 160, DATA_IS_PLUGGED: True},
        {COMMAND_TARGET_CURRENT: 160, DATA_IS_PLUGGED: False},
    ]

    await coord._async_update_data()
    await coord._async_update_data()

    mock_api.async_write_command.assert_not_awaited()
