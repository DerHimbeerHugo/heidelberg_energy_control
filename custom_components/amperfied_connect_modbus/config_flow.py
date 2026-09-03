"""Config flow for the Amperfied Connect Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_THREE_PHASE_AFTER_ECO,
    CONF_DEVICE_ID,
    CONF_PHASE_SWITCH_VERIFY,
    CONF_REARM_ON_DISCONNECT,
    DEFAULT_AUTO_THREE_PHASE_AFTER_ECO,
    DEFAULT_PHASE_SWITCH_VERIFY,
    DEFAULT_REARM_ON_DISCONNECT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .core.api import HeidelbergEnergyControlAPI
from .core.exceptions import (
    HeidelbergEnergyControlAPIError,
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Wallbox"): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=502): int,
        vol.Required(CONF_DEVICE_ID, default=1): int,
    }
)


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = HeidelbergEnergyControlAPI(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        device_id=data[CONF_DEVICE_ID],
    )

    try:
        static_data = await api.async_get_static_data()

        if static_data is None:
            raise HeidelbergEnergyControlReadError(
                "Wallbox connected but did not respond to requests"
            )

    except HeidelbergEnergyControlConnectionError:
        raise
    except HeidelbergEnergyControlReadError:
        raise
    except Exception as err:
        _LOGGER.error("Unexpected validation error: %s", err)
        raise HeidelbergEnergyControlAPIError(f"Validation failed: {err}") from err
    finally:
        await api.disconnect()

    return {"title": data[CONF_NAME]}


class HeidelbergEnergyControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amperfied Connect Modbus."""

    VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the wallbox connection without replacing the config entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_unique_id = f"{user_input[CONF_HOST]}-{user_input[CONF_DEVICE_ID]}"
            duplicate_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, new_unique_id
            )

            if (
                duplicate_entry is not None
                and duplicate_entry.entry_id != entry.entry_id
            ):
                errors["base"] = "already_configured"
            else:
                updated_data = {**entry.data, **user_input}
                try:
                    await validate_input(updated_data)
                except HeidelbergEnergyControlConnectionError:
                    errors["base"] = "cannot_connect"
                except HeidelbergEnergyControlReadError:
                    errors["base"] = "invalid_data"
                except HeidelbergEnergyControlAPIError:
                    errors["base"] = "unknown_api_error"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=new_unique_id,
                        data_updates=user_input,
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): int,
                    vol.Required(
                        CONF_DEVICE_ID, default=entry.data[CONF_DEVICE_ID]
                    ): int,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}-{user_input[CONF_DEVICE_ID]}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except HeidelbergEnergyControlConnectionError:
                errors["base"] = "cannot_connect"
            except HeidelbergEnergyControlReadError:
                errors["base"] = "invalid_data"
            except HeidelbergEnergyControlAPIError:
                errors["base"] = "unknown_api_error"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HeidelbergOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HeidelbergOptionsFlowHandler()


class HeidelbergOptionsFlowHandler(OptionsFlow):
    """Handle the options flow for the integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=3,
                            max=30,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Required(
                        CONF_AUTO_THREE_PHASE_AFTER_ECO,
                        default=self.config_entry.options.get(
                            CONF_AUTO_THREE_PHASE_AFTER_ECO,
                            DEFAULT_AUTO_THREE_PHASE_AFTER_ECO,
                        ),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_PHASE_SWITCH_VERIFY,
                        default=self.config_entry.options.get(
                            CONF_PHASE_SWITCH_VERIFY,
                            DEFAULT_PHASE_SWITCH_VERIFY,
                        ),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_REARM_ON_DISCONNECT,
                        default=self.config_entry.options.get(
                            CONF_REARM_ON_DISCONNECT,
                            DEFAULT_REARM_ON_DISCONNECT,
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )
