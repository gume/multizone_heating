from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.const import (
    STATE_UNKNOWN, STATE_ON, STATE_OFF,
)

from slugify import slugify

import logging
import copy
import datetime

from .const import DOMAIN, NAME, VERSION, MANUFACTURER, \
    ATTR_POSTACTIVE, ATTR_POSTACTIVE_START, ATTR_POSTACTIVE_END, ATTR_BOOST

_LOGGER = logging.getLogger(__name__)


class Valve():

    def __init__(self, name, master, valve_type) -> None:
        self.master = master
        self._hass = master._hass
        self.name = name
        self.valve_type = valve_type

    def turn_on(self):
        _LOGGER.debug(f"Valve {self.name} turn on")
        if self.valve_type == "switch":
            self._hass.async_create_task(
                self._hass.services.async_call("switch", "turn_on", {"entity_id": self.name})
            )
        elif self.valve_type == "valve":
            self._hass.async_create_task(
                self._hass.services.async_call("valve", "open_valve", {"entity_id": self.name})
            )

    def turn_off(self):
        _LOGGER.debug(f"Valve {self.name} turn off")
        if self.valve_type == "switch":
            self._hass.async_create_task(
                self._hass.services.async_call("switch", "turn_off", {"entity_id": self.name})
            )
        elif self.valve_type == "valve":
            self._hass.async_create_task(
                self._hass.services.async_call("valve", "close_valve", {"entity_id": self.name})
            )

    def __str__(self):
        return f"Valve(name={self.name}, valve_type={self.valve_type})"

class Pump(BinarySensorEntity):

    should_poll = False

    def __init__(self, name, master):
        super().__init__()

        # name is the name of the related switch
        self.switch = name
        self.master = master
        self._hass = master._hass

        if name.startswith("switch."):
            name = name[7:]
        self._attr_name = slugify(name)
        self._attr_unique_id = slugify(f"multizone_{master.name}_pumpfeedback_{name}")

        self._attr_is_on = False
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._icon = { STATE_ON: "mdi:pump", STATE_OFF: "mdi:pump-off"}
        self._attr_device_info = master.device_info

        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self.turn_off()

    def turn_on(self):
        _LOGGER.debug(f"Pump {self.name} turn on")
        self._hass.async_create_task(
            self._hass.services.async_call("switch", "turn_on", {"entity_id": self.switch})
        )
        self._attr_is_on = True

        self._attr_extra_state_attributes[ATTR_POSTACTIVE] = False
        self._attr_extra_state_attributes[ATTR_POSTACTIVE_START] = None
        self._attr_extra_state_attributes[ATTR_POSTACTIVE_END] = None

        self.async_write_ha_state()
        
    def turn_off(self):
        _LOGGER.debug(f"Pump {self.name} turn off")
        self._hass.async_create_task(
            self._hass.services.async_call("switch", "turn_off", {"entity_id": self.switch})
        )
        self._attr_is_on = False

        self._attr_extra_state_attributes[ATTR_POSTACTIVE] = False
        self._attr_extra_state_attributes[ATTR_POSTACTIVE_START] = None
        self._attr_extra_state_attributes[ATTR_POSTACTIVE_END] = None

        self.async_write_ha_state()

    def postactive(self):
        _LOGGER.debug(f"Pump {self.name} postactive")
        self._attr_extra_state_attributes[ATTR_POSTACTIVE] = True
        self._attr_extra_state_attributes[ATTR_POSTACTIVE_START] = datetime.datetime.now()
        self._attr_extra_state_attributes[ATTR_POSTACTIVE_END] = \
            datetime.datetime.now() + datetime.timedelta(seconds=self.master.postactive_time)

        self.async_write_ha_state()

    def __str__(self):
        return f"Pump(name={self.name}, switch={self.switch})"

class Room(SwitchEntity):

    should_poll = False

    def __init__(self, name, master):
        super().__init__()

        self._attr_name = slugify(name)
        self._attr_unique_id = slugify(f"multizone_{master.name}_room_{name}")
        self._attr_available = True
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_is_on = False
        self._icon = { STATE_ON: "mdi:pump", STATE_OFF: "mdi:pump-off"}
        self._attr_device_info = master.device_info

        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes[ATTR_BOOST] = False

        self._master = master
        self.pumps = []
        self.valves = []
        #self.name = name

    async def async_turn_on(self, **kwargs) -> None:
        _LOGGER.debug(f"Room {self.name} turn on")
        self._attr_is_on = True
        self.async_write_ha_state()

        self._master.adjust()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.debug(f"Room {self.name} turn off")
        self._attr_is_on = False
        self.async_write_ha_state()
        
        self._master.adjust()

    def __str__(self):
        return f"Room(name={self._name}, pumps=[{self._pumps}], valves=[{self._valves}])"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": NAME,
            "model": VERSION,
            "manufacturer": MANUFACTURER,
        }

class ZoneMaster(BinarySensorEntity):

    should_poll = False

    def __init__(self, hass: HomeAssistant, config: dict, name: str) -> None:
        self._hass = hass

        self._attr_name = name
        self._attr_device_class = BinarySensorDeviceClass.HEAT
        self._attr_unique_id = f"multizone_zonemaster_{name}"
        self._attr_is_on = False

        self.rooms = []
        self.master_switch = None

        self.keep_alive_timeout = None
        self.keep_alive_entity = None
        self.keep_alive_timer = None
        if "keep_alive" in config:
            ka = config.get("keep_alive")
            self.keep_alive_timeout = int(ka.get("timeout")) * 60 if "timeout" in ka else None
            self.keep_alive_entity = ka.get("entity_id") if "entity_id" in ka else None

        self.entities = [self]

        self.laststate = set() # Rooms, where the heating is on
        
        self.postactive_pumps = set() # Pumps, which are kept on for a while
        self.postactive_time = int(config.get("keep_active")) * 60 if "keep_active" in config else None
        self.postactive_timer = None

        def import_pumps(lconf: list):
            if lconf is None:
                return []
            pumps = []
            for conf in lconf:
                e = conf.get("entity_id")
                if e is None:
                    continue
                pump = Pump(e, self)
                self.entities.append(pump)
                pumps.append(pump)
            return pumps

        def import_valves(lconf: list):
            if lconf is None:
                return []
            valves = []
            for conf in lconf:
                e = conf.get("switch")
                if e is None:
                    continue
                valves.append(Valve(e, self, "switch"))
            for conf in lconf:
                e = conf.get("valve")
                if e is None:
                    continue
                valves.append(Valve(e, self, "valve"))
            return valves

        def import_zone(lconf: list, pumps, valves):
            for conf in lconf:
                name = conf.get("name") if "name" in conf else "Unknown"
                new_pumps = []
                new_valves = []
                if "pumps" in conf:
                    new_pumps = import_pumps(conf.get("pumps"))
                if "valves" in conf:
                    new_valves = import_valves(conf.get("valves"))
                new_pumps.extend(pumps)
                new_valves.extend(valves)
                if "zones" in conf:
                    import_zone(conf.get("zones"), new_pumps.copy(), new_valves.copy())
                else:
                    room = Room(name, self)
                    room.pumps = new_pumps
                    room.valves = new_valves
                    self.entities.append(room)
                    self.rooms.append(room)

        _LOGGER.info("ZoneMaster config: %s", config)
        self.master_switch = config.get("switch")

        import_zone([config], [], [])

        _LOGGER.info("ZoneMaster params:")
        _LOGGER.info("Master switch: %s", self.master_switch)
        _LOGGER.info("Keep alive timeout: %s", self.keep_alive_timeout)
        _LOGGER.info("Keep alive entity: %s", self.keep_alive_entity)
        _LOGGER.info("Postactive time: %s", self.postactive_time)
        for r in self.rooms:
            _LOGGER.info("Room: %s", r.name)
            _LOGGER.info("Pumps: %s", r.pumps)
            _LOGGER.info("Valves: %s", r.valves)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": NAME,
            "model": VERSION,
            "manufacturer": MANUFACTURER,
        }

    def turn_on(self):
        _LOGGER.debug(f"Multizone master {self.name} turn on")
        self._attr_is_on = True
        self._hass.async_create_task(
            self._hass.services.async_call("switch", "turn_on", {"entity_id": self.master_switch})
        )

    def turn_off(self):
        _LOGGER.debug(f"Multizone master {self.name} turn off")
        self._attr_is_on = False
        self._hass.async_create_task(
            self._hass.services.async_call("switch", "turn_off", {"entity_id": self.master_switch})
        )

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Maintain the state of the master switch
        if self.keep_alive_timeout is not None and self.keep_alive_entity is not None:
            self.keep_alive_timer = async_call_later(self._hass, self.keep_alive_timeout, self.keep_alive)

        # Turn off the master switch, at the beginning
        self.turn_off()

    async def postactive_stop(self, _):
        if self.postactive_timer is not None:
            self.postactive_timer() # Stop the timer
        
        _LOGGER.debug("Postactive stop ends")
        _LOGGER.debug("Postactive pumps: %s", self.postactive_pumps)
        for p in self.postactive_pumps:
            p.turn_off()

        self.postactive_pumps = set()
        self.postactive = False

    async def keep_alive(self, _):
        _LOGGER.debug("Keep alive")
        if self.keep_alive_entity is not None:
            if self.keep_alive_entity.startswith("button."):
                self._hass.async_create_task(
                    self._hass.services.async_call("button", "press", {"entity_id": self.keep_alive_entity})
                )
        self.keep_alive_timer = async_call_later(self._hass, self.keep_alive_timeout, self.keep_alive)

    def adjust(self):
        _LOGGER.debug("Adjusting")

        def pumps_set(rooms):
            pumps = set()
            for r in rooms:
                pumps.update(r.pumps)
            return pumps
        
        def valves_set(rooms):
            valves = set()
            for r in rooms:
                valves.update(r.valves)
            return valves
        
        # laststate is a set of rooms, where the heating is was on
        pls = pumps_set(self.laststate)
        vls = valves_set(self.laststate)

        # The actual demand for heating
        actual = set()
        for r in self.rooms:
            if r.is_on:
                actual.add(r)
        pac = pumps_set(actual)
        vac = valves_set(actual)

        # Turn heating on and off basen on demand
        if not pls and pac:
            self.turn_on()
            # Handle postactive pumps
            self.postactive = False
            if self.postactive_timer is not None:
                self.postactive_timer()
            pls = pls.union(self.postactive_pumps) # Add pumps, as if they are active
            self.postactive_pumps = set() # Clear the postactive pumps, as they are added to working pumps

        elif pls and not pac:
            self.turn_off()
            # When the main heating is truned off, the last pumps shpould be kept on for a while
            if self.postactive_time is not None:
                self.postactive_pumps = pls.copy()
                self.postactive = True
                self.portactive_timer = async_call_later(self._hass, self.postactive_time, self.postactive_stop)

        # Turn pumps on and off based on demand
        for p in pac.union(pls):
            if p in pac and not p in pls:
                p.turn_on()
                if p in self.postactive_pumps:
                    self.postactive_pumps.remove(p)
            elif p in pls and not p in pac:
                if not self.postactive:
                    p.turn_off()
                    if p in self.postactive_pumps:
                        self.postactive_pumps.remove(p)
                else:
                    p.postactive()

        # Turn valves on and off based on demand and pump state
        # When the pump is off, there is no need to change the valve state
        for r in self.rooms:
            # When a singe pump is off, the circuit is not working
            # Probably the last pump state would be enough
            # Multiple pumps with different states could be an error!
            doit = True
            for p in r.pumps:
                if not p in pac:
                    doit = False
                    break
            _LOGGER.debug(f"Valveset action: {doit}, state: {r in actual}")
            if not doit:
                continue
            # Circuit is active, adjust the valves
            for v in r.valves:
                if r in actual:
                    v.turn_on()
                else:
                    v.turn_off()

        self.laststate = actual.copy()