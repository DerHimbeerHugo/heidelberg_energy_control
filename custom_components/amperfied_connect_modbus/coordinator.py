"""Coordinator for Amperfied Connect Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from packaging import version

from .const import (
    COMMAND_ECO_MODE,
    COMMAND_PHASE_SWITCH,
    COMMAND_TARGET_CURRENT,
    COMMAND_WATCHDOG_TIMEOUT,
    CONF_AUTO_THREE_PHASE_AFTER_ECO,
    CONF_PHASE_SWITCH_VERIFY,
    CONF_REARM_ON_DISCONNECT,
    DATA_HW_MAX_CURR,
    DATA_IS_PLUGGED,
    DATA_PHASE_SWITCH_DURATION,
    DATA_PHASE_SWITCH_STATE,
    DATA_REG_LAYOUT_VER,
    DEFAULT_AUTO_THREE_PHASE_AFTER_ECO,
    DEFAULT_PHASE_SWITCH_DURATION,
    DEFAULT_PHASE_SWITCH_VERIFY,
    DEFAULT_REARM_ON_DISCONNECT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PHASE_SWITCH_GRACE_PERIOD,
    PHASE_SWITCH_VERIFY_MARGIN,
    VIRTUAL_ENABLE,
    VIRTUAL_TARGET_CURRENT,
)
from .core.capabilities.phase_switch import PHASE_ONE, PHASE_THREE
from .core.exceptions import (
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
    HeidelbergEnergyControlWriteError,
)

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching and proxy logic."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Any,
        static_data: dict[str, str],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.static_data = static_data
        self.entry = entry

        # The virtual enable/target-current UI depends on writing register 261
        # to 0 as "off"; below firmware 1.0.7 there's no way to turn it back on
        # from the UI, so we suppress the virtual layer and pass raw hardware
        # data through instead. Fail-open if the layout version can't be parsed.
        self.supports_virtual_logic = self._parse_supports_virtual_logic(static_data)

        # Get hardware limits from static data
        hw_max_current = float(static_data.get(DATA_HW_MAX_CURR, 16))
        default_current = min(16.0, hw_max_current)

        # Internal state memory for proxy logic
        self.target_current: float = default_current
        self.logic_enabled: bool = False
        self._initial_fetch_done: bool = False
        self._consecutive_empty_responses: int = 0
        self._scan_interval_seconds: int = scan_interval
        self._watchdog_warning_logged: bool = False
        self._last_eco_mode_state: bool | None = None
        self._last_is_plugged: bool | None = None
        self._phase_verification_task: asyncio.Task[None] | None = None

        self.auto_three_phase_after_eco = entry.options.get(
            CONF_AUTO_THREE_PHASE_AFTER_ECO,
            DEFAULT_AUTO_THREE_PHASE_AFTER_ECO,
        )
        self.phase_switch_verify = entry.options.get(
            CONF_PHASE_SWITCH_VERIFY,
            DEFAULT_PHASE_SWITCH_VERIFY,
        )
        self.rearm_on_disconnect = entry.options.get(
            CONF_REARM_ON_DISCONNECT,
            DEFAULT_REARM_ON_DISCONNECT,
        )

        # Initialize data dictionary
        self.data: dict[str, Any] = {
            VIRTUAL_ENABLE: False,
            VIRTUAL_TARGET_CURRENT: default_current,
            COMMAND_TARGET_CURRENT: 0.0,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from hardware and sync virtual states."""
        try:
            # Fetch all registers from the wallbox via Modbus API
            data = await self.api.async_get_data()
            if not data:
                self._consecutive_empty_responses += 1
                _LOGGER.warning(
                    "Empty data response from wallbox (consecutive count: %s), keeping previous state",
                    self._consecutive_empty_responses,
                )
                if self._consecutive_empty_responses >= 3:
                    raise UpdateFailed(
                        "Wallbox returned empty data for 3 consecutive updates"
                    )
                return self.data

            self._check_watchdog_headroom(data)
            await self._async_handle_external_eco_transition(data)

            # If virtual logic is not supported, just return raw data (Legacy Mode)
            if not self.supports_virtual_logic:
                self._track_vehicle_connection(data)
                return data

            # --- Virtual Logic (only for V1.0.7+) ---
            # Raw value is deci-amps; convert to amps for the virtual entities.
            hw_current = float(data.get(COMMAND_TARGET_CURRENT, 0)) / 10.0

            # Initial sync on startup: Read wallbox current state
            if not self._initial_fetch_done:
                if hw_current > 0:
                    self.target_current = hw_current
                    self.logic_enabled = True
                self._initial_fetch_done = True

            # Bidirectional Synchronization Logic:
            # 1. If hardware is 0, the virtual 'enable' switch must be turned OFF
            if hw_current == 0.0 and self.logic_enabled:
                _LOGGER.info("Wallbox reported 0.0A: Setting virtual enable to OFF")
                self.logic_enabled = False

            # 2. If hardware is > 0 but our switch was OFF (e.g. external override),
            # we must turn the switch ON and update our target slider to match reality
            elif hw_current > 0.0 and not self.logic_enabled:
                _LOGGER.info(
                    "Wallbox reported %sA (external change): Setting virtual enable to ON",
                    hw_current,
                )
                self.logic_enabled = True
                self.target_current = hw_current

            # Ensure virtual states are always synced into the data dict for the generic UI entities
            data[VIRTUAL_ENABLE] = self.logic_enabled
            data[VIRTUAL_TARGET_CURRENT] = self.target_current

            await self._async_handle_vehicle_connection(data)

            # Reset consecutive empty response counter on successful update
            self._consecutive_empty_responses = 0

            # Note: COMMAND_TARGET_CURRENT remains the raw hardware value (will show 0.0 when logic is off)
            return data

        except HeidelbergEnergyControlConnectionError as err:
            raise UpdateFailed(
                f"Connection to Modbus gateway failed: {err}",
                retry_after=30,
            ) from err

        except HeidelbergEnergyControlReadError as err:
            raise UpdateFailed(f"Failed to read from Wallbox: {err}") from err

        except Exception as err:
            # Catch unexpected errors and log full traceback
            _LOGGER.exception("Unexpected error in coordinator update")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _supports_phase_switch(self) -> bool:
        """Return whether the optional phase-switch capability was loaded."""
        return any(
            capability.key == "phase_switch" for capability in self.api.capabilities
        )

    async def _async_restore_three_phase(self, source: str) -> bool:
        """Set manual charging to three phases when phase control is available."""
        if not self.auto_three_phase_after_eco or not self._supports_phase_switch():
            return True

        try:
            await self.async_set_phase(PHASE_THREE, source=source)
            _LOGGER.info(
                "Eco mode disabled via %s: restored three-phase charging", source
            )
            return True
        except (
            HeidelbergEnergyControlWriteError,
            HeidelbergEnergyControlConnectionError,
        ) as err:
            _LOGGER.error(
                "Eco mode is off, but restoring three-phase charging failed: %s",
                err,
            )
            return False

    async def _async_handle_external_eco_transition(self, data: dict[str, Any]) -> None:
        """Restore three phases when Eco is disabled outside Home Assistant."""
        eco_state = data.get(COMMAND_ECO_MODE)
        if not isinstance(eco_state, bool):
            return

        previous = self._last_eco_mode_state
        if previous is True and eco_state is False:
            if await self._async_restore_three_phase("external control"):
                self._last_eco_mode_state = False
            return

        self._last_eco_mode_state = eco_state

    async def async_handle_eco_mode_change(self, is_on: bool) -> None:
        """Write Eco mode and restore three phases whenever Eco is disabled."""
        register_value = 1 if is_on else 0
        success = await self.api.async_write_command(COMMAND_ECO_MODE, register_value)
        if not success:
            return

        self.data[COMMAND_ECO_MODE] = is_on

        if is_on:
            self._last_eco_mode_state = True
        elif await self._async_restore_three_phase("Home Assistant"):
            self._last_eco_mode_state = False

        self.async_set_updated_data(self.data)

    async def async_set_phase(self, value: int, *, source: str) -> None:
        """Write a phase command and schedule one bounded verification cycle."""
        if value not in (PHASE_ONE, PHASE_THREE):
            raise HomeAssistantError(f"Unsupported phase count: {value}")
        if not self._supports_phase_switch():
            raise HomeAssistantError("This wallbox does not support phase switching")

        success = await self.api.async_write_command(COMMAND_PHASE_SWITCH, value)
        if not success:
            raise HeidelbergEnergyControlWriteError(
                "The wallbox rejected the phase-switch command"
            )

        _LOGGER.info("Requested %s-phase charging via %s", value, source)
        if self.phase_switch_verify:
            self._schedule_phase_verification(value, source)

    def _schedule_phase_verification(self, target: int, source: str) -> None:
        """Replace any pending verification with one for the newest command."""
        if self._phase_verification_task is not None:
            self._phase_verification_task.cancel()

        self._phase_verification_task = self.hass.async_create_background_task(
            self._async_verify_phase_switch(target, source),
            f"{DOMAIN} phase switch verification",
        )

    async def _async_verify_phase_switch(self, target: int, source: str) -> None:
        """Verify a phase change and retry its command no more than once."""
        current_task = asyncio.current_task()
        duration = self.data.get(
            DATA_PHASE_SWITCH_DURATION, DEFAULT_PHASE_SWITCH_DURATION
        )
        if not isinstance(duration, (int, float)) or duration <= 0:
            duration = DEFAULT_PHASE_SWITCH_DURATION
        verify_delay = float(duration) + PHASE_SWITCH_VERIFY_MARGIN

        try:
            await asyncio.sleep(verify_delay)
            state = await self._async_refresh_phase_state()
            if state == target:
                self._dismiss_phase_failure_notification()
                return
            if state is None:
                self._notify_phase_switch_failure(
                    target,
                    "The wallbox state could not be read; no retry was sent.",
                )
                return

            # State 0 means the internal contactor is still switching. Give it one
            # short grace period before deciding whether a retry is necessary.
            if state == 0:
                await asyncio.sleep(PHASE_SWITCH_GRACE_PERIOD)
                state = await self._async_refresh_phase_state()
                if state == target:
                    self._dismiss_phase_failure_notification()
                    return
                if state is None:
                    self._notify_phase_switch_failure(
                        target,
                        "The wallbox state could not be read; no retry was sent.",
                    )
                    return

            _LOGGER.warning(
                "Phase switch requested via %s did not reach %s phases; retrying once",
                source,
                target,
            )
            try:
                success = await self.api.async_write_command(
                    COMMAND_PHASE_SWITCH, target
                )
            except (
                HeidelbergEnergyControlWriteError,
                HeidelbergEnergyControlConnectionError,
            ) as err:
                self._notify_phase_switch_failure(target, str(err))
                return

            if not success:
                self._notify_phase_switch_failure(
                    target, "The wallbox rejected the one-time retry."
                )
                return

            await asyncio.sleep(verify_delay)
            state = await self._async_refresh_phase_state()
            if state == target:
                self._dismiss_phase_failure_notification()
                return

            detail = (
                "The final state could not be read."
                if state is None
                else f"The final phase-switch state was {state}."
            )
            self._notify_phase_switch_failure(target, detail)
        finally:
            if self._phase_verification_task is current_task:
                self._phase_verification_task = None

    async def _async_refresh_phase_state(self) -> int | None:
        """Refresh coordinator data and return the phase-switch feedback value."""
        await self.async_refresh()
        if not self.last_update_success:
            return None
        state = self.data.get(DATA_PHASE_SWITCH_STATE)
        return state if state in (0, PHASE_ONE, PHASE_THREE) else None

    def _phase_failure_notification_id(self) -> str:
        """Return a stable notification id for this config entry."""
        return f"{DOMAIN}_phase_switch_{self.entry.entry_id}"

    def _notify_phase_switch_failure(self, target: int, detail: str) -> None:
        """Raise one persistent HA notification after the bounded retry failed."""
        _LOGGER.error(
            "Phase switch to %s phases failed after one retry: %s", target, detail
        )
        persistent_notification.async_create(
            self.hass,
            (
                f"The wallbox did not switch to {target} phases after one retry. "
                f"{detail} No further commands will be sent automatically."
            ),
            title="Amperfied phase switching failed",
            notification_id=self._phase_failure_notification_id(),
        )

    def _dismiss_phase_failure_notification(self) -> None:
        """Dismiss an earlier phase error after a later successful command."""
        persistent_notification.async_dismiss(
            self.hass, self._phase_failure_notification_id()
        )

    async def _write_current_to_wallbox(
        self, value: float, data: dict[str, Any] | None = None
    ) -> bool:
        """Internal helper to write a specific Ampere value."""
        if not self.supports_virtual_logic:
            _LOGGER.error("Firmware too old to support writing to register 261")
            return False

        modbus_value = int(value * 10.0)
        try:
            await self.api.async_write_command(COMMAND_TARGET_CURRENT, modbus_value)

            self.data[COMMAND_TARGET_CURRENT] = modbus_value
            if data is not None:
                data[COMMAND_TARGET_CURRENT] = modbus_value
            self.async_update_listeners()
            return True

        except (
            HeidelbergEnergyControlWriteError,
            HeidelbergEnergyControlConnectionError,
        ) as err:
            _LOGGER.error("Failed to write to wallbox: %s", err)

            # If write fails due to connection, we also want to mark the coordinator as failed
            # This ensures entities reflect the broken state immediately
            self.last_update_success = False
            return False

        except Exception as err:
            # Catch unexpected errors and log full traceback
            _LOGGER.exception("Unexpected error during write operation")
            raise HomeAssistantError(f"Failed to set current: {err}") from err

    async def async_set_charging_enabled(
        self,
        is_on: bool,
        *,
        source: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """Set register 261 while keeping the virtual entities synchronized."""
        if not self.supports_virtual_logic:
            raise HomeAssistantError(
                "This register layout does not support the charge-enable control"
            )

        previous = self.logic_enabled
        current_to_write = self.target_current if is_on else 0.0
        if not await self._write_current_to_wallbox(current_to_write, data):
            self.logic_enabled = previous
            return False

        self.logic_enabled = is_on
        self.data[VIRTUAL_ENABLE] = is_on
        if data is not None:
            data[VIRTUAL_ENABLE] = is_on
            data[VIRTUAL_TARGET_CURRENT] = self.target_current
        _LOGGER.info("Charge enable set to %s via %s", "on" if is_on else "off", source)
        self.async_update_listeners()
        return True

    async def async_stop_charging(self) -> None:
        """End the active charging session by setting register 261 to zero."""
        if not await self.async_set_charging_enabled(
            False, source="Home Assistant stop button"
        ):
            raise HomeAssistantError("Failed to stop charging")

    async def _async_handle_vehicle_connection(self, data: dict[str, Any]) -> None:
        """Re-enable charging once when the vehicle becomes disconnected."""
        is_plugged = data.get(DATA_IS_PLUGGED)
        if not isinstance(is_plugged, bool):
            return

        previous = self._last_is_plugged
        self._last_is_plugged = is_plugged
        should_rearm = (
            self.rearm_on_disconnect
            and not is_plugged
            and not self.logic_enabled
            and (previous is None or previous is True)
        )
        if not should_rearm:
            return

        source = "integration startup" if previous is None else "vehicle disconnect"
        if await self.async_set_charging_enabled(True, source=source, data=data):
            return

        _LOGGER.error("Could not restore charge enable after %s", source)
        persistent_notification.async_create(
            self.hass,
            (
                "Charge enable could not be restored after the vehicle was "
                "disconnected. No further automatic attempts will be made."
            ),
            title="Amperfied charge enable not restored",
            notification_id=f"{DOMAIN}_charge_rearm_{self.entry.entry_id}",
        )

    def _track_vehicle_connection(self, data: dict[str, Any]) -> None:
        """Track the connection edge on register layouts without virtual logic."""
        is_plugged = data.get(DATA_IS_PLUGGED)
        if isinstance(is_plugged, bool):
            self._last_is_plugged = is_plugged

    async def async_handle_switch_state_change(self, key: str, is_on: bool) -> None:
        """Handle UI requests from the virtual enable switch."""
        if not self.supports_virtual_logic:
            return

        if key == VIRTUAL_ENABLE:
            if not await self.async_set_charging_enabled(
                is_on, source="Home Assistant charge-enable switch"
            ):
                raise HomeAssistantError("Failed to change charge enable")
        else:
            _LOGGER.warning("Unknown key '%s' in switch state change handler", key)

    async def async_handle_number_set(self, key: str, value: float) -> None:
        """Handle UI requests from the virtual target current slider."""
        if not self.supports_virtual_logic:
            return

        if key == VIRTUAL_TARGET_CURRENT:
            # Always store the new 'desired' value, even if wallbox is currently disabled
            self.target_current = value
            self.data[VIRTUAL_TARGET_CURRENT] = value

            # Only push the update to hardware if the charging logic is currently ENABLED
            if self.logic_enabled:
                await self._write_current_to_wallbox(value)
            else:
                _LOGGER.debug(
                    "Stored new target %sA, hardware remains at 0.0A until enabled",
                    value,
                )
                self.async_update_listeners()
        else:
            _LOGGER.warning("Unknown key '%s' in number set handler", key)

    async def async_shutdown(self) -> None:
        """Cancel delayed verification work during config-entry unload."""
        if self._phase_verification_task is None:
            return
        self._phase_verification_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._phase_verification_task
        self._phase_verification_task = None

    def _check_watchdog_headroom(self, data: dict[str, Any]) -> None:
        """Warn once if the poll interval is too slow to keep the watchdog fed.

        The wallbox falls back to the FailSafe current if it doesn't see a
        successful transaction within the watchdog window. A poll interval
        near the timeout gives no room for a single missed poll; warn the
        user once when scan_interval * 1.5 > timeout so they can retune.

        Watchdog timeout is stored in the coordinator data as raw ms (wire
        format); convert to seconds here for a like-for-like comparison
        against the scan interval.
        """
        if self._watchdog_warning_logged:
            return
        timeout_ms = data.get(COMMAND_WATCHDOG_TIMEOUT)
        if not timeout_ms:  # None or 0 (watchdog disabled)
            return
        timeout_seconds = timeout_ms / 1000.0
        headroom_seconds = self._scan_interval_seconds * 1.5
        if headroom_seconds > timeout_seconds:
            _LOGGER.warning(
                "Poll interval %ss leaves no headroom for the wallbox watchdog "
                "(timeout %ss). A single missed poll may trigger the FailSafe "
                "current. Consider a shorter poll interval or a longer watchdog.",
                self._scan_interval_seconds,
                timeout_seconds,
            )
            self._watchdog_warning_logged = True

    @staticmethod
    def _parse_supports_virtual_logic(static_data: dict[str, str]) -> bool:
        """Return True iff the layout version supports the virtual enable layer.

        The virtual layer depends on register 261 semantics that landed in
        firmware 1.0.7. Fail-open on missing or unparseable versions so a
        misreport doesn't disable a feature that would otherwise work.
        """
        layout_str = static_data.get(DATA_REG_LAYOUT_VER)
        if layout_str is None:
            _LOGGER.warning(
                "Layout version not in static data; assuming virtual enable is supported"
            )
            return True
        try:
            return version.parse(layout_str) >= version.parse("1.0.7")
        except version.InvalidVersion:
            _LOGGER.warning(
                "Could not parse layout version %r; assuming virtual enable is supported",
                layout_str,
            )
            return True
