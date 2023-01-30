"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_NAME, CONF_ENTITY_ID, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, UnitOfTemperature
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import Entity


from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES, CONF_PUMPS, CONF_SUBZONES, CONF_SENSOR,
    CONF_MAIN, CONF_MODES,
    remove_platform_name,
    SERVICE_SUBZONE_PRESET_MODE,
)

_LOGGER = logging.getLogger(__name__)


class SubZone(SwitchEntity):

    def __init__(self, zone, device_name, config):
        self._attr_name = slugify(f"{zone.name}_{config[CONF_NAME]}")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        self._attr_icon = "mdi:radiator-disabled"
        self._attr_available = True
        self._state = "off"

        self._entities = [ self ]

        self._zone = zone
        self.hass = zone.hass

        if CONF_SENSOR in config:
            self._temp = SubZoneTemperature(self, self._device_name, config[CONF_SENSOR])
            self._entities += [ self._temp ]

        self._mode = SubZoneMode(self, self._device_name)
        self._entities += [ self._mode ]
        
        self.hass.states.async_set(f"subzone.{self.name}" , self._mode.state)

    async def async_call(self, service: str, call: ServiceCall):
        if  f"subzone.{self.name}" in call.data[CONF_ENTITY_ID]:
            if service == SERVICE_SUBZONE_PRESET_MODE:
                return await self.async_call_subzone_preset_mode(call)
            _LOGGER.warning(f"No such service {service}")
        return False

    async def async_call_subzone_preset_mode(self, call: ServiceCall):
        new_mode = call.data["preset_mode"]
        result = await self._mode.async_set_preset_mode(new_mode)
        if result:
            self.hass.states.async_set(f"subzone.{self.name}" , self._mode.state)
        return result

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
    #@property    
    #def hass(self) ->HomeAssistant:
    #    return self._hass
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_name)},
            "name": self._zone.name,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }

class SubZoneTemperature(SensorEntity):

    def __init__(self, zone, device_name, entity_id):
        self._sensor_id = entity_id
        self._attr_name = slugify(f"{zone.name}_{remove_platform_name(entity_id)}")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        #self._attr_icon = "mdi:radiator-disabled"
        self._attr_available = False
        self._temperature = None
        self._device_class =  SensorDeviceClass.TEMPERATURE

        self._zone = zone
        self.hass = zone.hass

        _LOGGER.debug(self._sensor_id)
        self._listen = async_track_state_change_event(self.hass, [self._sensor_id], self.async_temp_state_change_event)

    async def async_temp_state_change_event(self, event):
        self._temperature = event.data.get("new_state").state
        self._attr_available = True
        self.async_write_ha_state()

    @property
    def state(self):
        return self._temperature
    @property
    def unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS
    @property    
    def name(self):
        return self._attr_name
    #@property    
    #def hass(self) ->HomeAssistant:
    #    return self._hass
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_name)},
            "name": self._zone.name,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }

class SubZoneMode(SensorEntity):
    """ MZH offers this control """
    """ Busy, Away, Vacation, Night, Off, Burst """
    def __init__(self, zone, device_name):
        self._states = CONF_MODES
        self._attr_name = slugify(f"{zone.name}_mode")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        self._attr_available = True
        self._state = CONF_MODES[0]
        self._device_class =  SensorDeviceClass.ENUM

        self._zone = zone
        self.hass = zone.hass

    async def async_set_preset_mode(self, preset):
        if preset in CONF_MODES:
            self._state = preset
            self.async_write_ha_state()
        else:
            return False

    @property
    def state(self):
        return self._state
    @property    
    def name(self):
        return self._attr_name
    #@property    
    #def hass(self) ->HomeAssistant:
    #    return self._hass
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_name)},
            "name": self._zone.name,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }
