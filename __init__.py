import asyncio
from datetime import timedelta
import logging
import voluptuous as vol
import hashlib


from homeassistant.core import Config, HomeAssistant, ServiceCall, callback
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, CONF_ENTITY_ID, CONF_ENABLED
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate.const import SERVICE_SET_PRESET_MODE
from homeassistant.util import slugify

from .multizones import ZoneMaster

from .const import (
    DOMAIN,
    CONF_IMPORT,
    CONF_ZONES,
    CONFIG_SCHEMA,
)

PLATFORMS = [ SWITCH_DOMAIN, BINARY_SENSOR_DOMAIN ]

_LOGGER: logging.Logger = logging.getLogger(__package__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    if DOMAIN not in config:
        return True
    #_LOGGER.debug(config[DOMAIN])
    config = config[DOMAIN]

    """ Tell whether this config is already available in config_entries """
    def order_dict(dictionary):
        # Create a straightforward order of the values. First sort by value, then sort by key
        return {k: order_dict(v) if isinstance(v, dict) else v for k, v in sorted(dictionary.items())}
    def sort_dict_keys(input_dict):
        sorted_dict = {}
        for key in sorted(input_dict.keys()):
            value = input_dict[key]
            if isinstance(value, dict):
                value = sort_dict_keys(value)
            elif isinstance(value, (list, tuple)):
                value = [sort_dict_keys(item) if isinstance(item, dict) else item for item in value]
            sorted_dict[key] = value
        return sorted_dict

    def imported(iid):
        result = False
        for ce in hass.config_entries.async_entries(DOMAIN):
            if CONF_IMPORT in ce.data:
                if ce.data[CONF_IMPORT] == iid:
                    result = True
                    break
        return result

    # Add the main zone controller                
    iid =  hashlib.md5(str(sort_dict_keys(config)).encode('utf-8')).hexdigest()
    #_LOGGER.debug(str(sort_dict_keys(config)))
    #_LOGGER.debug(iid)

    if not imported(iid):
        config[CONF_IMPORT] = iid
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config
            )
        )
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    zonemaster = ZoneMaster(hass, entry.data, "Master")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = zonemaster

    for p in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, p)
        )
    #hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    _LOGGER.debug(f"Unload entry: {entry}")
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details

    #unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    unload_ok = True
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
