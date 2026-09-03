"""Tests for the Amperfied Connect Modbus config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.amperfied_connect_modbus.const import CONF_DEVICE_ID, DOMAIN
from custom_components.amperfied_connect_modbus.core.exceptions import (
    HeidelbergEnergyControlConnectionError,
)

OLD_HOST = "192.0.2.10"
NEW_HOST = "192.0.2.20"


def _entry(host: str = OLD_HOST, *, unique_id: str | None = None) -> MockConfigEntry:
    """Create a wallbox config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Wallbox",
        unique_id=unique_id or f"{host}-1",
        data={
            CONF_NAME: "Wallbox",
            CONF_HOST: host,
            CONF_PORT: 502,
            CONF_DEVICE_ID: 1,
        },
    )


async def _start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry):
    """Start a reconfigure flow for an entry."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )


async def test_reconfigure_form_uses_current_connection(hass: HomeAssistant) -> None:
    """The form should be pre-filled with the current connection."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["data_schema"]({}) == {
        CONF_HOST: OLD_HOST,
        CONF_PORT: 502,
        CONF_DEVICE_ID: 1,
    }


async def test_reconfigure_updates_existing_entry(hass: HomeAssistant) -> None:
    """A valid connection should update and reload the existing entry."""
    entry = _entry()
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry)
    new_connection = {
        CONF_HOST: NEW_HOST,
        CONF_PORT: 1502,
        CONF_DEVICE_ID: 2,
    }

    with (
        patch(
            "custom_components.amperfied_connect_modbus.config_flow.validate_input",
            new=AsyncMock(return_value={"title": "Wallbox"}),
        ) as validate,
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_connection
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_NAME: "Wallbox",
        **new_connection,
    }
    assert entry.unique_id == f"{NEW_HOST}-2"
    validate.assert_awaited_once_with(
        {
            CONF_NAME: "Wallbox",
            **new_connection,
        }
    )
    reload_entry.assert_called_once_with(entry.entry_id)


async def test_reconfigure_rejects_unreachable_wallbox(hass: HomeAssistant) -> None:
    """An unreachable replacement must leave the existing entry untouched."""
    entry = _entry()
    entry.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry)

    with patch(
        "custom_components.amperfied_connect_modbus.config_flow.validate_input",
        new=AsyncMock(side_effect=HeidelbergEnergyControlConnectionError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: NEW_HOST,
                CONF_PORT: 502,
                CONF_DEVICE_ID: 1,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == OLD_HOST
    assert entry.unique_id == f"{OLD_HOST}-1"


async def test_reconfigure_rejects_duplicate_connection(hass: HomeAssistant) -> None:
    """A connection already used by another entry must be rejected."""
    entry = _entry()
    entry.add_to_hass(hass)
    duplicate = _entry(NEW_HOST)
    duplicate.add_to_hass(hass)
    result = await _start_reconfigure(hass, entry)

    with patch(
        "custom_components.amperfied_connect_modbus.config_flow.validate_input",
        new=AsyncMock(),
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: NEW_HOST,
                CONF_PORT: 502,
                CONF_DEVICE_ID: 1,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert entry.data[CONF_HOST] == OLD_HOST
    validate.assert_not_awaited()
