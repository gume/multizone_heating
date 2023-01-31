"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, ServiceCall
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
        self._name = slugify(config[CONF_NAME])
        self._zonemaster = zm
        self._entities = []
        self._hass = zm.hass

        self._pumps = []
        self._pump_states = {}
        self._subzones = []
        self._subzone_states = {}
        self._heating = "unknown"

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._name, cp)
            self._pumps.append(pump.name)
            self._pump_states[pump.name] = (pump, "unknown")
            self._entities += pump.entities

        for csz in config[CONF_SUBZONES]:
            subzone = SubZone(self, self._name, csz)
            self._subzones.append(subzone.name)
            self._subzone_states[subzone.name] = (subzone, "unknown")
            self._entities += subzone.entities

    async def async_call(self, service: str, call: ServiceCall):
        _LOGGER.debug(f"async_call {self.name}")
        main_result = []
        for z in self._subzones:
            result = await z.async_call(service, call)
            if result is not False:
                main_result.append((z, result))
        return main_result

    async def async_subzone_change(self, subzone: SubZone, new_state: str):
        _LOGGER.debug(f"Subzone change {subzone}")
        change = False
        if subzone in self._subzones:
            sz, szs = self._subzone_states[subzone]
            if szs != new_state:
                change = True
            self._subzone_states[subzone] = (sz, new_state)
        else:
            _LOGGER.warning(f"Unknown subzone name! {subzone}")
        if not change:
            return
        
        self.hass.async_create_task(self.async_control_pumps())

    async def async_control_pumps(self, force = False):
        _LOGGER.debug(f"Pump control {force}, {self._heating}")
        any_on = False
        for szn, (sz, szs) in self._subzone_states.items():
            if szs == "on":
                any_on = True
                break
        
        if any_on:
            if not force and self._heating is "on":
                return
            self._heating = "on"
            _LOGGER.debug(f"Pump control to {self._heating}")
            for pn, (p, ps) in self._pump_states.items():
                _LOGGER.debug(f"Pump {pn} on {p}")
                await p.async_turn_on()
        else:
            if not force and self._heating is "off":
                return
            self._heating = "off"
            _LOGGER.debug(f"Pump control to {self._heating}")
            for pn, (p, ps) in self._pump_states.items():
                _LOGGER.debug(f"Pump {pn} off {p}")
                await p.async_turn_off()

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

    async def async_call(self, service: str, call: ServiceCall):
        _LOGGER.debug(f"async_call {self.name}")
        main_result = []
        for z in self._zones:
            result = await z.async_call(service, call)
            if result is not False:
                main_result.append((z, result))
        return main_result        

    async def async_control_pumps(self, force = False):
        pass

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
        _LOGGER.debug(f"Pump change {event.data}")
        self._state = (event.data.get("new_state").state == "on")
        self._attr_icon = "mdi:valve-open" if self._state else "mdi:valve-closed"
        self._attr_available = True
        self.async_write_ha_state()

        self.hass.async_create_task(self._zone.async_control_pumps(True))

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        _LOGGER.debug(f"switch turn_on entity_id: {self._pumpswitch}")
        await self.hass.services.async_call("switch", "turn_on", {"entity_id": self._pumpswitch})

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        _LOGGER.debug(f"switch turn_off entity_id: {self._pumpswitch}")
        await self.hass.services.async_call("switch", "turn_off", {"entity_id": self._pumpswitch})

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
