"""Binary sensor platform for multizone_heating."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback, ) -> None:
    zonemaster = hass.data[DOMAIN][config_entry.entry_id]
    binary_sensors = [i for i in zonemaster.entities if isinstance(i, BinarySensorEntity)]
    #_LOGGER.info(f"Binary sensors: {binary_sensors}")
    async_add_entities(binary_sensors)
