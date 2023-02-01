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
CONF_TARGET_TEMP = "target_temp"
CONF_AWAY_TEMP = "away_temp"
CONF_VACATION_TEMP = "vacation_temp"
CONF_NIGHT_TEMP = "night_temp"
CONF_CONTROL = "control"
CONF_KEEP_ALIVE = "keep_alive"
CONF_KEEP_ACTIVE = "keep_active"
CONF_PUMPS = "pumps"
CONF_IMPORT = "import_id"
CONF_MAIN = "Main Controller"
CONF_ZONE = "Zone"
CONF_MODES = [ "busy", "away", "night", "vacation", "burst", "off", "manual" ]

SERVICE_SUBZONE_PRESET_MODE = "subzone_preset_mode"
ATTR_ACTIVE = "active"
ATTR_ACTIVE_START = "active_start"
ATTR_ACTIVE_END = "active_end"


# Defaults
DEFAULT_NAME = DOMAIN

CONFIG_VALVES = vol.Schema({
    vol.Required(CONF_SWITCH): cv.entity_id,
})

CONFIG_SUBZONE = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_VALVES): vol.All([CONFIG_VALVES]),
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
    vol.Optional(CONF_VACATION_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NIGHT_TEMP): vol.Coerce(float),
    vol.Optional(CONF_CONTROL): cv.entity_id,
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
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
    vol.Optional(CONF_VACATION_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NIGHT_TEMP): vol.Coerce(float),
    vol.Required(CONF_PUMPS): vol.All([CONFIG_TARGET_SWITCH]),
    vol.Required(CONF_SUBZONES): vol.All([CONFIG_SUBZONE]),
})

CONFIG_SCHEMA = vol.Schema({
        DOMAIN: vol.Schema({
            vol.Required(CONF_PUMPS): vol.All([CONFIG_TARGET_SWITCH]),
            vol.Required(CONF_ZONES): vol.All([CONFIG_ZONE]),
            vol.Optional(CONF_ENABLED): cv.boolean,
        })
    },
    extra = vol.ALLOW_EXTRA,
)


def remove_platform_name(str):
    for tag in ['sensor', 'switch', 'input_number', 'input_boolean']:
        if str.startswith(f"{tag}."):
            return str[len(tag) + 1:]
    return str


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
