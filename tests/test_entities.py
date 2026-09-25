"""Tests for the entity platforms."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maentum_ble.client import MaentumConnectionError
from custom_components.maentum_ble.protocol import FridgeStatus, RunMode

CLIMATE = "climate.wt_0001"


async def test_climate_state(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """The climate entity mirrors the status."""
    state = hass.states.get(CLIMATE)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == -15
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == -13
    assert state.attributes[ATTR_MIN_TEMP] == -20
    assert state.attributes[ATTR_MAX_TEMP] == 20
    assert state.attributes[ATTR_PRESET_MODE] == "max"


async def test_set_temperature(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Setting a target sends it to zone 1."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 4},
        blocking=True,
    )
    mock_client.async_set_target.assert_awaited_once_with(1, 4)


async def test_set_temperature_out_of_range(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Values outside the box's range are rejected before sending."""
    await hass.config.async_update(unit_system="metric")
    state = hass.states.get(CLIMATE)
    assert state.attributes[ATTR_MIN_TEMP] == -20
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: -25},
            blocking=True,
        )
    mock_client.async_set_target.assert_not_awaited()


async def test_hvac_off(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    single_status: FridgeStatus,
) -> None:
    """Turning off sends a Set with powered_on False and shows the result."""
    mock_client.async_set.return_value = replace(single_status, powered_on=False)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_client.async_set.assert_awaited_once_with(single_status, powered_on=False)
    assert hass.states.get(CLIMATE).state == HVACMode.OFF


async def test_hvac_same_mode_sends_nothing(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Selecting the current mode does not write."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_client.async_set.assert_not_awaited()


async def test_preset(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    single_status: FridgeStatus,
) -> None:
    """Eco preset sets run mode 1."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )
    mock_client.async_set.assert_awaited_once_with(single_status, run_mode=RunMode.ECO)


async def test_command_error(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A failed write surfaces as HomeAssistantError."""
    mock_client.async_set_target.side_effect = MaentumConnectionError("gone")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 4},
            blocking=True,
        )


async def test_sensors(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Temperature, voltage and battery sensors."""
    temp = hass.states.get("sensor.wt_0001_temperature_zone_1")
    assert temp.state == "-13"
    assert temp.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert hass.states.get("sensor.wt_0001_supply_voltage").state == "12.3"
    assert hass.states.get("sensor.wt_0001_battery").state == "100"
    assert hass.states.get("sensor.wt_0001_temperature_zone_2") is None


async def test_battery_unknown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_lookup: MagicMock,
    single_status: FridgeStatus,
) -> None:
    """0x7f is shown as unknown."""
    mock_client.async_query.return_value = replace(single_status, battery_percent=0x7F)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.wt_0001_battery").state == STATE_UNKNOWN


async def test_fahrenheit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_lookup: MagicMock,
    single_status: FridgeStatus,
) -> None:
    """A box set to Fahrenheit reports Fahrenheit, HA converts for display."""
    mock_client.async_query.return_value = replace(single_status, unit=1)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # -13 °F is -25 °C in a metric Home Assistant.
    assert hass.states.get("sensor.wt_0001_temperature_zone_1").state == "-25.0"


async def test_lock_switch(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    single_status: FridgeStatus,
) -> None:
    """The lock switch sends a Set with locked True."""
    assert hass.states.get("switch.wt_0001_control_panel_lock").state == "off"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wt_0001_control_panel_lock"},
        blocking=True,
    )
    mock_client.async_set.assert_awaited_once_with(single_status, locked=True)


async def test_battery_saver_select(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    single_status: FridgeStatus,
) -> None:
    """The select maps options to levels 0..2."""
    entity_id = "select.wt_0001_battery_protection"
    assert hass.states.get(entity_id).state == "low"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "high"},
        blocking=True,
    )
    mock_client.async_set.assert_awaited_once_with(single_status, battery_saver=2)


async def test_dual_zone(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_lookup: MagicMock,
    dual_status: FridgeStatus,
) -> None:
    """A dual-zone box gets two climate entities and zone 2 uses command 6."""
    mock_client.async_query.return_value = dual_status
    mock_client.async_set_target.return_value = dual_status
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("climate.wt_0001_zone_1").attributes[ATTR_TEMPERATURE] == -15
    zone2 = hass.states.get("climate.wt_0001_zone_2")
    assert zone2.attributes[ATTR_TEMPERATURE] == 4
    assert zone2.attributes[ATTR_CURRENT_TEMPERATURE] == 6
    assert hass.states.get("sensor.wt_0001_temperature_zone_2").state == "6"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.wt_0001_zone_2", ATTR_TEMPERATURE: 2},
        blocking=True,
    )
    mock_client.async_set_target.assert_awaited_once_with(2, 2)


async def test_diagnostics(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Diagnostics contain the raw status and redact the address."""
    from custom_components.maentum_ble.diagnostics import (  # noqa: PLC0415
        async_get_config_entry_diagnostics,
    )

    diag = await async_get_config_entry_diagnostics(hass, setup_integration)
    assert diag["entry"]["data"]["address"] == "**REDACTED**"
    assert diag["status"]["raw"].startswith("00 01 00 00 f1")
