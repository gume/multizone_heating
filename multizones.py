from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.const import (
    STATE_UNKNOWN, STATE_ON, STATE_OFF,
)

from slugify import slugify

import logging
import copy

from .const import DOMAIN, NAME, VERSION, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class Pump(object):
    def __init__(self, name):
        self.name = name
        self.active_time = None

    def __str__(self):
        return f"Pump(name={self.name}, active_time={self.active_time})"

class Room(SwitchEntity):

    should_poll = False

    def __init__(self, name, master):
        super().__init__()

        self._attr_name = slugify(name)
        self._attr_unique_id = slugify(f"multizone_room_{name}")
        self._attr_available = True
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_is_on = False
        self._icon = { STATE_ON: "mdi:pump", STATE_OFF: "mdi:pump-off"}
        self._attr_device_info = master.device_info

        self._master = master
        self.pumps = []
        self.valves = []
        self.name = name

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()
        self._master.adjust()

    async def async_turn_off(self, **kwargs) -> None:
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
        self._attr_unique_id = f"multizone_{name}"
        self._attr_is_on = False

        self.rooms = []
        self.master_switch = {}

        self.keep_alive = config.get("keep_alive") if "keep_alive" in config else None
        self.entities = [self]

        self.laststate = set() # Rooms, where the heating is on

        def import_pumps(lconf: list):
            if lconf is None:
                return []
            pumps = []
            for conf in lconf:
                e = conf.get("entity_id")
                if e is None:
                    continue
                pump = Pump(e)
                pumps.append(pump)
                if "keep_active" in conf:
                    pump.active_time = conf.get("keep_active")
            return pumps

        def import_valves(lconf: list):
            if lconf is None:
                return []
            valves = []
            for conf in lconf:
                e = conf.get("switch")
                if e is None:
                    continue
                valves.append((e, "switch"))
            for conf in lconf:
                e = conf.get("valve")
                if e is None:
                    continue
                valves.append((e, "valve"))
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
                    self.rooms.append(room)

        _LOGGER.info("ZoneMaster config: %s", config)
        self.master_switch = config.get("switch")
        import_zone([config], [], [])

        for r in self.rooms:
            _LOGGER.error("Room: %s", r.name)
            _LOGGER.error("Pumps: %s", r.pumps)
            _LOGGER.error("Valves: %s", r.valves)

        self.entities.extend(self.rooms)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": NAME,
            "model": VERSION,
            "manufacturer": MANUFACTURER,
        }
    
    def adjust(self):
        _LOGGER.error("Adjusting")

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
        
        pls = pumps_set(self.laststate)
        vls = valves_set(self.laststate)

        actual = set()
        for r in self.rooms:
            if r.is_on:
                actual.add(r)
        pac = pumps_set(actual)
        vac = valves_set(actual)

        # Turn heating on and off basen on demand
        if not pls and pac:
            self._attr_is_on = True
            self._hass.async_create_task(
                self._hass.services.async_call("switch", "turn_on", {"entity_id": self.master_switch})
            )
        elif pls and not pac:
            self._attr_is_on = False
            self._hass.async_create_task(
                self._hass.services.async_call("switch", "turn_off", {"entity_id": self.master_switch})
            )

        # TBD: Last pumps shpould be kept on for a while

        # Turn pumps on and off based on demand
        for p in pac.union(pls):
            if p in pac and not p in pls:
                self._hass.create_task(
                    self._hass.services.async_call("switch", "turn_on", {"entity_id": p.name})
                )
            elif p in pls and not p in pac:
                self._hass.create_task(
                    self._hass.services.async_call("switch", "turn_off", {"entity_id": p.name})
                )
        # Turn valves on and off based on demand
        for v, vt in vac.union(vls):
            if v in vac and not v in vls:
                self._hass.services.async_call(vt, "turn_on", {"entity_id": v})
            elif v in vls and not v in vac:
                self._hass.services.async_call(vt, "turn_off", {"entity_id": v})

        self.laststate = actual.copy()