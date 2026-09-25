"""Sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaentumConfigEntry, MaentumCoordinator
from .entity import MaentumEntity
from .protocol import FridgeStatus

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MaentumSensorDescription(SensorEntityDescription):
    """Describe a sensor and how to read it."""

    value_fn: Callable[[FridgeStatus], float | int | None]
    temperature: bool = False


def _battery_percent(status: FridgeStatus) -> int | None:
    return status.battery_percent if status.battery_percent_known else None


ZONE1_TEMPERATURE = MaentumSensorDescription(
    key="zone1_temperature",
    translation_key="zone1_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda s: s.zone1.current_temperature,
    temperature=True,
)
ZONE2_TEMPERATURE = MaentumSensorDescription(
    key="zone2_temperature",
    translation_key="zone2_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda s: s.zone2.current_temperature if s.zone2 else None,
    temperature=True,
)
SENSORS: tuple[MaentumSensorDescription, ...] = (
    MaentumSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda s: s.battery_voltage,
    ),
    MaentumSensorDescription(
        key="battery_percent",
        translation_key="battery_percent",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_battery_percent,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaentumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors."""
    coordinator = entry.runtime_data
    descriptions = [ZONE1_TEMPERATURE, *SENSORS]
    if coordinator.data.is_dual_zone:
        descriptions.insert(1, ZONE2_TEMPERATURE)
    async_add_entities(MaentumSensor(coordinator, d) for d in descriptions)


class MaentumSensor(MaentumEntity, SensorEntity):
    """A value from the status."""

    entity_description: MaentumSensorDescription

    def __init__(
        self, coordinator: MaentumCoordinator, description: MaentumSensorDescription
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Follow the unit the box is set to for temperatures."""
        if self.entity_description.temperature:
            if self.coordinator.data.is_fahrenheit:
                return UnitOfTemperature.FAHRENHEIT
            return UnitOfTemperature.CELSIUS
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> float | int | None:
        """Return the value."""
        return self.entity_description.value_fn(self.coordinator.data)
