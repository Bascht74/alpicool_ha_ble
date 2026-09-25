"""Base entity for the MAENTUM BLE integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MaentumCoordinator


class MaentumEntity(CoordinatorEntity[MaentumCoordinator]):
    """Common device info and unique id."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MaentumCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        address = coordinator.client.address
        self._attr_unique_id = f"{address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            name=coordinator.config_entry.title,
            manufacturer="Alpicool-compatible",
            model="Dual-Zone" if coordinator.data.is_dual_zone else "Single-Zone",
        )
