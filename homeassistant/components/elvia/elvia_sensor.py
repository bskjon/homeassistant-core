"""elvia sensors."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from .const import DOMAIN

# https://github.com/adafycheng/home-assistant-components/blob/main/dummy-garage/homeassistant/components/dummy_garage/sensor.py


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Elvia Sensor."""


class ElviaSensor(SensorEntity):
    """Base sensor class."""

    _attr_has_entity_name: bool = True


class ElviaMaxHoursSensor(SensorEntity):
    """Sensor for max hours."""

    _attr_has_entity_name: bool = True

    def __init__(self, name: str) -> None:
        """Class init. Default assignment."""
        self._name = name
        self._attr_name = name
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_native_value = 0.0  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
            "calculated_time": None,
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of sensor."""
        return super().unique_id

    def update(self) -> None:
        """Fetch new values for the sensor."""

        self._attr_native_value = 0.0  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
            "calculated_time": None,
        }


class ElviaEnergyFixedLink(NumberEntity):
    """Elvia Energy Fixed Link Cost.

    Will consist of Daytime and Nighttime + Weekend.
    """

    _attr_has_entity_name: bool = True

    def __init__(self, name: str) -> None:
        """Class init. Default assignment."""

        self._name = name
        self._attr_name = name
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "NOK"

    def set_native_value(self, value: float) -> None:
        """Set fixedlink cost (Fixed Link)."""
        self._attr_native_value = value
