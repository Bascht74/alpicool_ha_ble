"""Climate entities, one per cooling zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MaentumConfigEntry, MaentumCoordinator
from .entity import MaentumEntity
from .protocol import RunMode, ZoneStatus

PARALLEL_UPDATES = 1

PRESET_MAX = "max"
PRESET_ECO = "eco"
_PRESET_TO_MODE = {PRESET_MAX: RunMode.MAX, PRESET_ECO: RunMode.ECO}
_MODE_TO_PRESET = {mode: preset for preset, mode in _PRESET_TO_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaentumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one climate entity per zone the box reports."""
    coordinator = entry.runtime_data
    zones = [1, 2] if coordinator.data.is_dual_zone else [1]
    async_add_entities(MaentumClimate(coordinator, zone, len(zones) > 1) for zone in zones)


class MaentumClimate(MaentumEntity, ClimateEntity):
    """Target temperature, power and run mode of one zone.

    Power and run mode are global settings of the box; in a dual-zone box both
    climate entities show and change the same values.
    """

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_preset_modes = [PRESET_MAX, PRESET_ECO]
    _attr_target_temperature_step = 1
    _attr_precision = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MaentumCoordinator, zone: int, dual: bool) -> None:
        """Initialise the entity."""
        super().__init__(coordinator, f"zone{zone}_climate")
        self._zone = zone
        if dual:
            self._attr_translation_key = f"zone{zone}"
        else:
            self._attr_translation_key = "fridge"
            self._attr_name = None

    @property
    def _zone_status(self) -> ZoneStatus | None:
        status = self.coordinator.data
        return status.zone1 if self._zone == 1 else status.zone2

    @property
    def available(self) -> bool:
        """Return False when the zone is missing from the last status."""
        return super().available and self._zone_status is not None

    @property
    def temperature_unit(self) -> str:
        """Return the unit the box is set to."""
        if self.coordinator.data.is_fahrenheit:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the measured temperature."""
        zone = self._zone_status
        return zone.current_temperature if zone else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        zone = self._zone_status
        return zone.target_temperature if zone else None

    @property
    def min_temp(self) -> float:
        """Return the lowest target the box accepts."""
        return self.coordinator.data.temp_min

    @property
    def max_temp(self) -> float:
        """Return the highest target the box accepts."""
        return self.coordinator.data.temp_max

    @property
    def hvac_mode(self) -> HVACMode:
        """Return cool while the box is switched on."""
        return HVACMode.COOL if self.coordinator.data.powered_on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return off or idle.

        The status does not reliably say whether the compressor is running
        (the meaning of the running status byte is not documented), so the
        entity never claims "cooling".
        """
        return HVACAction.IDLE if self.coordinator.data.powered_on else HVACAction.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return max or eco."""
        return _MODE_TO_PRESET.get(self.coordinator.data.run_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, and optionally the hvac mode."""
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        value = round(temperature)
        if not self.min_temp <= value <= self.max_temp:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temperature_out_of_range",
                translation_placeholders={
                    "value": str(value),
                    "min": str(self.min_temp),
                    "max": str(self.max_temp),
                },
            )
        client = self.coordinator.client
        await self.coordinator.async_command(
            lambda _status: client.async_set_target(self._zone, value)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch the box on or off."""
        powered_on = hvac_mode == HVACMode.COOL
        if powered_on == self.coordinator.data.powered_on:
            return
        client = self.coordinator.client
        await self.coordinator.async_command(
            lambda status: client.async_set(status, powered_on=powered_on)
        )

    async def async_turn_on(self) -> None:
        """Switch the box on."""
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Switch the box off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Switch between max and eco."""
        client = self.coordinator.client
        mode = _PRESET_TO_MODE[preset_mode]
        await self.coordinator.async_command(lambda status: client.async_set(status, run_mode=mode))
