"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import logging
import datetime

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_POWER,
    STATE_UNKNOWN, STATE_ON, STATE_OFF,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util


from .const import (
    MANUFACTURER, VERSION, NAME,
    DOMAIN,
    CONF_ZONES, CONF_PUMPS, CONF_SUBZONES, CONF_KEEP_ACTIVE,
    CONF_MAIN,
    remove_platform_name,
    ATTR_ACTIVE, ATTR_ACTIVE_START, ATTR_ACTIVE_END,
    CONF_ACTIVE_TEMP, CONF_AWAY_TEMP, CONF_NIGHT_TEMP, CONF_VACATION_TEMP, CONF_OFF_TEMP, CONF_BURST_TEMP, CONF_BURST_TIME
)

from .subzone import SubZone


_LOGGER = logging.getLogger(__name__)


class Zone:

    def __init__(self, zm: ZoneMaster, config: dict) -> None:

        self._attr_name = slugify(config[CONF_NAME])
        self._zonemaster = zm
        self._entities = []
        self._hass = zm.hass

        self._pump_names = []
        self._pump_states = {}
        self._subzone_names = []
        self._subzone_states = {}
        
        #self._heating = STATE_UNKNOWN
        self._heating = STATE_OFF
        self._heating_change = dt_util.utcnow()

        self._preset = {}
        self.init_temperatures(config)
        _LOGGER.debug(f"Presets: {self._preset}")

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self.name, cp)
            self._pump_names.append(pump.name)
            self._pump_states[pump.name] = (pump, STATE_UNKNOWN)
            self._entities += pump.entities

        for csz in config[CONF_SUBZONES]:
            subzone = SubZone(self, self.name, csz)
            self._subzone_names.append(subzone.name)
            self._subzone_states[subzone.name] = (subzone, STATE_UNKNOWN)
            self._entities += subzone.entities

    def init_temperatures(self, config):
        for cp in [ CONF_ACTIVE_TEMP, CONF_AWAY_TEMP, CONF_NIGHT_TEMP, CONF_VACATION_TEMP, CONF_OFF_TEMP, CONF_BURST_TEMP, CONF_BURST_TIME  ]:
            if cp in config:
                """ Try to read from the config file """
                try:
                    self._preset[cp] = float(config[cp])
                except:
                    _LOGGER.warn(f"{self.name} Wrong config for preset {cp}: {config[cp]}")
            else:
                """ If there is no entry in the config file, maybe the parent already has this value """
                if self.parent is not None and cp in self.parent.preset:
                    self._preset[cp] = self.parent.preset[cp]

    async def async_call(self, service: str, call: ServiceCall):
        _LOGGER.debug(f"async_call {self.name}")
        main_result = []
        for zn, (z, zs) in self._subzone_states.items():
            result = await z.async_call(service, call)
            if result is not False:
                main_result.append((z, result))
        return main_result

    async def async_parent_notify(self):
        _LOGGER.debug(f"{self.name}: Parent notify")
        """ Tell the parent about the cahnge (SubZone->Zone, Zone->ZoneMaster) """
        if self.parent is not None:
            await self.parent.async_subzone_change(self.name, self._heating)

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
            if szs == STATE_ON:
                any_on = STATE_ON
                break
        _LOGGER.debug(f"{self.name}: Calculated any on {any_on}")

        """ in case of change, notify parent and schedule a pump control """
        if any_on != self._heating:
            _LOGGER.debug(f"{self.name}: Change heating to {any_on}")
            self._heating = any_on
            self._heating_change = dt_util.utcnow()
            await self.async_parent_notify()
            self.hass.async_create_task(self.async_control_pumps())

    async def async_control_pumps(self, force = False):
        _LOGGER.debug(f"{self.name} Pump control {force}, {self._heating}")
        
        """ Heating should be on or off to change """
        if self._heating != STATE_ON and self._heating != STATE_OFF:
            return

        _LOGGER.debug(f"{self.name} Pump control to {self._heating}")
        for pn, (p, ps) in self._pump_states.items():

            """ Check active pump. When the pump is active, it should be on regardelss of the heating state """
            if p.extra_state_attributes[ATTR_ACTIVE]:
                _LOGGER.debug(f"Force active pump {pn} to on")
                await p.async_turn_on()
                continue

            """ When pump state and heating state is the same, the control should be forced """
            if ps == self._heating and not force:
                continue

            _LOGGER.debug(f"Pump {pn} to {self._heating}")
            self._pump_states[pn] = (p, self._heating)
            if self._heating == STATE_ON:
                await p.async_turn_on()
            if self._heating == STATE_OFF:
                await p.async_turn_off()

    @property
    def name(self):
        return self._attr_name
    @property
    def entities(self) ->dict:
        return self._entities
    @property
    def hass(self) ->HomeAssistant:
        return self._hass
    @property
    def parent(self):
        return self._zonemaster
    @property
    def preset(self) ->dict:
        return self._preset


class ZoneMaster(Zone):

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        
        self._entities = []
        self._attr_name = CONF_MAIN

        self._subzone_names = []
        self._subzone_states = {}
        self._pump_names = []
        self._pump_states = {}

        self._hass = hass

        self._heating = STATE_OFF
        self._heating_change = dt_util.utcnow()

        self._preset = {}
        self.init_temperatures(config)
        _LOGGER.debug(f"Presets: {self._preset}")


        for cz in config[CONF_ZONES]:
            zone = Zone(self, cz)
            self._subzone_names.append(zone.name)
            self._subzone_states[zone.name] = (zone, STATE_UNKNOWN)
            self._entities += zone.entities

        for cp in config[CONF_PUMPS]:
            pump = Pump(self, self._attr_name, cp)
            self._pump_names.append(pump.name)
            self._pump_states[pump.name] = (pump, STATE_UNKNOWN)
            self._entities += pump.entities

    #@override
    @property
    def parent(self):
        return None


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

        self._keep_active = 0
        self._later = None
        self._keeo_alive = 0
        if CONF_KEEP_ACTIVE in config:
            _LOGGER.debug(config)
            try:
                if config[CONF_KEEP_ACTIVE] is not None:
                    self._keep_active = int(config[CONF_KEEP_ACTIVE])
            except:
                _LOGGER.warning(f"keep_active input :{config[CONF_KEEP_ACTIVE]}: is wrong for {self._pumpswitch}")

        self._entities = [ self ]
        self._zone = zone

        self._attr_state = STATE_UNKNOWN
        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes[ATTR_ACTIVE] = False

        self.hass = zone.hass

        self._listen = async_track_state_change_event(self.hass, [self._pumpswitch], self.async_pumpswitch_state_change_event)

    async def async_pumpswitch_state_change_event(self, event):
        _LOGGER.debug(f"Pump change {event.data}")
        self._attr_state = event.data.get("new_state").state
        self._attr_icon = "mdi:valve-open" if self.state == STATE_ON else "mdi:valve-closed"
        self._attr_available = True
        self.async_write_ha_state()
        self.hass.async_create_task(self._zone.async_control_pumps(True))

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        _LOGGER.debug(f"switch turn_on entity_id: {self._pumpswitch}")
        await self.hass.services.async_call("switch", "turn_on", {"entity_id": self._pumpswitch})

    async def async_turn_off_now(self, _):
        _LOGGER.debug(f"switch turn_off entity_id: {self._pumpswitch}")
        await self.hass.services.async_call("switch", "turn_off", {"entity_id": self._pumpswitch})
        self._attr_extra_state_attributes[ATTR_ACTIVE] = False
        if ATTR_ACTIVE_START in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_ACTIVE_START]
        if ATTR_ACTIVE_END in self._attr_extra_state_attributes:
            del self._attr_extra_state_attributes[ATTR_ACTIVE_END]
        self.async_write_ha_state()


    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        if self._keep_active == 0:
            return await self.async_turn_off_now(dt_util.utcnow())

        _LOGGER.debug(f"switch call turn_off entity_id: {self._pumpswitch} after {self._keep_active} seconds")
        if self._later != None:
            self._later() # Cancel old event
        """ Check the heating state at parent. Taking into account the time of the change """
        activetime =  self._zone._heating_change + datetime.timedelta(seconds=self._keep_active) - dt_util.utcnow()
        activetime_s = activetime.total_seconds()
        if activetime_s < 0.0:
            return await self.async_turn_off_now(dt_util.utcnow())

        """ Set the turn off at a later time """
        self._later = async_call_later(self.hass, activetime_s, self.async_turn_off_now)
        self._attr_extra_state_attributes[ATTR_ACTIVE] = True
        self._attr_extra_state_attributes[ATTR_ACTIVE_START] = dt_util.utcnow()
        self._attr_extra_state_attributes[ATTR_ACTIVE_END] = dt_util.utcnow() + datetime.timedelta(seconds=activetime_s)
        self.async_write_ha_state()
    
    @property
    def entities(self):
        return self._entities
    @property
    def is_on(self):
        return self._attr_state == STATE_ON
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_name)},
            "name": self._zone.name,
            "model": NAME,
            "manufacturer": MANUFACTURER,
        }
    @property
    def parent(self):
        return self._zone
