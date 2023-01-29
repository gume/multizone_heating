"""Switch platform for multizone_heating."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback, ) -> None:
    zonemaster = hass.data[DOMAIN][config_entry.entry_id]
    sensors = zonemaster.sensors
    for zone in zonemaster.zones:
        sensors += zone.sensors
    async_add_entities(sensors)
