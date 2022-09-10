"""The elvia integration."""
from __future__ import annotations

import asyncio

# from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, TOKEN
from .elvia import Elvia

PLATFORMS: list[Platform] = [Platform.SENSOR]


# pylint: disable=fixme
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up elvia from a config entry."""

    elvia = Elvia(entry.data[TOKEN])
    hass.data[DOMAIN] = elvia

    try:
        await elvia.update_meters()
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady from err

    # IF NEEDED: entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


# https://dev.to/adafycheng/write-custom-component-for-home-assistant-4fce
