"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity


from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES,
)

_LOGGER = logging.getLogger(__name__)


class Zone:

    def __init__(self, zm: ZoneMaster, config: dict) -> None:
        """Init dummy hub."""
        self._name = config[CONF_NAME]
        self._zonemaster = zm
        self._switches = []
        self._sensors = []

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

    async def async_test(self):
        _LOGGER.debug(f"async_test at {self.name}")

class ZoneMaster:

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        
        self._switches = []
        self._sensors = []
        self._zones = []

        for cz in config[CONF_ZONES]:
            zone = Zone(self, cz)
            self._zones.append(zone)

    def add(self, zone: Zone) -> None:
        self.zones.append(zone)

    @property
    def zones(self) ->dict:
        return self._zones
    @property
    def switches(self) ->dict:
        return self._switches
    @property
    def sensors(self) ->dict:
        return self._sensors

class ZoneSwitch(SwitchEntity):

    def __init__(self, name, zonename):
        _LOGGER.debug(f"Init ZoneSwitch {zonename}-{name}")
        self._attr_name = name
        self._attr_unique_id = slugify(f"{DOMAIN}_{zonename}_{name}")
        self.zonename = zonename
#        self._attr_device_info = DeviceInfo({"identifiers": ({DOMAIN, zonename}), "name": NAME, "model": VERSION, "manufacturer": MANUFACTURER })

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        pass

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        pass

    @property
    def name(self):
        """Return the name of the switch."""
        return self._attr_name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.zonename)},
            "name": self.zonename,
            "model": "Zone controller",
            "manufacturer": MANUFACTURER,
        }
