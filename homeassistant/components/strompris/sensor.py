"""strompris sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from strompris.const import SOURCE_HVAKOSTERSTROMMEN
from strompris.schemas import Prising
from strompris.strompris import Strompris

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DOMAIN, PRICE_ZONE, PRICE_ZONES

_LOGGER = logging.getLogger(__name__)


def get_zone(selected_price_zone: str) -> int:
    """Return zone number from string."""
    return PRICE_ZONES.index(selected_price_zone) + 1


def uid_price_zone(pris_sone: str) -> str:
    """Return uid."""
    return f"{DOMAIN.lower()}_pris_sone_{pris_sone}"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Elvia Sensor."""

    sone = hass.data[PRICE_ZONE]
    entities = [StromPrisSensor(pris_sone_nummer=get_zone(sone), pris_sone=sone)]
    async_add_entities(entities, True)


class StromSensor(SensorEntity):
    """Base sensor."""

    _pris_sone_nummer: int
    _pris_sone: str
    _attr_has_entity_name = True
    _attr_extra_state_attributes: dict[str, Any]

    strompris: Strompris

    def __init__(self, pris_sone_nummer: int, pris_sone: str) -> None:
        """Class init."""
        self._pris_sone_nummer = pris_sone_nummer
        self._pris_sone = pris_sone
        super().__init__()
        self.strompris = Strompris(
            source=SOURCE_HVAKOSTERSTROMMEN, zone=pris_sone_nummer
        )


class StromPrisSensor(StromSensor):
    """Representation of a generic Strompris Sensor."""

    _price_end: datetime | None = None

    def __init__(self, pris_sone_nummer: int, pris_sone: str) -> None:
        """Class init."""
        super().__init__(pris_sone_nummer, pris_sone)
        self._last_updated = None
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_unique_id = uid_price_zone(pris_sone=pris_sone)
        self._attr_name = f"Electricity price - {pris_sone}"
        self._model = "Price Sensor"

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:cash"

    async def async_update(self) -> None:
        """Update sensor."""
        today = await self.strompris.async_get_prices_for_today()
        if not today or len(today) == 0:
            _LOGGER.error(
                "Could not obtain electricity pricing for today. Setting sensor available state to False"
            )
            self._attr_available = False
            return

        current: Prising = await self.strompris.async_get_current_price()
        if not current:
            _LOGGER.error(
                "Could not obtain current electricity pricing. Setting sensor available state to False"
            )
            self._attr_available = False
            return
        self._attr_available = True
        self._attr_native_value = round(current.total, 3)
        self._last_updated = current.start

        self._attr_extra_state_attributes.update(
            await self.strompris.async_get_current_price_attrs()
        )

        if self._price_end is None:
            self._price_end = today[-1].start

        today_price_attrs: dict[str, Any] = {
            "price_today": [
                round(x.total, 2) for x in today
            ],  # list(map(lambda value: round(value.total, 2), today)),
            "price_start": today[0].start.isoformat(),
            "price_end": self._price_end.isoformat(),
        }

        self._attr_extra_state_attributes.update(today_price_attrs)
        await self.async_fetch_prices_for_tomorrow_with_throttle()

    @Throttle(timedelta(minutes=5))
    async def async_fetch_prices_for_tomorrow_with_throttle(self) -> list[Prising]:
        """Fetch prices for tomorrow."""
        price_attrs: dict[str, Any]
        tomorrow = await self.strompris.async_get_prices_for_tomorrow()
        if tomorrow is None or len(tomorrow) == 0:
            print("Fikk ingen priser for i morgen..")
            _LOGGER.info("Priser for i morgen er ikke tilgjengelig enda")
            price_attrs = {
                "price_tomorrow": [],
            }
            self._attr_extra_state_attributes.update(price_attrs)
            return []
        self._price_end = tomorrow[-1].start
        iso_end: str
        if self._price_end is not None:
            iso_end = self._price_end.isoformat()
        price_attrs = {
            "price_tomorrow": [
                round(x.total, 2) for x in tomorrow
            ],  # list(map(lambda value: round(value.total, 2), tomorrow)),
            "price_end": iso_end,
        }
        self._attr_extra_state_attributes.update(price_attrs)
        return tomorrow
