"""Switch entity for the control panel lock."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaentumConfigEntry, MaentumCoordinator
from .entity import MaentumEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaentumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the switch."""
    async_add_entities([MaentumLockSwitch(entry.runtime_data)])


class MaentumLockSwitch(MaentumEntity, SwitchEntity):
    """Lock the buttons on the box."""

    _attr_translation_key = "controls_locked"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: MaentumCoordinator) -> None:
        """Initialise the switch."""
        super().__init__(coordinator, "controls_locked")

    @property
    def is_on(self) -> bool:
        """Return True while the buttons are locked."""
        return self.coordinator.data.locked

    async def _set(self, locked: bool) -> None:
        client = self.coordinator.client
        await self.coordinator.async_command(lambda s: client.async_set(s, locked=locked))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the buttons."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the buttons."""
        await self._set(False)
