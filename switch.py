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
    _LOGGER.debug("switch: _async_setup_entry")
    zonemaster = hass.data[DOMAIN][config_entry.entry_id]
    switches = zonemaster.switches
    for zone in zonemaster.zones:
        switches += zone.switches
    async_add_entities(switches)
