import voluptuous as vol
from datetime import timedelta


import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, CONF_ENTITY_ID, CONF_ENABLED
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN


"""Constants for multizone_keating."""
# Base component constants
NAME = " Multizone for heating"
DOMAIN = "multizone_heating"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ATTRIBUTION = "Data provided by ..."
ISSUE_URL = "https://github.com/gume/multizone_heating/issues"
MANUFACTURER = "Gume"


# Configuration and options
CONF_ZONES = "zones"
CONF_SUBZONES = "subzones"
CONF_SENSOR = "sensor"
CONF_SWITCH = "switch"
CONF_VALVES = "valves"
CONF_PUMPS = "pumps"
CONF_KEEP_ALIVE = "keep_alive"
CONF_KEEP_ACTIVE = "keep_active"

CONF_IMPORT = "import_id"
CONF_MAIN = "Main Controller"
CONF_ZONE = "Zone"

CONF_BOOST_TIME = "boost_time"
PRESET_DEFAULTS = { CONF_BOOST_TIME: 15 * 1 }
#PRESET_DEFAULTS = { CONF_BOOST_TIME: 15 * 60 }

ATTR_ACTIVE = "active"
ATTR_ACTIVE_START = "active_start"
ATTR_ACTIVE_END = "active_end"
ATTR_BOOST = "boost"
ATTR_BOOST_START = "boost_start"
ATTR_BOOST_END = "boost_end"

# Defaults
DEFAULT_NAME = DOMAIN


CONFIG_VALVES = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

CONFIG_SUBZONE = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_VALVES): vol.All([CONFIG_VALVES]),
    vol.Optional(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_BOOST_TIME): vol.Coerce(float),
})

CONFIG_TARGET_SWITCH = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_domain([SWITCH_DOMAIN]),
#    vol.Optional(CONF_KEEP_ALIVE, default=None): vol.Any(None, cv.positive_time_period, cv.positive_timedelta),
    vol.Optional(CONF_KEEP_ALIVE, default=None): vol.Any(None, cv.string),
#    vol.Optional(CONF_KEEP_ACTIVE, default=None): vol.Any(None, cv.positive_time_period, cv.positive_timedelta),
    vol.Optional(CONF_KEEP_ACTIVE, default=None): vol.Any(None, cv.string),
})

CONFIG_ZONE = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Required(CONF_PUMPS): vol.All([CONFIG_TARGET_SWITCH]),
    vol.Required(CONF_SUBZONES): vol.All([CONFIG_SUBZONE]),
    vol.Optional(CONF_BOOST_TIME): vol.Coerce(float),
})

CONFIG_SCHEMA = vol.Schema({
        DOMAIN: vol.Schema({
            vol.Required(CONF_PUMPS): vol.All([CONFIG_TARGET_SWITCH]),
            vol.Required(CONF_ZONES): vol.All([CONFIG_ZONE]),
            vol.Optional(CONF_ENABLED): cv.boolean,
            vol.Optional(CONF_BOOST_TIME): vol.Coerce(float),
        })
    },
    extra = vol.ALLOW_EXTRA,
)


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
