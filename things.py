"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging
import datetime

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    CONF_ENTITY_ID, DEVICE_CLASS_POWER,
    STATE_UNKNOWN, STATE_ON, STATE_OFF,
    SERVICE_TURN_ON, SERVICE_TURN_OFF,
    ATTR_TEMPERATURE,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, UnitOfTemperature
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    CONF_BOOST_TIME, CONF_KEEP_ACTIVE, CONF_KEEP_ALIVE,
    ATTR_ACTIVE, ATTR_ACTIVE_START, ATTR_ACTIVE_END,
    ATTR_BOOST, ATTR_BOOST_START, ATTR_BOOST_END,
)

_LOGGER = logging.getLogger(__name__)


def remove_platform_name(str):
    for tag in ['sensor', 'switch', 'input_number', 'input_boolean']:
        if str.startswith(f"{tag}."):
            return str[len(tag) + 1:]
    return str


""" Pump controls the heating, either for a zone or for all the zones """
""" There is a binary sensor to visualize the state of the sensor """
class Pump(BinarySensorEntity): 

    def __init__(self, parent, enabled, config):
        self._switch = config[CONF_ENTITY_ID]

        self._attr_name = slugify(f"{parent.zonename}_{remove_platform_name(self._switch)}")
        self._attr_unique_id = slugify(f"{DOMAIN}_{self.name}")
        self._device_name = self.name
        self._attr_device_info = parent.device_info
        self._icon = { STATE_ON: "mdi:pump", STATE_OFF: "mdi:pump-off"}
        self._attr_available = False
        self._attr_is_on = False    # Pumps starts with off
        self._attr_icon = self._icon[self.state]
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_should_poll = False

        self._parent = parent
        self._enabled = enabled
        self.hass = parent.hass

        """ Keep active keeps circulation for a time period """
        self._keep_active = 0   # Should be in seconds
        self._later = None  # _later is a function for keeping active state
        if CONF_KEEP_ACTIVE in config:
            try:
                if config[CONF_KEEP_ACTIVE] is not None:
                    self._keep_active = int(config[CONF_KEEP_ACTIVE])
            except:
                _LOGGER.warning(f"keep_active input :{config[CONF_KEEP_ACTIVE]}: is wrong for {self._switch}")

        """ Keep alive repeat the on (off?) state peridically """
        self._keeo_alive = 0    # Should be in seconds
        if CONF_KEEP_ALIVE in config:
            try:
                if config[CONF_KEEP_ALIVE] is not None:
                    self._keep_alive = int(config[CONF_KEEP_ALIVE])
            except:
                _LOGGER.warning(f"keep_alive input :{config[CONF_KEEP_ALIVE]}: is wrong for {self._switch}")

        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes[ATTR_ACTIVE] = False

        self._listen = async_track_state_change_event(self.hass, [self._switch], self.async_switch_state_change_event)

    async def async_switch_state_change_event(self, event):
        _LOGGER.info(f"{self.name} switch change {event.data}")
        self._attr_available = True
        new_state = event.data.get("new_state").state
        if new_state != self.state:
            """ Unintentional state change. Change back! """
            _LOGGER.warning(f"{self.name} unintentional change.")
        else:
            return

        if self.is_on:
            await self.async_change(STATE_ON, True)
        else:
            await self.async_change(STATE_OFF, True)
    
    async def async_change(self, state, force = False):
        _LOGGER.info(f"{self.name} Change switch {self._switch} to {state} with force {force}")
        if state == STATE_ON:
            return await self.async_turn_on()
        else:
            if force:
                return await self.async_turn_off_now(dt_util.utcnow())
            else:
                return await self.async_turn_off()

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        self._attr_is_on = True
        if self._enabled:
            _LOGGER.info(f"Turn_on switch: {self._switch}")
            await self.hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {CONF_ENTITY_ID: self._switch})

        await self.async_clear_active()
        self._attr_icon = self._icon[self.state]
        self.async_write_ha_state()

    async def async_clear_active(self):
        if self._later != None:
            self._later() # Cancel old event
            self._later = None
        
        self._attr_extra_state_attributes[ATTR_ACTIVE] = False
        if ATTR_ACTIVE_START in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_ACTIVE_START]
        if ATTR_ACTIVE_END in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_ACTIVE_END]
        self.async_write_ha_state()

    async def async_turn_off_now(self, _):
        await self.async_clear_active()

        """ ASSERT """
        if self._parent.state == STATE_ON:
            _LOGGER.error(f"ERROR! Cant switch off actuator {self._switch} while the zone {self._parent.name} should heat")
            return await self.async_turn_on()

        self._attr_is_on = False
        self._attr_icon = self._icon[self.state]

        self.async_write_ha_state()
        if self._enabled:        
            _LOGGER.info(f"Turn_off switch immediately: {self._switch}")
            await self.hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, {CONF_ENTITY_ID: self._switch})

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        self._attr_is_on = False
        self.async_write_ha_state()
        if self._keep_active == 0:
            return await self.async_turn_off_now(dt_util.utcnow())

        _LOGGER.info(f"Turn_off switch: {self._switch} after {self._keep_active} seconds")

        """ Check the heating state at parent. Taking into account the time of the change """
        activetime =  self._parent.last_change + datetime.timedelta(seconds=self._keep_active) - dt_util.utcnow()
        activetime_s = activetime.total_seconds()
        _LOGGER.debug(f"activetime: {activetime_s}")
        if activetime_s < 0.0:
            # active time is already over
            return await self.async_turn_off_now(dt_util.utcnow())

        """ Set turn off call at a later time """
        if self._later != None:
            self._later() # Cancel old event
        self._later = async_call_later(self.hass, activetime_s, self.async_turn_off_now)
        self._attr_extra_state_attributes[ATTR_ACTIVE] = True
        self._attr_extra_state_attributes[ATTR_ACTIVE_START] = dt_util.utcnow()
        self._attr_extra_state_attributes[ATTR_ACTIVE_END] = dt_util.utcnow() + datetime.timedelta(seconds=activetime_s)
        self.async_write_ha_state()


""" Valve is like a Pump, but starts with open state """
class Valve(Pump): 

    def __init__(self, parent, enabled, config):
        super().__init__(parent, enabled, config)

        self._attr_device_class = BinarySensorDeviceClass.OPENING
        self._attr_is_on = True    # Valve starts with on

        self._icon = { STATE_ON: "mdi:valve-open", STATE_OFF: "mdi:valve-closed"}
        self._attr_icon = self._icon[self.state]


""" Temperature sensor to receive updates """
class TemperatureSensor(Entity):

    def __init__(self, parent, entity_id):
        self._sensor_id = entity_id
        self._attr_name = f"{slugify(parent.zonename)}_temperature"
        self._attr_unique_id = slugify(f"{DOMAIN}_{self.name}_temp")
        self._attr_available = False

        self._parent = parent
        self.hass = parent.hass

        self._listen = async_track_state_change_event(self.hass, [self._sensor_id], self.async_temp_state_change_event)

    async def async_temp_state_change_event(self, event):
        new_state = event.data.get("new_state").state
        self._attr_available = True

        await self._parent.async_sensor_change(self.name, new_state)


class SubZoneSwitch(SwitchEntity):

    def __init__(self, parent):
        #self._attr_name = slugify(f"{SWITCH_DOMAIN}.{parent.zonename}")
        self._attr_name = slugify(parent.zonename)
        self._attr_unique_id = slugify(f"{DOMAIN}_{self.name}_switch")
        self._attr_available = True
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_device_info = parent.device_info
        self._attr_is_on = False

        self._parent = parent
        self.hass = parent.hass

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()
        self.hass.async_create_task(self._parent.async_turn_on())
        #await self._parent.async_turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
        self.hass.async_create_task(self._parent.async_turn_off())
        #await self._parent.async_turn_off()

class SubZoneBoostSwitch(SwitchEntity):

    def __init__(self, parent, boosttime):
        #self._attr_name = slugify(f"{SWITCH_DOMAIN}.{parent.zonename}")
        self._attr_name = f"{slugify(parent.zonename)}_boost"
        self._attr_unique_id = slugify(f"{DOMAIN}_{self.name}_boost")
        self._attr_available = True
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_device_info = parent.device_info
        self._attr_is_on = False
        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes[ATTR_BOOST] = False

        self._parent = parent
        self.hass = parent.hass
        self._boosttime = boosttime
        self._switchoff = None

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.hass.async_create_task(self._parent.async_turn_on())
        #await self._parent.async_turn_on()

        self._switchoff = async_call_later(self.hass, self._boosttime, self.async_turn_off_now)
        self._attr_extra_state_attributes[ATTR_BOOST] = True
        self._attr_extra_state_attributes[ATTR_BOOST_START] = dt_util.utcnow()
        self._attr_extra_state_attributes[ATTR_BOOST_END] = dt_util.utcnow() + datetime.timedelta(seconds=self._boosttime)
        self.async_write_ha_state()

    async def async_turn_off_now(self, _) -> None:
        await self.async_turn_off()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.hass.async_create_task(self._parent.async_turn_off())
        #await self._parent.async_turn_off()

        if self._switchoff is not None:
            self._switchoff()
            self._switchoff = None
        
        self._attr_extra_state_attributes[ATTR_BOOST] = False
        if ATTR_BOOST_START in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_BOOST_START]
        if ATTR_BOOST_END in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_BOOST_END]
        self.async_write_ha_state()
