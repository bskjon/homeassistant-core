"""elvia sensors."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

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
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .elvia import CostTimeSpan, Elvia
from .elvia_schema import MaxHours, maxHourAggregate, meteringPointV2

_LOGGER = logging.getLogger(__name__)


# https://github.com/adafycheng/home-assistant-components/blob/main/dummy-garage/homeassistant/components/dummy_garage/sensor.py


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Elvia Sensor."""
    elvia: Elvia = hass.data[DOMAIN]

    cost_periods = elvia.get_cost_periods()
    price_entities: list[NumberEntity] = [
        ElviaEnergyFixedLinkCost("day", cost_periods["day"]),
        ElviaEnergyFixedLinkCost("night", cost_periods["night"]),
        ElviaEnergyFixedLinkCost("weekend", cost_periods["weekend"]),
    ]
    async_add_entities(price_entities, True)

    # device_registry = async_get_dev_reg(hass)
    entities: list[ElviaSensor] = []

    max_hours_data = asyncio.run(elvia.get_max_hours()).data
    maxhours: MaxHours
    if isinstance(max_hours_data, MaxHours):
        maxhours = max_hours_data
        for meter in maxhours.meteringpoints:
            meter_id = meter.meteringPointId
            entities.append(ElviaMaxHourFixedLevelSensor(elvia, "maxHours", meter_id))
            if len(meter.maxHoursAggregate) > 0:
                max_hours_current: maxHourAggregate = meter.maxHoursAggregate[0]
                for peak_max in max_hours_current.maxHours:
                    peak_max_index = max_hours_current.maxHours.index(peak_max)
                    entities.append(
                        ElviaMaxHourPeakSensor(
                            elvia, "maxHour_" + str(peak_max_index), meter_id
                        )
                    )
                entities.append(
                    ElviaEnergyFixedLinkSensor(elvia, "costPeriod", meter_id)
                )

    async_add_entities(entities, True)


class ElviaSensor(SensorEntity):
    """Base sensor class."""

    _attr_has_entity_name: bool = True
    elvia_instance: Elvia

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init."""
        self.elvia_instance = elvia_instance
        self._name = "elvia_" + meter_id + "_" + name
        self._attr_name = self.name
        self._attr_unique_id = meter_id


class ElviaMaxHourFixedLevelSensor(ElviaSensor):
    """Sensor for max hours."""

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init. Default assignment."""
        super().__init__(elvia_instance, name, meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_native_value = 0.0  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
            "calculated_time": None,
        }

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""

        now = dt_util.now()
        dts: datetime = self._attr_extra_state_attributes["end_time"]
        allow_new_pull: datetime = dts + timedelta(hours=1)
        max_hours: meteringPointV2
        max_hours_current: maxHourAggregate

        if now > allow_new_pull or self.elvia_instance.max_hours is None:
            _LOGGER.debug("Asking for new data")
            await self.elvia_instance.update_max_hours()
            max_from_meters = self.elvia_instance.max_hours.meteringpoints
            max_hours_data = next(
                (
                    meter_max
                    for meter_max in max_from_meters
                    if meter_max.meteringPointId == self.unique_id
                ),
                None,
            )
            if max_hours_data is not None and len(max_hours_data.maxHoursAggregate):
                max_hours = max_hours_data
                max_hours_current = max_hours.maxHoursAggregate[0]
            else:
                return

        else:
            return

        self._attr_native_value = max_hours_current.averageValue  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": max_hours.maxHoursFromTime,
            "end_time": max_hours.maxHoursToTime,
            "calculated_time": max_hours.maxHoursCalculatedTime,
            "grid_level": self.elvia_instance.get_grid_level(
                max_hours_current.averageValue
            ),
        }


class ElviaMaxHourPeakSensor(ElviaSensor):
    """Sensor for max hours."""

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init. Default assignment."""
        super().__init__(elvia_instance, name, meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_native_value = 0.0  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
            "calculated_time": None,
        }

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""

        now = dt_util.now()
        dts: datetime = self._attr_extra_state_attributes["end_time"]
        allow_new_pull: datetime = dts + timedelta(hours=1)
        max_hours: meteringPointV2
        max_hours_current: maxHourAggregate

        if now > allow_new_pull or self.elvia_instance.max_hours is None:
            _LOGGER.debug("Asking for new data")
            await self.elvia_instance.update_max_hours()
            max_from_meters = self.elvia_instance.max_hours.meteringpoints
            max_hours_found = next(
                (
                    meter_max
                    for meter_max in max_from_meters
                    if meter_max.meteringPointId == self.unique_id
                ),
                None,
            )
            if max_hours_found is None:
                return
            max_hours = max_hours_found
            max_hours_current = max_hours.maxHoursAggregate[0]

        else:
            return

        self._attr_native_value = max_hours_current.averageValue  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": max_hours.maxHoursFromTime,
            "end_time": max_hours.maxHoursToTime,
            "calculated_time": max_hours.maxHoursCalculatedTime,
            "grid_level": self.elvia_instance.get_grid_level(
                max_hours_current.averageValue
            ),
        }


class ElviaEnergyFixedLinkSensor(ElviaSensor):
    """Sensor for current fixed link cost."""

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init. Default assignment."""
        super().__init__(elvia_instance, name, meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "NOK"

        self._attr_native_value = 0.0
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
        }

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""
        period = self.elvia_instance.get_cost_period_now()

        self._attr_native_value = period.cost
        self._attr_extra_state_attributes = {
            "start_time": period.start_time,
            "end_time": period.end_time,
        }


class ElviaEnergyFixedLinkCost(NumberEntity):
    """Elvia Energy Fixed Link Cost.

    Will consist of Daytime and Nighttime + Weekend.
    """

    _attr_has_entity_name: bool = True

    def __init__(self, name: str, value: CostTimeSpan) -> None:
        """Class init. Default assignment."""

        self._name = name
        self._attr_name = name
        self._attr_device_class = SensorDeviceClass.MONETARY

        self._attr_native_unit_of_measurement = "NOK"
        self._attr_extra_state_attributes = {
            "start_time": value.start_time,
            "end_time": value.end_time,
        }
        self.set_native_value(value=value.cost)

    def set_native_value(self, value: float) -> None:
        """Set fixedlink cost (Fixed Link)."""
        self._attr_native_value = value
