"""Tests for the config and options flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maentum_ble.client import (
    MaentumConnectionError,
    MaentumNotSupportedError,
)
from custom_components.maentum_ble.const import DOMAIN

from .conftest import ADDRESS

FLOW = "custom_components.maentum_ble.config_flow"


def _info(address: str = ADDRESS, name: str = "WT-0001", uuids: list[str] | None = None):
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak  # noqa: PLC0415

    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids or [],
        source="local",
        device=BLEDevice(address, name, {}),
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )


@pytest.fixture
def flow_client() -> Generator[MagicMock]:
    """Mock the client the flow uses to validate."""
    with (
        patch(f"{FLOW}.MaentumClient", autospec=True) as cls,
        patch(
            f"{FLOW}.async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, "WT-0001", {}),
        ),
    ):
        client = cls.return_value
        client.async_query = AsyncMock()
        client.disconnect = AsyncMock()
        yield client


@pytest.fixture(autouse=True)
def no_setup() -> Generator[None]:
    """Do not set up the entry after the flow."""
    with patch("custom_components.maentum_ble.async_setup_entry", return_value=True):
        yield


async def test_user_flow(hass: HomeAssistant, flow_client: MagicMock) -> None:
    """Pick a device, validate, create the entry."""
    other = _info("11:22:33:44:55:66", "Headphones")
    with patch(f"{FLOW}.async_discovered_service_info", return_value=[other, _info()]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_ADDRESS].config["options"]
    # Likely boxes are listed first and marked.
    assert options[0]["value"] == ADDRESS
    assert options[0]["label"].startswith("★ WT-0001")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WT-0001"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Abort when nothing is in range."""
    with patch(f"{FLOW}.async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (MaentumConnectionError("x"), "cannot_connect"),
        (MaentumNotSupportedError("x"), "not_supported"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, flow_client: MagicMock, error: Exception, key: str
) -> None:
    """Validation errors are shown and the user can retry."""
    with patch(f"{FLOW}.async_discovered_service_info", return_value=[_info()]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        flow_client.async_query.side_effect = error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": key}

        flow_client.async_query.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    flow_client.disconnect.assert_awaited()


async def test_bluetooth_discovery(hass: HomeAssistant, flow_client: MagicMock) -> None:
    """A discovered box is confirmed and validated."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WT-0001"


async def test_bluetooth_already_configured(hass: HomeAssistant) -> None:
    """A known box is not offered again."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Options are stored as int and bool."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 45.0, "keep_connected": False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"scan_interval": 45, "keep_connected": False}


def test_looks_like_fridge() -> None:
    """Name prefixes and the service UUID are recognised."""
    from custom_components.maentum_ble.config_flow import looks_like_fridge  # noqa: PLC0415

    assert looks_like_fridge(_info(name="A1-1234"))
    assert looks_like_fridge(_info(name="x", uuids=["00001234-0000-1000-8000-00805F9B34FB"]))
    assert not looks_like_fridge(_info(name="W1001"))
