"""Config flow for the MAENTUM BLE integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
import voluptuous as vol

from .client import MaentumClient, MaentumError, MaentumNotSupportedError
from .const import (
    CONF_KEEP_CONNECTED,
    CONF_SCAN_INTERVAL,
    DEFAULT_KEEP_CONNECTED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KNOWN_NAME_PREFIXES,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SERVICE_UUID,
)
from .coordinator import MaentumConfigEntry

_LOGGER = logging.getLogger(__name__)


def looks_like_fridge(info: BluetoothServiceInfoBleak) -> bool:
    """Return True if the advertisement hints at an Alpicool-type box."""
    if SERVICE_UUID in (uuid.lower() for uuid in info.service_uuids):
        return True
    return (info.name or "").upper().startswith(KNOWN_NAME_PREFIXES)


def _title(info: BluetoothServiceInfoBleak) -> str:
    return info.name if info.name and info.name != info.address else info.address


class MaentumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a box."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._candidates: dict[str, BluetoothServiceInfoBleak] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: MaentumConfigEntry) -> MaentumOptionsFlow:
        """Return the options flow."""
        return MaentumOptionsFlow()

    async def _async_validate(self, address: str) -> str | None:
        """Connect once and read the status. Return an error key or None."""
        device = async_ble_device_from_address(self.hass, address, connectable=True)
        if device is None:
            return "cannot_connect"
        client = MaentumClient(address, lambda: device, keep_connected=False)
        try:
            await client.async_query()
        except MaentumNotSupportedError:
            return "not_supported"
        except MaentumError as err:
            _LOGGER.debug("Validation of %s failed: %s", address, err)
            return "cannot_connect"
        finally:
            await client.disconnect()
        return None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a box found by Home Assistant's Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": _title(discovery_info)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered box."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if (error := await self._async_validate(self._discovery.address)) is None:
                return self.async_create_entry(
                    title=_title(self._discovery),
                    data={CONF_ADDRESS: self._discovery.address},
                )
            errors["base"] = error
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": _title(self._discovery)},
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick a box from all connectable Bluetooth devices in range."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if (error := await self._async_validate(address)) is None:
                info = self._candidates.get(address)
                return self.async_create_entry(
                    title=_title(info) if info else address,
                    data={CONF_ADDRESS: address},
                )
            errors["base"] = error

        configured = self._async_current_ids(include_ignore=False)
        self._candidates = {
            info.address: info
            for info in async_discovered_service_info(self.hass, connectable=True)
            if info.address not in configured
        }
        if not self._candidates:
            return self.async_abort(reason="no_devices_found")

        # Likely boxes first, the rest because MAENTUM names are not documented.
        ordered = sorted(
            self._candidates.values(),
            key=lambda i: (not looks_like_fridge(i), -(i.rssi or -127), i.address),
        )
        options = [
            SelectOptionDict(
                value=info.address,
                label=(
                    f"{'★ ' if looks_like_fridge(info) else ''}{_title(info)} "
                    f"({info.address}, {info.rssi} dBm)"
                ),
            )
            for info in ordered
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): SelectSelector(SelectSelectorConfig(options=options))}
            ),
            errors=errors,
        )


class MaentumOptionsFlow(OptionsFlow):
    """Change polling behaviour."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_KEEP_CONNECTED,
                    default=options.get(CONF_KEEP_CONNECTED, DEFAULT_KEEP_CONNECTED),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
