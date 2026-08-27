"""Tests for restoring three phases when Eco mode is disabled."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

from custom_components.amperfied_connect_modbus.const import (
    COMMAND_ECO_MODE,
    COMMAND_PHASE_SWITCH,
    COMMAND_TARGET_CURRENT,
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
)
from custom_components.amperfied_connect_modbus.coordinator import (
    HeidelbergEnergyControlCoordinator,
)
from custom_components.amperfied_connect_modbus.core.capabilities.phase_switch import (
    PHASE_THREE,
)


def _make_coordinator(hass, mock_api, *, phase_switch: bool = True):
    entry = MagicMock()
    entry.options = {}
    mock_api.capabilities = (
        [SimpleNamespace(key="phase_switch")] if phase_switch else []
    )
    return HeidelbergEnergyControlCoordinator(
        hass=hass,
        api=mock_api,
        static_data={DATA_REG_LAYOUT_VER: "2.0.4", DATA_HW_MAX_CURR: 16},
        entry=entry,
    )


async def test_ha_eco_off_writes_manual_mode_then_three_phases(hass, mock_api):
    coord = _make_coordinator(hass, mock_api)
    coord._last_eco_mode_state = True

    await coord.async_handle_eco_mode_change(False)

    assert mock_api.async_write_command.await_args_list == [
        call(COMMAND_ECO_MODE, 0),
        call(COMMAND_PHASE_SWITCH, PHASE_THREE),
    ]
    assert coord.data[COMMAND_ECO_MODE] is False
    assert coord._last_eco_mode_state is False


async def test_ha_eco_on_does_not_change_phase_mode(hass, mock_api):
    coord = _make_coordinator(hass, mock_api)

    await coord.async_handle_eco_mode_change(True)

    mock_api.async_write_command.assert_awaited_once_with(COMMAND_ECO_MODE, 1)
    assert coord._last_eco_mode_state is True


async def test_eco_off_without_phase_capability_only_disables_eco(hass, mock_api):
    coord = _make_coordinator(hass, mock_api, phase_switch=False)

    await coord.async_handle_eco_mode_change(False)

    mock_api.async_write_command.assert_awaited_once_with(COMMAND_ECO_MODE, 0)
    assert coord._last_eco_mode_state is False


async def test_external_eco_off_transition_restores_three_phases(hass, mock_api):
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.side_effect = [
        {COMMAND_ECO_MODE: True, COMMAND_TARGET_CURRENT: 160},
        {COMMAND_ECO_MODE: False, COMMAND_TARGET_CURRENT: 160},
    ]

    await coord._async_update_data()
    mock_api.async_write_command.assert_not_awaited()

    await coord._async_update_data()
    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_PHASE_SWITCH, PHASE_THREE
    )


async def test_startup_with_eco_already_off_does_not_override_manual_phase(
    hass, mock_api
):
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {
        COMMAND_ECO_MODE: False,
        COMMAND_TARGET_CURRENT: 160,
    }

    await coord._async_update_data()

    mock_api.async_write_command.assert_not_awaited()
