"""elvia sensors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

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
from .elvia_schema import MaxHours, maxHour, maxHourAggregate, meteringPointV2

_LOGGER = logging.getLogger(__name__)

datetime_format: str = "%Y-%m-%dT%H:%M:%S%z"


# https://github.com/adafycheng/home-assistant-components/blob/main/dummy-garage/homeassistant/components/dummy_garage/sensor.py


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Elvia Sensor."""
    elvia: Elvia = hass.data[DOMAIN]

    # device_registry = async_get_dev_reg(hass)
    entities: list[ElviaSensor] = []

    entities.append(ElviaEnergyFixedLinkSensor(elvia, "Grid Cost Period"))

    entities.extend(
        await async_create_max_hours(
            hass=hass, entry=entry, async_add_entities=async_add_entities, elvia=elvia
        )
    )

    async_add_entities(entities, True)


async def async_create_max_hours(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    elvia: Elvia,
) -> list[ElviaSensor]:
    """Return configured Elvia Max Hour entities."""
    entities: list[ElviaSensor] = []

    setup_data = await elvia.get_max_hours()
    max_hours_data = setup_data.data
    maxhours: MaxHours
    if isinstance(max_hours_data, MaxHours):
        maxhours = max_hours_data
        for meter in maxhours.meteringpoints:
            meter_id = meter.meteringPointId
            entities.append(ElviaMaxHourFixedLevelSensor(elvia, "Max Hours", meter_id))
            entities.append(ElviaFixedGridLevelSensor(elvia, "Grid Level", meter_id))
            if len(meter.maxHoursAggregate) > 0:
                max_hours_current: maxHourAggregate = meter.maxHoursAggregate[0]
                for peak_max in max_hours_current.maxHours:
                    peak_max_index = max_hours_current.maxHours.index(peak_max)
                    entities.append(
                        ElviaMaxHourPeakSensor(
                            elvia,
                            "Max Hour " + str(peak_max_index),
                            meter_id,
                            peak_max_index,
                        )
                    )
    return entities


class ElviaSensor(SensorEntity):
    """Base sensor class."""

    _attr_has_entity_name: bool = True
    elvia_instance: Elvia

    def __init__(self, elvia_instance: Elvia) -> None:
        """Class init."""
        self.elvia_instance = elvia_instance
        self._attr_extra_state_attributes = {}


class ElviaMeterSensor(ElviaSensor):
    """Base meter sensor class."""

    _meter_id: str

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init."""
        super().__init__(elvia_instance)
        self._meter_id = meter_id
        self._attr_name = f"Elvia Meter {meter_id} {name}"
        self._attr_unique_id = f"elvia_meter_{meter_id}_{name}"

    def get_meter_id(self) -> str | None:
        """Return meter id."""
        return (
            self._meter_id
            if self._meter_id is not None
            else self.meter_id_from_unique_id()
        )

    def meter_id_from_unique_id(self) -> str | None:
        """Obtain meter id from unique id."""
        if self.unique_id is None:
            return None
        uid = self.unique_id.split("_")[2]
        return uid

    def get_attr_end_time(self) -> str | None:
        """Return end_time value from attribute or None."""
        return (
            self._attr_extra_state_attributes["end_time"]
            if (
                self._attr_extra_state_attributes is not None
                and "end_time" in self._attr_extra_state_attributes
            )
            else None
        )

    def can_pull_new_data(self) -> bool:
        """Check wenether the sensor is allowed to pull new data.

        If data_ref is None, pull will be allowed
        """
        now = dt_util.now()
        end_time = self.get_attr_end_time()

        dts: datetime = (
            datetime.strptime(end_time, datetime_format)
            if end_time is not None
            else datetime.now(timezone.utc).replace(
                day=1, month=1, year=1970, hour=0, minute=0, second=1, microsecond=0
            )
        )

        allow_new_pull: datetime = dts + timedelta(hours=1)
        return now >= allow_new_pull


class ElviaValueSensor(ElviaSensor):
    """Base value sensor class."""

    def __init__(self, elvia_instance: Elvia, name: str) -> None:
        """Class init. Default assignment."""
        super().__init__(elvia_instance)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_name = name = f"Elvia {name}"
        self._attr_unique_id = f"elvia_{name}"

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:cash"


class ElviaFixedGridLevelSensor(ElviaMeterSensor):
    """Sensor for grid level.

    Displays the current monthly fixed grid level.
    The fixed grid level resets every start of the month, but will only increase depending om Max Hours calculated.
    """

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init. Default assignment."""

        super().__init__(elvia_instance, name=name, meter_id=meter_id)
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "Level"
        self._attr_native_value = 0

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""

        max_hours: meteringPointV2 | None
        max_hours_current: maxHourAggregate | None

        if self.can_pull_new_data() or self.elvia_instance.max_hours is None:
            _LOGGER.debug("Asking for new data")
            _meter_id = self.meter_id_from_unique_id()
            if _meter_id is None:
                return
            await self.elvia_instance.update_max_hours()
            max_hours = self.elvia_instance.extract_max_hours(
                meter_id=_meter_id,
                mtrpoints=self.elvia_instance.max_hours.meteringpoints,
            )
            if max_hours is None:
                return
            max_hours_current = self.elvia_instance.extract_max_hours_current(max_hours)
            if max_hours_current is None:
                return
        else:
            return

        self._attr_native_value = self.elvia_instance.get_grid_level(
            max_hours_current.averageValue
        )  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": max_hours.maxHoursFromTime,
            "end_time": max_hours.maxHoursToTime,
            "calculated_time": max_hours.maxHoursCalculatedTime,
        }

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:trending-up"


class ElviaMaxHourFixedLevelSensor(ElviaMeterSensor):
    """Sensor for max hours."""

    def __init__(self, elvia_instance: Elvia, name: str, meter_id: str) -> None:
        """Class init. Default assignment."""
        super().__init__(elvia_instance, name=name, meter_id=meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_native_value = 0.0  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
            "calculated_time": None,
            "grid_level": None,
        }

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""

        max_hours: meteringPointV2 | None
        max_hours_current: maxHourAggregate | None

        if self.can_pull_new_data() or self.elvia_instance.max_hours:
            _LOGGER.debug("Asking for new data")
            _meter_id = self.meter_id_from_unique_id()
            if _meter_id is None:
                return
            await self.elvia_instance.update_max_hours()
            max_hours = self.elvia_instance.extract_max_hours(
                meter_id=_meter_id,
                mtrpoints=self.elvia_instance.max_hours.meteringpoints,
            )
            if max_hours is None:
                return
            max_hours_current = self.elvia_instance.extract_max_hours_current(max_hours)
            if max_hours_current is None:
                return
        else:
            return

        self._attr_native_value = round(
            max_hours_current.averageValue, 2
        )  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": max_hours.maxHoursFromTime,
            "end_time": max_hours.maxHoursToTime,
            "calculated_time": max_hours.maxHoursCalculatedTime,
        }

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:transmission-tower"


class ElviaMaxHourPeakSensor(ElviaMeterSensor):
    """Sensor for max hours."""

    peak_index: int

    def __init__(
        self, elvia_instance: Elvia, name: str, meter_id: str, peak_index: int = 0
    ) -> None:
        """Class init. Default assignment."""

        self.peak_index = peak_index
        super().__init__(elvia_instance, name=name, meter_id=meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_native_value = 0.0  # Nettleie nivå her
        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
        }

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""
        max_hours: meteringPointV2 | None
        peak_hour: maxHour

        if self.can_pull_new_data() or self.elvia_instance.max_hours is None:
            _LOGGER.debug("Asking for new data")
            _meter_id = self.meter_id_from_unique_id()
            if _meter_id is None:
                return
            await self.elvia_instance.update_max_hours()
            max_hours = self.elvia_instance.extract_max_hours(
                meter_id=_meter_id,
                mtrpoints=self.elvia_instance.max_hours.meteringpoints,
            )
            if max_hours is None:
                return
            max_hours_current: maxHourAggregate | None = (
                self.elvia_instance.extract_max_hours_current(max_hours)
            )
            if (
                max_hours_current is None
                or len(max_hours_current.maxHours) < self.peak_index
            ):
                return
            peak_hour = max_hours_current.maxHours[self.peak_index]

        else:
            return

        self._attr_native_value = round(peak_hour.value, 2)
        self._attr_extra_state_attributes = {
            "start_time": max_hours.maxHoursFromTime,
            "end_time": max_hours.maxHoursToTime,
        }

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:meter-electric"


class ElviaEnergyFixedLinkSensor(ElviaValueSensor):
    """Sensor for current fixed link cost."""

    def __init__(self, elvia_instance: Elvia, name: str) -> None:
        """Class init. Default assignment."""
        super().__init__(elvia_instance, name)

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
        period = self.elvia_instance.get_cost_period_now(now=dt_util.now())
        if period is None:
            return

        self._attr_native_value = period.cost

        periods = self.elvia_instance.get_cost_periods()
        day_period: CostTimeSpan = periods["day"]
        night_period: CostTimeSpan = periods["night"]
        weekend_period: CostTimeSpan = periods["weekend"]

        self._attr_extra_state_attributes = {
            "friendly_name": "Grid cost period",
            "currency": "NOK",
            "now_period": f"{period.start_time} - {period.end_time}",
            "day_period": f"{day_period.start_time} - {day_period.end_time}",
            "day_cost": day_period.cost,
            "night_period": f"{night_period.start_time} - {night_period.end_time}",
            "night_cost": night_period.cost,
            "weekend_period": f"{weekend_period.start_time} - {weekend_period.end_time}",
            "weekend_cost": weekend_period.cost,
        }

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:cash"
