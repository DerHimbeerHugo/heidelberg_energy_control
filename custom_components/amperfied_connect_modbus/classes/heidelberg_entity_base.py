"""Heidelberg Entity Base class."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .. import HeidelbergEnergyControlConfigEntry
from ..const import (
    DATA_HW_VARIANT,
    DATA_REG_LAYOUT_VER,
    DATA_SW_VERSION,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
)
from ..coordinator import HeidelbergEnergyControlCoordinator


class HeidelbergEntityBase(CoordinatorEntity[HeidelbergEnergyControlCoordinator]):
    """Common base for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeidelbergEnergyControlCoordinator,
        entry: HeidelbergEnergyControlConfigEntry,
        description: Any,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        hardware_variant = self.coordinator.static_data.get(DATA_HW_VARIANT)
        hardware = (
            f"Variant {hardware_variant}"
            if hardware_variant not in (None, 0)
            else None
        )
        software = self.coordinator.static_data.get(DATA_SW_VERSION)
        if software in (None, "", "0.0.0", "v0.0.0", "V0.0.0"):
            software = None
        elif not str(software).lower().startswith("v"):
            software = "v" + str(software)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            model_id="Register Layout v"
            + self.coordinator.static_data.get(DATA_REG_LAYOUT_VER),
            hw_version=hardware,
            sw_version=software,
        )
