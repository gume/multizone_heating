"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
    STATE_UNKNOWN, STATE_ON, STATE_OFF,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, UnitOfTemperature
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import Entity
from homeassistant.exceptions import ServiceNotFound

from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES, CONF_PUMPS, CONF_SUBZONES, CONF_SENSOR, CONF_VALVES, CONF_SWITCH,
    CONF_MAIN,
    remove_platform_name,
    SERVICE_SUBZONE_PRESET_MODE, PRESET_MODES, PRESET_MODE_ACTIVE, PRESET_MODE_AWAY, PRESET_MODE_NIGHT, PRESET_MODE_VACATION,
    PRESET_MODE_BURST, PRESET_MODE_OFF, PRESET_MODE_MANUAL,
    CONF_ACTIVE_TEMP, CONF_AWAY_TEMP, CONF_NIGHT_TEMP, CONF_VACATION_TEMP, CONF_OFF_TEMP, CONF_BURST_TEMP, CONF_BURST_TIME,
)

_LOGGER = logging.getLogger(__name__)


class SubZone(SwitchEntity):

    def __init__(self, zone, device_name, config):
        self._attr_name = slugify(f"{zone.name}_{config[CONF_NAME]}")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        self._attr_icon = "mdi:radiator-disabled"
        self._attr_available = True
        self._state = STATE_OFF

        self._entities = [ self ]

        self._zone = zone
        self.hass = zone.hass

        if CONF_SENSOR in config:
            self._temp = SubZoneTemperature(self, self._device_name, config[CONF_SENSOR])   # Sensor for temperature display
            self._entities += [ self._temp ]

        self._preset_handler = SubZoneMode(self, self._device_name)   # Sensor and service offer for preset mode display/change
        self._entities += [ self._preset_handler ]
        self._preset_mode = self._preset_handler.state
        
        self._valves = []
        self._valve_states = {}
        if CONF_VALVES in config:
            for cv  in config[CONF_VALVES]:
                switch = cv[CONF_SWITCH]
                self._valves.append(switch)
                self._valve_states[switch] = STATE_UNKNOWN

        self._preset = {}
        self.init_temperatures(config)
        _LOGGER.debug(f"Presets: {self._preset}")

        """ Listen on valve changes and force them to follow the subzone requirements """
        if len(self._valves) > 0:
            self._listen_valves = async_track_state_change_event(self.hass, self._valves, self.async_track_valve_state_change_event)
            self.hass.async_create_task(self.async_control_valves())
                
        self.hass.async_create_task(self.async_update())

    def init_temperatures(self, config):
        """ Read preset temperatures and add default values if they would not exist """
        defaults = { CONF_ACTIVE_TEMP: 20.5, CONF_AWAY_TEMP: 18.0, CONF_NIGHT_TEMP: 18.0,
            CONF_VACATION_TEMP: 12.0, CONF_OFF_TEMP: 5.0, CONF_BURST_TEMP: 25.0, CONF_BURST_TIME: 30*60 }
        for cp in [ CONF_ACTIVE_TEMP, CONF_AWAY_TEMP, CONF_NIGHT_TEMP, CONF_VACATION_TEMP, CONF_OFF_TEMP, CONF_BURST_TEMP, CONF_BURST_TIME ]:
            if cp in config:
                """ Try to read from the config file """
                try:
                    self._preset[cp] = float(config[cp])
                except:
                    _LOGGER.warn(f"{self.name} Wrong config for preset {cp}: {config[cp]}")
            else:
                """ Use parent value, if defined """
                if self.parent is not None and cp in self.parent.preset:
                    self._preset[cp] = self.parent.preset[cp]
                else:
                    """ If there is no entry in the config file use the default """
                    self._preset[cp] = defaults[cp]
        _LOGGER.debug(self._preset)

    async def async_update(self):
        self._preset_mode = self._preset_handler.state

        """ Update the subzone.xxx state with the actual states """
        attributes = {}
        attributes["temperature"] = self._temp.state
        attributes["preset_mode"] = self._preset_mode
        if self._preset_mode != PRESET_MODE_MANUAL:
            _LOGGER.debug(self._preset)
            attributes["target_temperature"] = self._preset[f"{self._preset_mode}_temp"]
        attributes["valves"] = len(self._valves)

        self.hass.states.async_set(f"subzone.{self.name}" , self.state, attributes)

    async def async_call(self, service: str, call: ServiceCall):
        """ Service call dispatcher/ Returns false is there was no processing """
        if  f"subzone.{self.name}" in call.data[CONF_ENTITY_ID]:
            if service == SERVICE_SUBZONE_PRESET_MODE:
                return await self.async_call_subzone_preset_mode(call)
            _LOGGER.warning(f"No such service {service}")
        return False

    async def async_call_subzone_preset_mode(self, call: ServiceCall):
        """ Set the subzone mode """
        new_mode = call.data["preset_mode"]
        result = await self._preset_handler.async_set_preset_mode(new_mode)
        if result:
            """ Change climate to the new preset/value """
            """ TBD... """
            self.async_schedule_update_ha_state(True)
        return result

    async def async_control_valves(self):
        """ Set valves according to the subzone state """
        """ Valve states are cached, use them """
        for v, s in self._valve_states.items():
            if s != self._state:
                try:
                    await self.hass.services.async_call("switch", f"turn_{self._state}", {"entity_id": v})
                except ServiceNotFound as e:
                    _LOGGER.warning(str(e))

    async def async_track_valve_state_change_event(self, event):
        if event.data[CONF_ENTITY_ID] in self._valves:
            v, s = (event.data[CONF_ENTITY_ID], event.data.get("new_state").state)
            self._valve_states[v] = s
            if s != self._state:
                """ Schedule a control """
                self.hass.async_create_task(self.async_control_valves())
        """ Scedule update """
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """ This is the interface to the climate entity. The climate entity will switch it """
        self._state = STATE_ON
        self._attr_icon = "mdi:radiator"
        self.async_write_ha_state()
        self.hass.async_create_task(self._zone.async_subzone_change(self.name, STATE_ON))
        self.hass.async_create_task(self.async_control_valves())

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """ This is the interface to the climate entity. The climate entity will switch it """
        self._state = STATE_OFF
        self._attr_icon = "mdi:radiator-off"
        self.async_write_ha_state()
        self.hass.async_create_task(self._zone.async_subzone_change(self.name, STATE_OFF))
        self.hass.async_create_task(self.async_control_valves())

    @property
    def parent(self):
        return self._zone
    @property
    def state(self):
        return self._state
    @property
    def entities(self):
        return self._entities
    @property
    def is_on(self):
        return self._state == STATE_ON
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
        self._attr_available = False
        self._attr_device_class =  SensorDeviceClass.TEMPERATURE
        self._attr_device_info = DeviceInfo({ "identifiers": {(DOMAIN, self._device_name)} })
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

        self._zone = zone
        self.hass = zone.hass

        self._listen = async_track_state_change_event(self.hass, [self._sensor_id], self.async_temp_state_change_event)

    async def async_temp_state_change_event(self, event):
        self._attr_native_value = event.data.get("new_state").state
        self._attr_available = True
        self.async_write_ha_state()

        self._zone.async_schedule_update_ha_state(True)


class SubZoneMode(SensorEntity):
    """ MZH offers this control via service """
    """ Busy, Away, Vacation, Night, Off, Burst, Manual """
    def __init__(self, zone, device_name):
        self._presets = PRESET_MODES
        self._attr_name = slugify(f"{zone.name}_preset")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self._attr_name}")
        self._device_name = device_name
        self._attr_available = True
        self._attr_native_value = PRESET_MODE_MANUAL
        self._device_class =  SensorDeviceClass.ENUM
        self._attr_device_info = DeviceInfo({ "identifiers": {(DOMAIN, self._device_name)} })

        self._zone = zone
        self.hass = zone.hass

    async def async_set_preset_mode(self, preset):
        if not preset in PRESET_MODES:
            _LOGGER.warn(f"Invalid preset mode: {preset}")
            return False

        self._attr_native_value = preset
        self.async_write_ha_state()

        """ No need to tell the parent, as it is the caller """
        """ Return True as success """
        return True
 
