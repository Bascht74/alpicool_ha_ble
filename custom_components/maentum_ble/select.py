"""Select entity for the low voltage cut-out."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaentumConfigEntry, MaentumCoordinator
from .entity import MaentumEntity
from .protocol import BatterySaver

PARALLEL_UPDATES = 1

_OPTIONS = {"low": BatterySaver.LOW, "mid": BatterySaver.MID, "high": BatterySaver.HIGH}
_BY_VALUE = {value: option for option, value in _OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaentumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the select."""
    async_add_entities([MaentumBatterySaverSelect(entry.runtime_data)])


class MaentumBatterySaverSelect(MaentumEntity, SelectEntity):
    """Battery protection level (low voltage cut-out)."""

    _attr_translation_key = "battery_saver"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(_OPTIONS)

    def __init__(self, coordinator: MaentumCoordinator) -> None:
        """Initialise the select."""
        super().__init__(coordinator, "battery_saver")

    @property
    def current_option(self) -> str | None:
        """Return the current level, None if the box reports an unknown value."""
        return _BY_VALUE.get(self.coordinator.data.battery_saver)

    async def async_select_option(self, option: str) -> None:
        """Change the level."""
        client = self.coordinator.client
        level = _OPTIONS[option]
        await self.coordinator.async_command(lambda s: client.async_set(s, battery_saver=level))
