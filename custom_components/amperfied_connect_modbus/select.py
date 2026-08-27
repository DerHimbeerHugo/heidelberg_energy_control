"""Select platform for Amperfied Connect Modbus."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_select import (
    OPTION_ONE_PHASE,
    OPTION_THREE_PHASES,
    HeidelbergPhaseSelect,
)
from .const import COMMAND_PHASE_SWITCH
from .core.capabilities import Capability, PhaseSwitchCapability


@dataclass(frozen=True, kw_only=True)
class HeidelbergSelectEntityDescription(SelectEntityDescription):
    """Class describing Heidelberg select entities."""

    capability: type[Capability]


SELECT_TYPES: tuple[HeidelbergSelectEntityDescription, ...] = (
    HeidelbergSelectEntityDescription(
        key=COMMAND_PHASE_SWITCH,
        translation_key=COMMAND_PHASE_SWITCH,
        options=(OPTION_ONE_PHASE, OPTION_THREE_PHASES),
        icon="mdi:electric-switch",
        entity_category=EntityCategory.CONFIG,
        capability=PhaseSwitchCapability,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = entry.runtime_data
    loaded_types = {type(capability) for capability in coordinator.api.capabilities}

    entities: list[SelectEntity] = [
        HeidelbergPhaseSelect(coordinator, entry, description)
        for description in SELECT_TYPES
        if description.capability in loaded_types
    ]
    async_add_entities(entities)
