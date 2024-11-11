from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.switch import SwitchEntity

from slugify import slugify

import logging
import copy

from .const import DOMAIN, NAME, VERSION, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class Pump(object):
    def __init__(self, name):
        self._name = name
        self._active_time = None

    def __str__(self):
        return f"Pump(name={self._name}, active_time={self._active_time})"

class Room(SwitchEntity):

    should_poll = False

    def __init__(self, name):
        super().__init__()

        self._attr_name = slugify(name)
        self._attr_unique_id = slugify(f"multizone_room_{name}")

        self._pumps = []
        self._valves = []

    def __str__(self):
        return f"Room(name={self._name}, pumps=[{self._pumps}], valves=[{self._valves}])"



class ZoneMaster(BinarySensorEntity):

    should_poll = False

    def __init__(self, hass: HomeAssistant, config: dict, name: str) -> None:
        self._hass = hass

        self._rooms = []
        self._pumps = {}
        self._valves = {}
        self._keep_alive = config.get("keep_alive") if "keep_alive" in config else None
        self._entities = [self]

        self._attr_name = name
        self._attr_device_class = BinarySensorDeviceClass.HEAT
        self._attr_unique_id = f"multizone_{name}"
        self._attr_is_on = False

        def import_pumps(lconf: list):
            pumps = []
            for conf in lconf:
                e = conf.get("entity_id")
                if e is None:
                    continue
                pumps.append(e)
                pump = self._pumps[e] if e in self._pumps else Pump(e)
                if "keep_active" in conf:
                    pump._active_time = conf.get("keep_active")
                self._pumps[e] = pump
            return pumps

        def import_valves(lconf: list):
            valves = []
            for conf in lconf:
                e = conf.get("switch")
                if e is None:
                    continue
                valves.append(e)
                if e not in self._valves:
                    self._valves[e] = (e, "switch")
            for conf in lconf:
                e = conf.get("valve")
                if e is None:
                    continue
                valves.append(e)
                if e not in self._valves:
                    self._valves[e] = (e, "valve")
            _LOGGER.error("Valves: %s", valves)
            return valves

        def import_zone(lconf: list, pumps, valves):
            for conf in lconf:
                _LOGGER.error("Importing zone: %s", conf)
                name = conf.get("name") if "name" in conf else "Unknown"
                if "pumps" in conf:
                    new_pumps = import_pumps(conf.get("pumps"))
                    pumps.extend(new_pumps)
                if "valves" in conf:
                    new_valves = import_valves(conf.get("valves"))
                    valves.extend(new_valves)
                if "zones" in conf:
                    import_zone(conf.get("zones"), pumps.copy(), valves.copy())
                else:
                    room = Room(name)
                    room._pumps = pumps.copy()
                    room._valves = valves.copy()
                    self._rooms.append(room)

        _LOGGER.error("ZoneMaster config: %s", config)
        import_zone([config], [], [])

        _LOGGER.error("ZoneMaster rooms: %s", self._rooms)
        _LOGGER.error("ZoneMaster pumps: %s", self._pumps)
        _LOGGER.error("ZoneMaster valves: %s", self._valves)

        self._entities.extend(self._rooms)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": NAME,
            "model": VERSION,
            "manufacturer": MANUFACTURER,
        }