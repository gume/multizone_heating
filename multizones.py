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

        self._pump_names = []
        self._pump_states = {}
        self._subzone_names = []
        self._subzone_states = {}
        
        self._heating = "unknown"

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._name, cp)
            self._pump_names.append(pump.name)
            self._pump_states[pump.name] = (pump, "unknown")
            self._entities += pump.entities

        for csz in config[CONF_SUBZONES]:
            subzone = SubZone(self, self._name, csz)
            self._subzone_names.append(subzone.name)
            self._subzone_states[subzone.name] = (subzone, "unknown")
            self._entities += subzone.entities

    async def async_call(self, service: str, call: ServiceCall):
        _LOGGER.debug(f"async_call {self.name}")
        main_result = []
        for z, zs in self._subzone_states.items():
            result = await z.async_call(service, call)
            if result is not False:
                main_result.append((z, result))
        return main_result

    async def async_parent_notify(self):
        _LOGGER.debug(f"{self.name}: Parent notify")
        """ Tell the parent about the cahnge (SubZone->Zone, Zone->ZoneMaster) """
        await self._zonemaster.async_subzone_change(self.name, self._heating)

    async def async_pump_change(self, pump_name: str, new_state: str):
        _LOGGER.debug(f"{self.name}: Pump change {pump_name} to {new_state}")

        """ Store the new state of the pump """
        change = False
        if pump_name in self._pump_names:
            p, ps = self._pump_states[pump_name]
            if ps != new_state:
                change = True
            self._pump_states[pump_name] = (p, new_state)
        else:
            _LOGGER.warning(f"{self.name}: Unknown pump name! {pump_name}")
            _LOGGER.warning(f"Available names: {self._pump_names}")
        if not change:
            return

        """ Perform a pump control, due to the change """
        self.hass.async_create_task(self.async_control_pumps())

    async def async_subzone_change(self, subzone_name: str, new_state: str):
        _LOGGER.debug(f"{self.name}: Subzone change {subzone_name} to {new_state}")
        
        """ Stored the new state of the subzone """
        change = False
        if subzone_name in self._subzone_names:
            sz, szs = self._subzone_states[subzone_name]
            if szs != new_state:
                change = True
            self._subzone_states[subzone_name] = (sz, new_state)
        else:
            _LOGGER.warning(f"{self.name}: Unknown subzone name! {subzone_name}")
            _LOGGER.warning(f"Available names: {self._subzone_names}")
        if not change:
            return
        
        """ Calculate new state of the actual zone """
        any_on = "off"
        for szn, (sz, szs) in self._subzone_states.items():
            if szs == "on":
                any_on = "on"
                break
        _LOGGER.debug(f"{self.name}: Calculated any on {any_on}")

        """ in case of change, notify parent and schedule a pump control """
        if any_on != self._heating:
            _LOGGER.debug(f"{self.name}: Change heating to {any_on}")
            self._heating = any_on
            await self.async_parent_notify()
            self.hass.async_create_task(self.async_control_pumps())

    async def async_control_pumps(self, force = False):
        _LOGGER.debug(f"{self.name} Pump control {force}, {self._heating}")
        
        """ Heating should be on or off to change """
        if self._heating != "on" and self._heating != "off":
            return

        _LOGGER.debug(f"{self.name} Pump control to {self._heating}")
        for pn, (p, ps) in self._pump_states.items():
            if ps == self._heating and not force:
                continue
            _LOGGER.debug(f"Pump {pn} on {p}")
            self._pump_states[pn] = (p, self._heating)
            if self._heating == "on":
                await p.async_turn_on()
            if self._heating == "off":
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


class ZoneMaster(Zone):

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        
        self._entities = []
        self._name = CONF_MAIN

        self._subzone_names = []
        self._subzone_states = {}
        self._pump_names = []
        self._pump_states = {}

        self._hass = hass

        self._heating = "unknown"

        for cz in config[CONF_ZONES]:
            zone = Zone(self, cz)
            self._subzone_names.append(zone.name)
            self._subzone_states[zone.name] = (zone, "unknown")
            self._entities += zone.entities

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._name, cp)
            self._pump_names.append(pump.name)
            self._pump_states[pump.name] = (pump, "unknown")
            self._entities += pump.entities

    #@override
    async def async_parent_notify(self):
        _LOGGER.debug(f"{self.name}: Parent notify (override)")
        """ Tell the parent about the cahnge (SubZone->Zone, Zone->ZoneMaster) """
        pass

    """
    @property
    def name(self):
        return self._name
    @property
    def entities(self) ->dict:
        return self._entities
    @property
    def hass(self) ->HomeAssistant:
        return self._hass
    """

class Pump(BinarySensorEntity): 
    """ Pump controls the heating, either for a zone or for all the zones """
    """ There is a binary sensor to visualize the state of the sensor """

    def __init__(self, zone, device_name, config):
        self._pumpswitch = config[CONF_ENTITY_ID]
        #self._pumpswitch = self._pumpswitch[7:] if self._pumpswitch.startswith("switch.") else self._pumpswitch
        self._attr_name = slugify(f"{zone.name}_{remove_platform_name(self._pumpswitch)}")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        self._attr_icon = "mdi:valve"
        self._attr_available = False
        self._device_class = DEVICE_CLASS_POWER

        self._entities = [ self ]
        self._zone = zone
        self._state = "unknown"

        self.hass = zone.hass

        self._listen = async_track_state_change_event(self.hass, [self._pumpswitch], self.async_pumpswitch_state_change_event)

    async def async_pumpswitch_state_change_event(self, event):
        _LOGGER.debug(f"Pump change {event.data}")
        self._state = event.data.get("new_state").state
        self._attr_icon = "mdi:valve-open" if self._state == "on" else "mdi:valve-closed"
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
