"""Tests for setup and unload."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.maentum_ble.client import MaentumConnectionError


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The entry loads, creates entities and closes the link on unload."""
    assert setup_integration.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.wt_0001") is not None
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_client.disconnect.assert_awaited()


async def test_not_in_range(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Setup is retried while no adapter sees the box."""
    with patch(
        "custom_components.maentum_ble.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_first_query_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_lookup: MagicMock,
) -> None:
    """Setup is retried when the box does not answer."""
    mock_client.async_query.side_effect = MaentumConnectionError("boom")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.disconnect.assert_awaited()


async def test_update_failure_marks_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities go unavailable when a poll fails and recover afterwards."""
    status = mock_client.async_query.return_value
    mock_client.async_query.side_effect = MaentumConnectionError("gone")
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("climate.wt_0001").state == STATE_UNAVAILABLE

    mock_client.async_query.side_effect = None
    mock_client.async_query.return_value = status
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("climate.wt_0001").state == "cool"


async def test_options_reload(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Changing options reloads the entry with the new interval."""
    hass.config_entries.async_update_entry(
        setup_integration, options={"scan_interval": 60, "keep_connected": False}
    )
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.LOADED
    coordinator = setup_integration.runtime_data
    assert coordinator.update_interval == timedelta(seconds=60)
