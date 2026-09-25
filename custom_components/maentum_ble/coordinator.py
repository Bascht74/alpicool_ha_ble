"""Data update coordinator for the MAENTUM BLE integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import MaentumClient, MaentumError
from .const import DOMAIN
from .protocol import FridgeStatus

_LOGGER = logging.getLogger(__name__)

type MaentumConfigEntry = ConfigEntry[MaentumCoordinator]


class MaentumCoordinator(DataUpdateCoordinator[FridgeStatus]):
    """Poll the box and run commands against it."""

    config_entry: MaentumConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MaentumConfigEntry,
        client: MaentumClient,
        scan_interval: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.address}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> FridgeStatus:
        try:
            return await self.client.async_query()
        except MaentumError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_command(
        self, command: Callable[[FridgeStatus], Awaitable[FridgeStatus]]
    ) -> None:
        """Run a command with the last known status and publish the result."""
        if self.data is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_status")
        try:
            status = await command(self.data)
        except MaentumError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.async_set_updated_data(status)
