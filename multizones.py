"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME, CONF_ENTITY_ID, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_POWER
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
    remove_platform_name,
)

from .subzone import SubZone


_LOGGER = logging.getLogger(__name__)


class Zone:

    def __init__(self, zm: ZoneMaster, config: dict) -> None:
        """Init dummy hub."""
        self._name = config[CONF_NAME]
        self._zonemaster = zm
        self._entities = []
        self._hass = zm.hass

        self._pumps = []
        self._subzones = []

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._name, cp)
            self._pumps.append(pump)
            self._entities += pump.entities

        for csz in config[CONF_SUBZONES]:
            subzone = SubZone(self, self._name, csz)
            self._subzones.append(subzone)
            self._entities += subzone.entities

    @property
    def name(self):
        return self._name
    @property
    def entities(self) ->dict:
        return self._entities
    @property
    def hass(self) ->HomeAssistant:
        return self._hass


class ZoneMaster:

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        
        self._entities = []
        self._name = CONF_MAIN

        self._zones = []
        self._pumps = []
        self._hass = hass

        for cz in config[CONF_ZONES]:
            zone = Zone(self, cz)
            self._zones.append(zone)
            self._entities += zone.entities

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._name, cp)
            self._pumps.append(pump)
            self._entities += pump.entities

    @property
    def name(self):
        return self._name
    @property
    def entities(self) ->dict:
        return self._entities
    @property
    def hass(self) ->HomeAssistant:
        return self._hass


class Pump(BinarySensorEntity): 
    """ Pump controls the heating, either for a zone or for all the zones """
    """ There is a binary sensor to visualize the state of the sensor """

    def __init__(self, zone, device_name, config):
        self._pumpswitch = config[CONF_ENTITY_ID]
        #self._pumpswitch = self._pumpswitch[7:] if self._pumpswitch.startswith("switch.") else self._pumpswitch
        self._attr_name = f"{zone.name}_{remove_platform_name(self._pumpswitch)}"
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        self._attr_icon = "mdi:valve"
        self._attr_available = False
        self._device_class = DEVICE_CLASS_POWER

        self._entities = [ self ]
        self._zone = zone
        self._state = False

        self.hass = zone.hass

        self._listen = async_track_state_change_event(self.hass, [self._pumpswitch], self.async_pumpswitch_state_change_event)

    async def async_pumpswitch_state_change_event(self, event):
        self._state = (event.data.get("new_state").state == "on")
        self._attr_icon = "mdi:valve-open" if self._state else "mdi:valve-closed"
        self._attr_available = True
        self.async_write_ha_state()

    @property
    def entities(self):
        return self._entities
    @property
    def name(self):
        return self._attr_name
    @property
    def is_on(self):
        return self._state
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_name)},
            "name": self._zone.name,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }
