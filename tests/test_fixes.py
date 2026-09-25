"""Regression tests for fixes found in the review of 2026-09-25."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alpicool_ble.api import FridgeApi
from custom_components.alpicool_ble.climate import AlpicoolClimateZone
from custom_components.alpicool_ble.const import DOMAIN, Request
from custom_components.alpicool_ble.number import NUMBERS, AlpicoolNumber
from custom_components.alpicool_ble.select import AlpicoolBatterySaverSelect
from custom_components.alpicool_ble.sensor import SENSORS, AlpicoolSensor
from custom_components.alpicool_ble.switch import AlpicoolLockSwitch

from test_api import DUAL_ZONE_PAYLOAD, SINGLE_ZONE_PAYLOAD

ADDRESS = "AA:BB:CC:DD:EE:FF"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, data={"address": ADDRESS, "name": "Fridge"}, options={}
    )


def _api(**status) -> MagicMock:
    api = MagicMock()
    api.status = status
    api.is_available = True
    api.is_fahrenheit = False
    api.async_set_values = AsyncMock()
    api.update_status = AsyncMock(return_value=True)
    return api


def _frame(cmd: int, payload: bytes, checksum: bool = True) -> bytearray:
    """Build a frame; real fridges append a two byte checksum."""
    frame = bytearray(b"\xfe\xfe")
    frame.append(len(payload) + 1 + (2 if checksum else 0))
    frame.append(cmd)
    frame.extend(payload)
    if checksum:
        frame.extend((sum(frame) & 0xFFFF).to_bytes(2, "big"))
    return frame


# --- Battery 0x7F -----------------------------------------------------------


def test_battery_percent_unknown_is_none() -> None:
    """0x7F means the fridge does not know the charge level."""
    sensor = AlpicoolSensor(
        _entry(), _api(bat_percent=0x7F), "battery_percent", SENSORS["battery_percent"]
    )
    assert sensor.native_value is None


def test_battery_percent_known_is_passed_through() -> None:
    """Real values are unchanged."""
    sensor = AlpicoolSensor(
        _entry(), _api(bat_percent=87), "battery_percent", SENSORS["battery_percent"]
    )
    assert sensor.native_value == 87


# --- Names do not repeat the device name ----------------------------------


def test_entity_names_do_not_repeat_the_device_name() -> None:
    """has_entity_name adds the device name, so the entity name must not."""
    api = _api()
    assert (
        AlpicoolSensor(
            _entry(), api, "battery_voltage", SENSORS["battery_voltage"]
        ).name
        == "Battery Voltage"
    )
    assert AlpicoolLockSwitch(_entry(), api).name == "Lock"
    assert (
        AlpicoolNumber(_entry(), api, "start_delay", NUMBERS["start_delay"]).name
        == "Start Delay"
    )


# --- Refresh after writes -------------------------------------------------


async def _run_and_check_refresh(entity, call) -> None:
    entity.hass = MagicMock()
    with (
        patch("custom_components.alpicool_ble.entity.asyncio.sleep", AsyncMock()),
        patch("custom_components.alpicool_ble.entity.async_dispatcher_send") as send,
    ):
        await call()
    entity.api.update_status.assert_awaited_once()
    send.assert_called_once()


async def test_lock_switch_refreshes_after_write() -> None:
    """Turning the lock on reads the new status."""
    switch = AlpicoolLockSwitch(_entry(), _api(locked=False))
    await _run_and_check_refresh(switch, switch.async_turn_on)
    switch.api.async_set_values.assert_awaited_once_with({"locked": True})


async def test_select_refreshes_after_write() -> None:
    """Changing the battery saver reads the new status."""
    select = AlpicoolBatterySaverSelect(_entry(), _api(bat_saver=0))
    await _run_and_check_refresh(select, lambda: select.async_select_option("High"))
    select.api.async_set_values.assert_awaited_once_with({"bat_saver": 2})


async def test_number_refreshes_after_write() -> None:
    """Changing a number reads the new status."""
    number = AlpicoolNumber(
        _entry(), _api(start_delay=0), "start_delay", NUMBERS["start_delay"]
    )
    await _run_and_check_refresh(number, lambda: number.async_set_native_value(3))
    number.api.async_set_values.assert_awaited_once_with({"start_delay": 3})


# --- SET answer carries the new status ------------------------------------


def test_set_answer_with_status_is_decoded() -> None:
    """The fridge answers SET with its full status; use it."""
    fridge = FridgeApi(MagicMock(), ADDRESS)
    fridge._notification_handler(None, _frame(Request.SET, SINGLE_ZONE_PAYLOAD))
    assert fridge.status["left_target"] == -5
    assert fridge._status_updated_event.is_set()


def test_set_echo_and_status_in_one_notification() -> None:
    """An echo of the SET command is skipped, the status after it is used."""
    fridge = FridgeApi(MagicMock(), ADDRESS)
    echo = _frame(Request.SET, SINGLE_ZONE_PAYLOAD[:14])
    fridge._notification_handler(None, echo + _frame(Request.SET, DUAL_ZONE_PAYLOAD))
    assert fridge.status["right_target"] == -10


def test_set_echo_alone_is_not_status() -> None:
    """A 14 or 25 byte echo must not be decoded as status."""
    fridge = FridgeApi(MagicMock(), ADDRESS)
    fridge._notification_handler(None, _frame(Request.SET, DUAL_ZONE_PAYLOAD[:25]))
    fridge._notification_handler(
        None, _frame(Request.SET, SINGLE_ZONE_PAYLOAD[:14], checksum=False)
    )
    assert fridge.status == {}
    assert not fridge._status_updated_event.is_set()


# --- climate.turn_on / turn_off -------------------------------------------


async def test_climate_supports_turn_on_and_off() -> None:
    """turn_on/turn_off are advertised and map to the hvac mode."""
    zone = AlpicoolClimateZone(_entry(), _api(powered_on=False), "left")
    assert zone.supported_features & ClimateEntityFeature.TURN_ON
    assert zone.supported_features & ClimateEntityFeature.TURN_OFF
    with patch.object(zone, "async_set_hvac_mode", AsyncMock()) as set_mode:
        await zone.async_turn_on()
        set_mode.assert_awaited_once_with(HVACMode.COOL)
        await zone.async_turn_off()
        set_mode.assert_awaited_with(HVACMode.OFF)


# --- Discovery only offers devices with the fridge service -----------------


def _discovery(uuids: list[str]):
    from bleak.backends.device import BLEDevice
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

    return BluetoothServiceInfoBleak(
        name="Some device",
        address=ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        source="local",
        device=BLEDevice(ADDRESS, "Some device", {}),
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )


FFF0 = "0000fff0-0000-1000-8000-00805f9b34fb"


def _gatt_client(has_chars: bool) -> MagicMock:
    client = MagicMock()
    client.services.get_characteristic.side_effect = (
        lambda uuid: MagicMock() if has_chars else None
    )
    client.disconnect = AsyncMock()
    return client


async def _discover(hass, info, connect):
    with patch(
        "custom_components.alpicool_ble.config_flow.establish_connection", connect
    ):
        return await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "bluetooth"}, data=info
        )


async def test_discovery_with_advertised_service_needs_no_connect(
    hass, enable_bluetooth
) -> None:
    """0x1234 in the advertisement is enough."""
    connect = AsyncMock()
    result = await _discover(
        hass, _discovery(["00001234-0000-1000-8000-00805f9b34fb"]), connect
    )
    assert result["type"] == "form"
    connect.assert_not_awaited()


async def test_discovery_fff0_device_with_fridge_service_is_offered(
    hass, enable_bluetooth
) -> None:
    """A 0xFFF0 device that has the fridge characteristics is offered."""
    client = _gatt_client(True)
    result = await _discover(hass, _discovery([FFF0]), AsyncMock(return_value=client))
    assert result["type"] == "form"
    client.disconnect.assert_awaited_once()


async def test_discovery_fff0_device_without_fridge_service_is_ignored(
    hass, enable_bluetooth
) -> None:
    """Other 0xFFF0 gadgets are not offered as fridges."""
    client = _gatt_client(False)
    result = await _discover(hass, _discovery([FFF0]), AsyncMock(return_value=client))
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"
    client.disconnect.assert_awaited_once()


async def test_discovery_unreachable_device_is_still_offered(
    hass, enable_bluetooth
) -> None:
    """If the check cannot connect (e.g. phone app connected), offer it anyway."""
    from bleak.exc import BleakError

    result = await _discover(
        hass, _discovery([FFF0]), AsyncMock(side_effect=BleakError("busy"))
    )
    assert result["type"] == "form"


# --- Bind on start is an option -------------------------------------------


async def _connect_with(bind: bool) -> AsyncMock:
    from custom_components.alpicool_ble import api as api_module
    from test_api import _connected_client

    fridge = FridgeApi(MagicMock(), ADDRESS)
    client = _connected_client()
    send = AsyncMock()
    with (
        patch.object(
            api_module.bluetooth,
            "async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch.object(
            api_module, "establish_connection", AsyncMock(return_value=client)
        ),
        patch.object(fridge, "_send_raw", send),
        patch.object(
            api_module.asyncio,
            "wait_for",
            AsyncMock(side_effect=lambda coro, timeout: coro.close()),
        ),
    ):
        assert await fridge.connect(bind=bind) is True
    return send


async def test_bind_is_sent_by_default() -> None:
    """With the option on (default) the fridge is asked to pair."""
    send = await _connect_with(True)
    send.assert_awaited_once()
    assert send.await_args.args[0][3] == Request.BIND


async def test_bind_can_be_switched_off() -> None:
    """With the option off no Bind is sent and setup does not wait."""
    send = await _connect_with(False)
    send.assert_not_awaited()


async def test_user_flow_stores_bind_option(hass, enable_bluetooth) -> None:
    """The checkbox on the setup form ends up in the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"address": ADDRESS, "name": "Box", "bind_on_start": False},
    )
    assert result["type"] == "create_entry"
    assert result["data"]["bind_on_start"] is False
