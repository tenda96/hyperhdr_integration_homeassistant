"""Number platform for HyperHDR priority control."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DEFAULT_PRIORITY, DOMAIN
from .coordinator import HyperHDRCoordinator

_LOGGER = logging.getLogger(__name__)

MIN_PRIORITY = 1
MAX_PRIORITY = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HyperHDR number platform."""
    coordinator: HyperHDRCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, "HyperHDR")
    async_add_entities([HyperHDRPriorityNumber(coordinator, name, entry.entry_id)])


class HyperHDRPriorityNumber(CoordinatorEntity, RestoreNumber):
    """Priority slider used by the HyperHDR light entity."""

    def __init__(self, coordinator: HyperHDRCoordinator, name: str, entry_id: str) -> None:
        """Initialize the priority number entity."""
        super().__init__(coordinator)
        self.coordinator: HyperHDRCoordinator = coordinator
        self._entry_id = entry_id

        self._attr_name = f"{name} Priority"
        self._attr_unique_id = f"hyperhdr_{entry_id}_priority"
        self._attr_native_value = DEFAULT_PRIORITY
        self._attr_native_min_value = MIN_PRIORITY
        self._attr_native_max_value = MAX_PRIORITY
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:sort-numeric-ascending"

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Restore the last selected priority after Home Assistant restart/reload."""
        await super().async_added_to_hass()

        last_number_data = await self.async_get_last_number_data()
        if last_number_data and last_number_data.native_value is not None:
            restored = self._sanitize_priority(last_number_data.native_value)
            self._attr_native_value = restored

        self.coordinator.priority = int(self._attr_native_value or DEFAULT_PRIORITY)

    async def async_set_native_value(self, value: float) -> None:
        """Update the selected HyperHDR priority."""
        new_priority = self._sanitize_priority(value)
        old_priority = self.coordinator.priority

        self._attr_native_value = new_priority
        self.coordinator.priority = new_priority

        if old_priority != new_priority:
            light_entity = getattr(self.coordinator, "light_entity", None)
            if light_entity is not None:
                await light_entity.async_migrate_priority(old_priority, new_priority)
            elif self.coordinator.is_priority_visible(old_priority):
                _LOGGER.warning(
                    "Priority changed while old priority %s is active, but no light entity is registered",
                    old_priority,
                )

        self.async_write_ha_state()

    @staticmethod
    def _sanitize_priority(value: float) -> int:
        """Clamp a priority value to the HyperHDR range."""
        return max(MIN_PRIORITY, min(MAX_PRIORITY, int(float(value))))
