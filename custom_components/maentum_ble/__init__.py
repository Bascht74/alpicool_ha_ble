"""MAENTUM / Alpicool-compatible cooler boxes over Bluetooth Low Energy."""

from __future__ import annotations

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .client import MaentumClient
from .const import (
    CONF_KEEP_CONNECTED,
    CONF_SCAN_INTERVAL,
    DEFAULT_KEEP_CONNECTED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import MaentumConfigEntry, MaentumCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: MaentumConfigEntry) -> bool:
    """Set up a box from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    @callback
    def _ble_device() -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(hass, address, connectable=True)

    if _ble_device() is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_in_range",
            translation_placeholders={"address": address},
        )

    client = MaentumClient(
        address,
        _ble_device,
        keep_connected=entry.options.get(CONF_KEEP_CONNECTED, DEFAULT_KEEP_CONNECTED),
    )
    coordinator = MaentumCoordinator(
        hass,
        entry,
        client,
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.disconnect()
        raise
    entry.runtime_data = coordinator

    async def _on_stop(_event: Event) -> None:
        await client.disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: MaentumConfigEntry) -> None:
    """Reload after the options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MaentumConfigEntry) -> bool:
    """Unload a config entry and close the link."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.disconnect()
    return unload_ok
