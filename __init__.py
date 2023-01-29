import asyncio
from datetime import timedelta
import logging
import voluptuous as vol
import hashlib


from homeassistant.core import Config, HomeAssistant
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, CONF_ENTITY_ID, CONF_ENABLED
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.util import slugify

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .multizones import Zone, ZoneMaster

from .const import (
    DOMAIN,
    CONF_IMPORT,
    CONF_ZONES,
    CONFIG_SCHEMA,
)

#PLATFORMS = [ SWITCH_DOMAIN, SENSOR_DOMAIN ]
PLATFORMS = [ SWITCH_DOMAIN ]

_LOGGER: logging.Logger = logging.getLogger(__package__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    _LOGGER.debug("Config from YAML")
    if DOMAIN not in config:
        return True
    _LOGGER.debug(config[DOMAIN])
    config = config[DOMAIN]

    """ Tell whether this config is already available in config_entries """
    def order_dict(dictionary):
        return {k: order_dict(v) if isinstance(v, dict) else v for k, v in sorted(dictionary.items())}

    def imported(iid):
        result = False
        for ce in hass.config_entries.async_entries(DOMAIN):
            if CONF_IMPORT in ce.data:
                if ce.data[CONF_IMPORT] == iid:
                    result = True
                    break
        return result

    # Add the main zone controller                
    iid =  hashlib.md5(str(config).encode('utf-8')).hexdigest()
    if not imported(iid):
        config[CONF_IMPORT] = iid
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config
            )
        )
    
    #hass.states.async_set("switch.world", "On")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    zonemaster = ZoneMaster(hass, entry.data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = zonemaster

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    _LOGGER.debug("Unload entry")
    _LOGGER.debug(entry)
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details

    #unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    unload_ok = True
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class MZHCoordinator(DataUpdateCoordinator):

    def __init__(self, hass):
        """Initialize my coordinator."""
        self.platforms = []
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        pass

