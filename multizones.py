"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME, CONF_ENTITY_ID
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import Entity


from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES, CONF_PUMPS,
    CONF_MAIN,
)

BINARY_SENSOR_DEVICE_CLASS = "power"


_LOGGER = logging.getLogger(__name__)


class Zone:

    def __init__(self, zm: ZoneMaster, config: dict) -> None:
        """Init dummy hub."""
        self._name = config[CONF_NAME]
        self._zonemaster = zm
        self._switches = []
        self._sensors = []
        self._binary_sensors = []
        self._hass = zm.hass

        self._pumps = []

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._name, cp)
            self._pumps.append(pump)
            self._binary_sensors.append(pump)

        self._switches.append(ZoneSwitch("test1", self._name))
        self._switches.append(ZoneSwitch("test2", self._name))

    @property
    def name(self):
        return self._name
    @property
    def switches(self) ->dict:
        return self._switches
    @property
    def sensors(self) ->dict:
        return self._sensors
    @property
    def binary_sensors(self) ->dict:
        return self._binary_sensors
    @property
    def hass(self) ->HomeAssistant:
        return self._hass


class ZoneMaster:

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        
        self._switches = []
        self._sensors = []
        self._binary_sensors = []

        self._zones = []
        self._pumps = []
        self._hass = hass

        for cz in config[CONF_ZONES]:
            zone = Zone(self, cz)
            self._zones.append(zone)

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, CONF_MAIN, cp)
            self._pumps.append(pump)
            self._binary_sensors.append(pump)        

    @property
    def zones(self) ->dict:
        return self._zones
    @property
    def switches(self) ->dict:
        return self._switches
    @property
    def sensors(self) ->dict:
        return self._sensors
    @property
    def binary_sensors(self) ->dict:
        return self._binary_sensors
    @property
    def hass(self) ->HomeAssistant:
        return self._hass


class Pump(BinarySensorEntity): 
    """ Pump controls the heating, either for a zone or for all the zones """
    """ There is a binary sensor to visualize the state of the sensor """

    def __init__(self, zone, zonename, config):
        self._pumpswitch = config[CONF_ENTITY_ID]
        self._pumpswitch = self._pumpswitch[7:] if self._pumpswitch.startswith("switch.") else self._pumpswitch
        self._attr_name = f"{self._pumpswitch}"
        self._attr_unique_id = slugify(f"{DOMAIN}_{zonename}_{self._pumpswitch}")
        self._attr_icon = "mdi:valve"
        self._attr_available = False

        self._zone = zone
        self._zonename = zonename
        self._state = False

        self.hass = zone.hass

        self._listen = async_track_state_change_event(self.hass, [config[CONF_ENTITY_ID]], self.async_pumpswitch_state_change)

    async def async_pumpswitch_state_change(self, event):
        _LOGGER.debug(event.data)
        self._state = (event.data.get("new_state").state == "on")
        self._attr_icon = "mdi:valve-open" if self._state else "mdi:valve-closed"
        self._attr_available = True
        _LOGGER.debug(self._state)
        self.async_write_ha_state()

    @property
    def name(self):
        return self._attr_name
    @property
    def device_class(self):
        return BINARY_SENSOR_DEVICE_CLASS
    @property
    def is_on(self):
        return self._state
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._zonename)},
            "name": self._zonename,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }


class ZoneSwitch(SwitchEntity):

    def __init__(self, name, zonename):
        self._attr_name = name
        self._attr_unique_id = slugify(f"{DOMAIN}_{zonename}_{name}")
        self._zonename = zonename
#        self._attr_device_info = DeviceInfo({"identifiers": ({DOMAIN, zonename}), "name": NAME, "model": VERSION, "manufacturer": MANUFACTURER })

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        pass

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        pass

    @property
    def name(self):
        return self._attr_name
    @property
    def is_on(self):
        """Return true if the switch is on."""
        return True
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._zonename)},
            "name": self._zonename,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }
