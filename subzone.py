"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME, CONF_ENTITY_ID, DEVICE_CLASS_TEMPERATURE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import Entity


from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES, CONF_PUMPS, CONF_SUBZONES,
    CONF_MAIN,
)

_LOGGER = logging.getLogger(__name__)


class SubZone(SwitchEntity):

    def __init__(self, zone, config):
        self._attr_name = f"subzone_{config[CONF_NAME]}"
        self._attr_unique_id = slugify(f"{DOMAIN}_{zone.name}_{config[CONF_NAME]}")
        self._attr_icon = "mdi:radiator-disabled"
        self._attr_available = True
        self._state = "off"

        self._entities = [ self ]

        self._zone = zone
        self._hass = zone.hass

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        self._state = "on"
        self._attr_icon = "mdi:radiator"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        self._state = "off"
        self._attr_icon = "mdi:radiator-off"
        self.async_write_ha_state()

    @property
    def state(self):
        return self._state
    @property
    def entities(self):
        return self._entities
    @property
    def is_on(self):
        return self._state == "on"
    @property    
    def name(self):
        return self._attr_name
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._zone.name)},
            "name": self._zone.name,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }
