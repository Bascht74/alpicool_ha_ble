"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maentum_ble.const import DOMAIN
from custom_components.maentum_ble.protocol import FridgeStatus, parse_status

ADDRESS = "AA:BB:CC:DD:EE:FF"

# Status payload from the BrassMonkeyFridgeMonitor README: target -15, current -13,
# range -20..20, 12.3 V, 100 %.
SINGLE_PAYLOAD = bytes.fromhex("00 01 00 00 f1 14 ec 02 00 00 00 00 00 00 f3 64 0c 03")
# Synthetic dual-zone payload: zone 2 target 4, current 6.
DUAL_PAYLOAD = SINGLE_PAYLOAD + bytes([4, 0, 0, 1, 0, 0, 0, 0, 6, 1])


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components in every test."""


@pytest.fixture(autouse=True)
def mock_bluetooth_deps(enable_bluetooth: None) -> None:
    """Set up the Bluetooth stack with mocked adapters."""


@pytest.fixture
def single_status() -> FridgeStatus:
    """A single-zone status."""
    return parse_status(SINGLE_PAYLOAD)


@pytest.fixture
def dual_status() -> FridgeStatus:
    """A dual-zone status."""
    return parse_status(DUAL_PAYLOAD)


@pytest.fixture
def ble_device() -> BLEDevice:
    """A BLE device as Home Assistant would resolve it."""
    return BLEDevice(ADDRESS, "WT-0001", {})


@pytest.fixture
def mock_client(single_status: FridgeStatus) -> Generator[MagicMock]:
    """Replace the BLE client used by the integration."""
    with patch("custom_components.maentum_ble.MaentumClient", autospec=True) as cls:
        client = cls.return_value
        client.address = ADDRESS
        client.is_connected = True
        client.last_frame = None
        client.async_query = AsyncMock(return_value=single_status)
        client.async_set = AsyncMock(return_value=single_status)
        client.async_set_target = AsyncMock(return_value=single_status)
        client.disconnect = AsyncMock()
        yield client


@pytest.fixture
def mock_ble_lookup(ble_device: BLEDevice) -> Generator[MagicMock]:
    """Pretend the box is in range."""
    with patch(
        "custom_components.maentum_ble.bluetooth.async_ble_device_from_address",
        return_value=ble_device,
    ) as lookup:
        yield lookup


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A config entry for the box."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="WT-0001", unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_lookup: MagicMock,
) -> MockConfigEntry:
    """Set up the integration with a mocked box."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
