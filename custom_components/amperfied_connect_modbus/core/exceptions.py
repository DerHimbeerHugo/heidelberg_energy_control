"""Exceptions for the Amperfied Connect Modbus integration."""

from homeassistant.exceptions import HomeAssistantError


class HeidelbergEnergyControlAPIError(HomeAssistantError):
    """Base exception for Amperfied Connect Modbus API errors."""


class HeidelbergEnergyControlConnectionError(HeidelbergEnergyControlAPIError):
    """Error to indicate a connection problem with the wallbox."""


class HeidelbergEnergyControlReadError(HeidelbergEnergyControlAPIError):
    """Error to indicate a read error from the wallbox."""


class HeidelbergEnergyControlWriteError(HeidelbergEnergyControlAPIError):
    """Error to indicate a write error to the wallbox."""
