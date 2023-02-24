"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging
import datetime

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID,
    STATE_UNKNOWN, STATE_ON, STATE_OFF,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate.const import SERVICE_SET_PRESET_MODE, ATTR_PRESET_MODE
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util


from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES, CONF_PUMPS, CONF_SUBZONES, CONF_ENABLED, CONF_SENSOR, CONF_VALVES, CONF_BOOST_TIME, 
    CONF_MAIN,
    PRESET_DEFAULTS,
)

from .things import Pump, Valve, TemperatureSensor, SubZoneSwitch, SubZoneBoostSwitch


_LOGGER = logging.getLogger(__name__)


class BaseZone(BinarySensorEntity):

    def __init__(self, hass: HomeAssistant, parent, config: dict, name: str) -> None:

        self._entities = []     # Entity names that should be added to hass
        self._sensors = {}      # sensors, eg. temperature sensor. Key: name, item: (sensor object, state)
        self._actuators = {}    # actuators, eg. pump. Key: name, item: (sensor object, state)
        self._subzones = {}     # ZoneMaster -> Zone -> SubZone
        self._presets = {}      # Store temperature settings

        self._enabled = False   # When diabled, no actuators are operated
        self._last_change = dt_util.utcnow() # Last state change time

        self._parent = parent # define parent property as well
        self._attr_name = slugify(name) # name property will work from Entity
        self._attr_unique_id = slugify(f"{DOMAIN}_{name}") # unique_id property will work from Entity
        self._attr_should_poll = False
        self._attr_device_class = BinarySensorDeviceClass.HEAT

        """ State is for heating on/off """
        self._attr_is_on = False # The state of the heating

        self.hass = hass # Non registered entities would not have this

        self._entities.append(self)
        self._zonename = name     # Name of the zone

        """ read config presets """
        """ If there is no entry in the config, then use the parent's config """
        for cp in PRESET_DEFAULTS.keys():
            if cp in config:
                """ Try to read from the config file (Now it is just for floats)"""
                try:
                    self._presets[cp] = float(config[cp])
                except:
                    _LOGGER.warn(f"{self.name} Wrong config for preset {cp}: {config[cp]}")
            else:
                """ If there is no entry in the config file, maybe the parent already has this value """
                if self.parent is not None and cp in self.parent.presets:
                    self._presets[cp] = self.parent.presets[cp]

    """ Service call. Should be passed to the zonemaster, but dispatched this way """
    """ It should return a list of nodes, who answered the call """
    async def async_call(self, service: str, call: ServiceCall):
        _LOGGER.ingo(f"{self.name} Service call: {call.data}")
        """ local processing """
        result = await self.async_process_call(service, call)
        """ Process by children """
        for name, (child, state) in self._subzones.items():
            sub_result = await child.async_call(service, call)
            if sub_result is not None:
                result += sub_result
        return result

    """ Local service precessing. Can be overriden """
    async def async_process_call(self, service: str, call: ServiceCall):
        pass

    """ Adjust state of the acruator to the zone's state """
    """ Force means immadiate adjustment. """
    async def async_actuator_control(self, force = False):
        _LOGGER.info(f"{self.name} Actuator control with state {self.state} and force {force},")
        
        for acn, (ac, acs) in self._actuators.items():
            if acs == self.state:
                continue
            """ Set pump according to the heating state """
            self._actuators[acn] = (ac, self.state)
            if self.is_on:
                await ac.async_change(STATE_ON)
            else:
                await ac.async_change(STATE_OFF, force)
        

    """ Child state has changed """
    async def async_bottom_change(self, child_name, new_state):
        _LOGGER.info(f"{self.name}: zone change from bottom {child_name} to {new_state}")
        
        if child_name not in self._subzones:
            _LOGGER.warning(f"{self.name}: Unknown subzone name! {child_name}")
            #_LOGGER.warning(f"Available names: {self._subzones.keys()}")
            return

        """ Check change of the child zone """
        (sz, szs) = self._subzones[child_name]
        if szs == new_state:
            # No change
            return
        self._subzones[child_name] = (sz, new_state)

        """ Calculate new state of the actual zone """
        any_on = False
        for szn, (sz, szs) in self._subzones.items():
            if szs == STATE_ON:
                any_on = True
                break
        _LOGGER.debug(f"{self.name}: Calculated zone state: {any_on}")

        """ Check change """
        change = (self.is_on != any_on)
        if change:            
            self._attr_is_on = any_on
            self._last_change = dt_util.utcnow()
            _LOGGER.debug(f"{self.name} state: {self.is_on}")

            """ Update HA states """
            self.async_schedule_update_ha_state(True)
            _LOGGER.debug(f"{self.name} update to {self.is_on}")
            #self.async_write_ha_state()

            """ Notify all subzones about the change """
            for szn, (sz, szs) in self._subzones.items():
                await sz.async_top_change(self.state)
            
            """ Notify parent """
            if self.parent is not None:
                await self.parent.async_bottom_change(self.name, self.state)
            
            """ Adjust actuators """
            """ When parent zone is heating and this zone is not, then stop immeditaly """
            force = False if self.parent is None else (self.parent.is_on and not self.is_on)
            await self.async_actuator_control(force)

    """ Change from the top """
    async def async_top_change(self, new_state):
        _LOGGER.info(f"{self.name}: zone change from top to {new_state}")
        if self.state == STATE_ON and self.parent.state == STATE_OFF:
            _LOGGER.error("Invalid state. Heating required, but parent zone is not heating!")

        if self.state == STATE_OFF and self.parent.state == STATE_ON:
            """ Control actuators """
            await self.async_actuator_control(True)

    @property
    def parent(self):
        return self._parent
    @property
    def enabled(self):
        return self._enabled
    @property
    def entities(self) ->dict:
        return self._entities
    @property
    def presets(self) ->dict:
        return self._presets
    @property
    def zonename(self) ->str:
        return self._zonename
    @property
    def last_change(self):
        return self._last_change


class ZoneMaster(BaseZone):

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        super().__init__(hass, None, config, CONF_MAIN)

        self._attr_is_on = False

        self._attr_device_info = DeviceInfo({
            "identifiers": {(DOMAIN, CONF_MAIN)},
            "name": CONF_MAIN,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        })

        self._enabled = True
        if CONF_ENABLED in config:
            self._enabled = config[CONF_ENABLED]

        for cz in config[CONF_ZONES]:
            zone = Zone(self.hass, self, cz)
            self._subzones[zone.name] = (zone, STATE_UNKNOWN)
            self._entities += zone.entities

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._enabled, cp)
            self._actuators[pump.name] = (pump, STATE_UNKNOWN)
            self._entities.append(pump)


class Zone(BaseZone):

    def __init__(self, hass: HomeAssistant, parent, config: dict) -> None:

        super().__init__(hass, parent, config, config[CONF_NAME])

        """ State is for heating on/off """
        self._attr_is_on = False
        self._enabled = parent.enabled

        self._attr_device_info = DeviceInfo({
            "identifiers": {(DOMAIN, self.zonename)},
            "name": self.zonename,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        })

        for csz in config[CONF_SUBZONES]:
            subzone = SubZone(self.hass, self, csz)
            self._subzones[subzone.name] = (subzone, STATE_UNKNOWN)
            self._entities += subzone.entities

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self.enabled, cp)
            self._actuators[pump.name] = (pump, STATE_UNKNOWN)
            self._entities.append(pump)


""" SubZone is part of the zone. E.g. a room It may have valves (e.g. TRV) to open/close the heating """
""" Switch is to provide the interface to the climate entity. The climate entity will switch it on/off """
class SubZone(BaseZone):

    def __init__(self, hass: HomeAssistant, parent, config: dict) -> None:

        super().__init__(hass, parent, config, f"{parent.zonename}_{config[CONF_NAME]}")

        self._attr_icon = "mdi:radiator-disabled"
        self._attr_available = True
        """ State is for heating on/off """
        self._attr_is_on = False
        self._enabled = parent.enabled

        """ use dafault values for missing preset entries """
        for dk, dv in PRESET_DEFAULTS.items():
            if not dk in self._presets:
                self._presets[dk] = dv

        self._attr_device_info = DeviceInfo({
            "identifiers": {(DOMAIN, parent.zonename)},
        })

        """ Sensor for temperature """
        self._temperature = None
        if CONF_SENSOR in config:
            self._temperature = TemperatureSensor(self, config[CONF_SENSOR])
            self._sensors[self._temperature.name] = (self._temperature, STATE_UNKNOWN)
            self._entities.append(self._temperature)

        """ Switch """
        self._switch = SubZoneSwitch(self)
        self._entities.append(self._switch)

        """ Switch """
        self._boost = SubZoneBoostSwitch(self, self._presets[CONF_BOOST_TIME])
        self._entities.append(self._boost)

        """ Add valves as actuators """
        if CONF_VALVES in config:
            for cv  in config[CONF_VALVES]:
                valve = Valve(self, self._enabled, cv)
                self._actuators[valve.name] = (valve, STATE_ON)
                self._entities.append(valve)

    """ Turn on heating in subzone """
    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument

        """ No need to to anything if both of them are active (one of them just called this) """
        if self._switch.is_on and self._boost.is_on:
            return

        """ Set on state """
        self._attr_is_on = True
        self._last_change = dt_util.utcnow()
        _LOGGER.debug(f"{self.name} state: {self.is_on}")

        self._attr_icon = "mdi:radiator" if self.state == STATE_ON else "mdi:radiator-off"
        self.async_write_ha_state()
        """ Notify parent zone """
        #self.hass.async_create_task(self.parent.async_bottom_change(self.name, STATE_ON))
        await self.parent.async_bottom_change(self.name, STATE_ON)
        """ Adjust actuators on this level """
        await self.async_actuator_control()

    """ Turn off heating in subzone """
    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument

        """ Don not turn off if any of them are still active  """
        if self._switch.is_on or self._boost.is_on:
            return

        """ Set off state """
        self._attr_is_on = False
        self._last_change = dt_util.utcnow()
        _LOGGER.debug(f"{self.name} state: {self.is_on}")

        self._attr_icon = "mdi:radiator" if self.state == STATE_ON else "mdi:radiator-off"
        self.async_write_ha_state()
        """ Notify parent zone """
        #self.hass.async_create_task(self.parent.async_bottom_change(self.name, STATE_OFF))
        await self.parent.async_bottom_change(self.name, STATE_OFF)
        """ Adjust actuators on this level """
        """ If this was the last heating zone, then it can be left open """
        if self.parent.is_on:
            await self.async_actuator_control()
